"""A sense of direction and of being stuck (roadmap 7f7, decision 061).

The straight-line compass points through walls, so with a wall between
the car and the checkpoint an agent pushed into it until time ran out.
A driver without GPS still knows "the way around is over there", and
notices being stuck. So the agent gets:

- a **remembered waypoint** along the shortest drivable route to the
  checkpoint (the last point of that route still in a straight, car-wide
  line from the car: about one corner ahead), held, and refreshed when
  the car reaches it or every REFRESH_SECONDS (between, the car sees its
  direction relative to its own heading, every step);
- the **remembered route distance**, refreshed with the waypoint;
- a **stuck timer**: seconds since the car last got closer along the
  route than it had been to this checkpoint.

The route knows only the map's walls (they don't move), from the same
route field as the progress reward (one per checkpoint, shared through
RouteFields). Other cars, later, are for the rays. Deterministic: it
reads only the world, so replays rebuild it.
"""

import math
from dataclasses import dataclass

from src.ecs import World
from src.sim.components import Checkpoint, Transform
from src.sim.paths import PathField
from src.sim.resources import Field, SimClock, SimConfig, Walls

REFRESH_SECONDS = 2.0  # a held waypoint is refreshed at least this often
REACH = 30.0  # px: this close, the waypoint is reached (refreshed)
PROGRESS = 10.0  # px closer along the route than before: progress
STUCK_CAP = 10.0  # seconds: the stuck input reads 1 from here on
STEP = 12.0  # px: how far each step of the walk along the route goes
SIGHT = 10.0  # px: a straight line this clear of walls is in sight
SKIP = 14.0  # px: the line's start inside the car's own body isn't checked
MAX_WALK = 160  # steps of the walk (about 1,900 px)
FIELDS = 64  # route fields kept (random checkpoints never repeat)


class RouteFields:
    """Route fields by goal, shared by the route sense and the progress
    reward, for one game (a new world starts empty).
    """

    def __init__(self) -> None:
        self.fields: dict[tuple, PathField] = {}

    def field(self, world: World, goal: tuple[float, float]) -> PathField:
        found = self.fields.get(goal)
        if found is None:
            if len(self.fields) >= FIELDS:
                self.fields.clear()
            rect = world.resource(Field)
            walls = world.resource(Walls).boxes
            found = PathField(
                (rect.x, rect.y, rect.width, rect.height),
                [(w.left, w.top, w.right, w.bottom) for w in walls],
                goal,
            )
            self.fields[goal] = found
        return found


def route_fields(world: World) -> RouteFields:
    """The world's route fields (made on first use)."""
    try:
        return world.resource(RouteFields)
    except KeyError:
        fields = RouteFields()
        world.add_resource(fields)
        return fields


@dataclass
class RouteSense:
    """A car's remembered route to its checkpoint, and its stuck timer."""

    goal: tuple[float, float] | None = None
    waypoint: tuple[float, float] | None = None
    distance: float = math.inf  # px along the route, when refreshed
    refreshed: int = 0  # the step of the last refresh
    best: float = math.inf  # the closest it has been along the route
    progress: int = 0  # the step it last got closer
    updated: int | None = None  # the step it was last updated


def nearest_checkpoint(world: World, x: float, y: float):
    spots = [(s.x, s.y) for _, (s, _) in world.query(Transform, Checkpoint)]
    if not spots:
        return None
    return min(spots, key=lambda spot: math.dist(spot, (x, y)))


def sense(world: World, car: int) -> RouteSense:
    """The car's route sense, brought up to this step (once a step)."""
    route = world.try_component(car, RouteSense)
    if route is None:
        route = RouteSense()
        world.add_component(car, route)
    step = world.resource(SimClock).step
    if route.updated == step:
        return route
    route.updated = step
    transform = world.component(car, Transform)
    here = (transform.x, transform.y)
    goal = nearest_checkpoint(world, *here)
    if goal is None:
        route.goal = route.waypoint = None
        return route
    path = route_fields(world).field(world, goal)
    if goal != route.goal:  # a new checkpoint: start over
        route.goal = goal
        route.best = path.distance(*here)
        route.progress = step
        _refresh(world, route, path, here, step)
        return route
    live = path.distance(*here)
    if live < route.best - PROGRESS:
        route.best, route.progress = live, step
    sps = world.resource(SimConfig).steps_per_second
    reached = route.waypoint and math.dist(here, route.waypoint) < REACH
    if reached or step - route.refreshed >= REFRESH_SECONDS * sps:
        _refresh(world, route, path, here, step)
    return route


def stuck_seconds(world: World, route: RouteSense) -> float:
    if route.goal is None:
        return 0.0
    step = world.resource(SimClock).step
    return (step - route.progress) / world.resource(SimConfig).steps_per_second


def _refresh(world, route: RouteSense, path: PathField, here, step) -> None:
    route.waypoint = waypoint(path, here, route.goal, world)
    route.distance = path.distance(*here)
    route.refreshed = step


def waypoint(
    path: PathField, start, goal, world: World
) -> tuple[float, float]:
    """The last point of the route from `start` still in a straight,
    car-wide line from it (the goal itself when in sight).
    """
    boxes = world.resource(Walls).boxes
    if path.open_field or _clear(start, goal, boxes):
        return goal
    points = []
    here, left = start, path.distance(*start)
    for _ in range(MAX_WALK):
        step = _downhill(path, here, left)
        if step is None:
            break
        here, left = step
        points.append(here)
        if math.dist(here, goal) <= STEP:
            points.append(goal)
            break
    if not points:
        return goal  # no way found (inside a wall): the goal, as before
    # The route bends away from sight at most once per corner: the last
    # point in sight, found by halving (lines to later points are hidden).
    low, high = -1, len(points)  # points[low] in sight, points[high] not
    while high - low > 1:
        middle = (low + high) // 2
        if _clear(start, points[middle], boxes):
            low = middle
        else:
            high = middle
    return points[max(low, 0)]


def _downhill(path: PathField, here, left: float):
    """One STEP along the route: the neighbor (16 directions) closest to
    the goal, if it's closer than here.
    """
    best = None
    for k in range(16):
        angle = 2 * math.pi * k / 16
        x = here[0] + STEP * math.cos(angle)
        y = here[1] + STEP * math.sin(angle)
        d = path.distance(x, y)
        if d < left - 1.0 and (best is None or d < best[1]):
            best = ((x, y), d)
    return best


def _clear(a, b, boxes) -> bool:
    """A straight line from a to b keeps SIGHT px from every wall (past
    its first SKIP px, inside the car's own body).
    """
    length = math.dist(a, b)
    if length <= SKIP:
        return True
    n = max(int((length - SKIP) / 6), 1)
    for i in range(n + 1):
        t = (SKIP + (length - SKIP) * i / n) / length
        x = a[0] + (b[0] - a[0]) * t
        y = a[1] + (b[1] - a[1]) * t
        if any(box.distance(x, y) < SIGHT for box in boxes):
            return False
    return True
