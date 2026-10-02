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
from collections import OrderedDict
from dataclasses import dataclass

from src.ecs import World
from src.sim.components import Checkpoint, Transform
from src.sim.paths import PathField
from src.sim.resources import Field, SimClock, SimConfig, Walls

REFRESH_SECONDS = 2.0  # a held waypoint is refreshed at least this often
REACH = 45.0  # px: this close, the waypoint is reached (refreshed)
PROGRESS = 10.0  # px closer along the route than before: progress
STUCK_CAP = 10.0  # seconds: the stuck input reads 1 from here on
STEP = 12.0  # px: how far each step of the walk along the route goes
SIGHT = 10.0  # px: a straight line this clear of walls is in sight
# The route to drive keeps this far from walls (the reward's exact route
# keeps half the car's width, so it hugs every corner); where that closes
# the way (a gap narrower than twice it), the exact route is used.
PADDING = 30.0
DETOUR = 1.1  # the padded route this much longer (and 60 px): too far
SKIP = 14.0  # px: the line's start inside the car's own body isn't checked
WALK_CLEAR = 6.0  # px: a step of the walk keeps this clear of every wall
MAX_WALK = 160  # steps of the walk (about 1,900 px)
FIELDS = 64  # route fields kept, the least recently used dropped first
# The walk's 16 directions, a STEP long.
STEPS = [
    (STEP * math.cos(angle), STEP * math.sin(angle))
    for angle in (2 * math.pi * k / 16 for k in range(16))
]


class RouteFields:
    """Route fields by goal, shared by the route sense and the progress
    reward. A field depends only on the map (its size and walls), the
    goal, and the clearance, so an env keeps one RouteFields across its
    games (`MazeCarEnv.reset`): the scripted checkpoints of a course or a
    route map are met every round, and built once.
    """

    def __init__(self) -> None:
        self.fields: OrderedDict[tuple, PathField] = OrderedDict()

    def field(
        self,
        world: World,
        goal: tuple[float, float],
        clearance: float | None = None,
    ) -> PathField:
        """The route field to `goal`: the exact one (half the car's width
        from walls, for distances and the reward), or one keeping
        `clearance` px from walls.
        """
        rect = world.resource(Field)
        area = (rect.x, rect.y, rect.width, rect.height)
        boxes = tuple(
            (w.left, w.top, w.right, w.bottom)
            for w in world.resource(Walls).boxes
        )
        key = (area, boxes, goal, clearance)
        found = self.fields.get(key)
        if found is None:
            extra = {} if clearance is None else {"clearance": clearance}
            found = PathField(area, list(boxes), goal, **extra)
            self.fields[key] = found
            if len(self.fields) > FIELDS:
                self.fields.popitem(last=False)  # the least recently used
        else:
            self.fields.move_to_end(key)
        return found

    def driving(self, world: World, goal, start) -> PathField:
        """The route to drive from `start`: PADDING px from walls, or the
        exact one where padding closes the way.
        """
        padded = self.field(world, goal, PADDING)
        exact = self.field(world, goal)
        # Padding can close a gap and send the route a long way round:
        # then the exact route it is.
        if padded.distance(*start) > exact.distance(*start) * DETOUR + 60:
            return exact
        return padded


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
    # The waypoint's own distance along the route: once the car is closer
    # than that, it has passed the waypoint (an overshoot, 7f15).
    waypoint_distance: float = 0.0
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
    # Swept past it wider than REACH: it's behind now. Don't turn back for
    # it, take the next one (7f15).
    passed = route.waypoint != route.goal and live < route.waypoint_distance
    if reached or passed or step - route.refreshed >= REFRESH_SECONDS * sps:
        _refresh(world, route, path, here, step)
    return route


def stuck_seconds(world: World, route: RouteSense) -> float:
    if route.goal is None:
        return 0.0
    step = world.resource(SimClock).step
    return (step - route.progress) / world.resource(SimConfig).steps_per_second


def _refresh(world, route: RouteSense, path: PathField, here, step) -> None:
    driving = route_fields(world).driving(world, route.goal, here)
    route.waypoint = waypoint(driving, here, route.goal, world)
    route.distance = path.distance(*here)  # exact, like the reward
    route.waypoint_distance = path.distance(*route.waypoint)
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
        step = _downhill(path, here, left, boxes)
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


def route_points(world: World, start, goal) -> list[tuple[float, float]]:
    """The whole route from `start` to `goal`, a point every STEP px:
    for showing it (7f7). The agent never sees it, only its waypoint.
    """
    path = route_fields(world).driving(world, goal, start)
    if path.open_field:
        return [start, goal]
    points = [start]
    here, left = start, path.distance(*start)
    boxes = world.resource(Walls).boxes
    for _ in range(MAX_WALK * 3):
        step = _downhill(path, here, left, boxes)
        if step is None:
            break
        here, left = step
        points.append(here)
        if math.dist(here, goal) <= STEP:
            break
    return points + [goal]


def _downhill(path: PathField, here, left: float, boxes=()):
    """One STEP along the route: the neighbor (16 directions) closest to
    the goal, if it's closer than here. A step into or across a wall is
    never taken: next to a thin wall, a point on its far side reads the
    far side's (shorter) distance, and the walk used to cut through.
    """
    # Only walls this near can come within WALK_CLEAR of a step (a point
    # STEP away is at most STEP nearer; 1 px spare for rounding): the
    # same steps, far fewer checks.
    boxes = [b for b in boxes if b.distance(*here) < STEP + WALK_CLEAR + 1]
    best = None
    for dx, dy in STEPS:
        x = here[0] + dx
        y = here[1] + dy
        middle = ((here[0] + x) / 2, (here[1] + y) / 2)
        if any(
            box.distance(*point) < WALK_CLEAR
            for box in boxes
            for point in ((x, y), middle)
        ):
            continue
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
    # Only walls this near the line's middle can come within SIGHT of it.
    middle = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    reach = length / 2 + SIGHT + 1
    boxes = [w for w in boxes if w.distance(*middle) < reach]
    n = max(int((length - SKIP) / 6), 1)
    for i in range(n + 1):
        t = (SKIP + (length - SKIP) * i / n) / length
        x = a[0] + (b[0] - a[0]) * t
        y = a[1] + (b[1] - a[1]) * t
        if any(box.distance(x, y) < SIGHT for box in boxes):
            return False
    return True
