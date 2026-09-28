"""Walls inside the field (roadmap step 7a): axis-aligned rectangles from
the stage file ([x, y, width, height], decision 006). Pure geometry; the
systems use it like the border.

A car's hitbox is a rotated rectangle, so two kinds of contact can stop
a move: a car corner entering a wall, or a wall corner entering the
car's side. Each contact has a normal: the direction out of the wall,
toward the car. The move keeps its motion along the surface (the slide)
and loses the part along the normal (the impact).

Points on a surface count as touching, not inside: a car resting against
a wall can slide along it, or drive away. EPS absorbs floating point.
"""

import math
from dataclasses import dataclass

Point = tuple[float, float]
EPS = 1e-6  # px: closer than this to a surface is on it


@dataclass(frozen=True)
class Box:
    """A wall: left, top, right, bottom in stage coordinates."""

    left: float
    top: float
    right: float
    bottom: float

    @staticmethod
    def from_list(wall) -> "Box":
        x, y, width, height = wall
        return Box(x, y, x + width, y + height)

    def corners(self) -> list[Point]:
        return [
            (self.left, self.top),
            (self.right, self.top),
            (self.right, self.bottom),
            (self.left, self.bottom),
        ]

    def contains(self, x: float, y: float, margin: float = EPS) -> bool:
        """Strictly inside, deeper than `margin`."""
        return (
            self.left + margin < x < self.right - margin
            and self.top + margin < y < self.bottom - margin
        )

    def distance(self, x: float, y: float) -> float:
        """From a point to the box (0 inside)."""
        dx = max(self.left - x, 0.0, x - self.right)
        dy = max(self.top - y, 0.0, y - self.bottom)
        return math.hypot(dx, dy)


@dataclass(frozen=True)
class Contact:
    fraction: float  # of the move made before touching (0 to 1)
    normal: Point  # out of the wall, toward the car (unit length)


def _point_into_box(p: Point, d: Point, box: Box):
    """When the point p moving by d first enters the box: (t, normal),
    or None. Starting on a surface and moving into it is t = 0.
    """
    t_enter, t_exit = -math.inf, math.inf
    normal, depth = None, 0.0
    slabs = ((0, box.left, box.right), (1, box.top, box.bottom))
    for axis, near, far in slabs:
        position, step = p[axis], d[axis]
        if abs(step) < 1e-12:
            if not near + EPS < position < far - EPS:
                return None  # alongside or outside: never enters
            continue
        if step > 0:
            t_in, t_out = (near - position) / step, (far - position) / step
            face = (-1.0, 0.0) if axis == 0 else (0.0, -1.0)
            beyond = position - near  # how far past this face already
        else:
            t_in, t_out = (far - position) / step, (near - position) / step
            face = (1.0, 0.0) if axis == 0 else (0.0, 1.0)
            beyond = far - position
        if t_in > t_enter:
            t_enter, normal, depth = t_in, face, beyond
        t_exit = min(t_exit, t_out)
    return _entry(t_enter, t_exit, normal, depth)


def _entry(t_enter, t_exit, normal, depth):
    """(t, normal) for an entry during the move, or None. A point at
    most EPS past the surface at the start is touching (t = 0); deeper,
    it's already inside and this isn't its contact.
    """
    if normal is None or t_enter >= t_exit or t_enter > 1 or t_exit <= 0:
        return None
    if t_enter < 0:
        if depth > EPS:
            return None
        t_enter = 0.0
    return t_enter, normal


def _point_into_polygon(q: Point, d: Point, polygon: list[Point]):
    """When the point q moving by d first enters the convex polygon
    (corners in order): (t, the entered edge's outward normal), or None.
    """
    t_enter, t_exit = -math.inf, math.inf
    normal, depth = None, 0.0
    count = len(polygon)
    # Orientation, so each edge's normal points outward.
    area = sum(
        polygon[i][0] * polygon[(i + 1) % count][1]
        - polygon[(i + 1) % count][0] * polygon[i][1]
        for i in range(count)
    )
    sign = 1.0 if area > 0 else -1.0
    for i in range(count):
        (ax, ay), (bx, by) = polygon[i], polygon[(i + 1) % count]
        ex, ey = bx - ax, by - ay
        length = math.hypot(ex, ey)
        nx, ny = sign * ey / length, -sign * ex / length  # outward
        # Signed distance of q outside this edge, and how d changes it.
        outside = (q[0] - ax) * nx + (q[1] - ay) * ny
        rate = d[0] * nx + d[1] * ny
        if abs(rate) < 1e-12:
            if outside > -EPS:
                return None  # alongside or outside this edge
            continue
        t = -outside / rate
        if rate < 0:  # moving inward across this edge
            if t > t_enter:
                t_enter, normal, depth = t, (nx, ny), -outside
        else:
            t_exit = min(t_exit, t)
    return _entry(t_enter, t_exit, normal, depth)


def wall_contact(
    corners: list[Point], dx: float, dy: float, walls: tuple[Box, ...]
) -> Contact | None:
    """The first wall the car (its hitbox corners, in order) touches when
    it moves by (dx, dy), or None.
    """
    if not walls or (dx == 0 and dy == 0):
        return None
    best = None
    d = (dx, dy)
    back = (-dx, -dy)
    for box in walls:
        for corner in corners:  # a car corner into the wall
            hit = _point_into_box(corner, d, box)
            if hit and (best is None or hit[0] < best.fraction):
                best = Contact(hit[0], hit[1])
        for corner in box.corners():  # a wall corner into the car
            hit = _point_into_polygon(corner, back, corners)
            if hit and (best is None or hit[0] < best.fraction):
                # The car's edge was entered: the wall pushes back on it.
                nx, ny = hit[1]
                best = Contact(hit[0], (-nx, -ny))
    return best


def slide(dx: float, dy: float, normal: Point) -> tuple[Point, float]:
    """The motion left along the surface, and the speed into it (px per
    step, for the damage).
    """
    nx, ny = normal
    into = dx * nx + dy * ny  # negative: toward the wall
    return (dx - into * nx, dy - into * ny), abs(into)


def overlaps(corners: list[Point], box: Box) -> bool:
    """True when the car's hitbox and the wall overlap by more than EPS
    (touching doesn't count). Separating axes: the box's two and the
    car's two.
    """
    axes = [(1.0, 0.0), (0.0, 1.0)]
    for i in (0, 1):
        (ax, ay), (bx, by) = corners[i], corners[i + 1]
        length = math.hypot(bx - ax, by - ay)
        axes.append(((by - ay) / length, -(bx - ax) / length))
    wall = box.corners()
    for ux, uy in axes:
        car = [x * ux + y * uy for x, y in corners]
        other = [x * ux + y * uy for x, y in wall]
        if min(car) >= max(other) - EPS or min(other) >= max(car) - EPS:
            return False
    return True


def ray_to_walls(
    x: float, y: float, dx: float, dy: float, walls: tuple[Box, ...]
) -> float:
    """Distance from (x, y) along the unit vector (dx, dy) to the nearest
    wall (math.inf if none is in the way).
    """
    best = math.inf
    for box in walls:
        t_enter, t_exit = -math.inf, math.inf
        for position, step, near, far in (
            (x, dx, box.left, box.right),
            (y, dy, box.top, box.bottom),
        ):
            if abs(step) < 1e-12:
                if not near - EPS <= position <= far + EPS:
                    t_enter = math.inf  # parallel and outside: a miss
                continue
            t_in, t_out = (near - position) / step, (far - position) / step
            if t_in > t_out:
                t_in, t_out = t_out, t_in
            t_enter, t_exit = max(t_enter, t_in), min(t_exit, t_out)
        if t_enter <= t_exit and t_exit >= 0:
            best = min(best, max(t_enter, 0.0))
    return best


def rotation_into_walls(
    before: list[Point], after: list[Point], walls: tuple[Box, ...]
) -> float | None:
    """None if the turned hitbox (`after`) is clear of every wall. Else
    the impact (px per step): the speed of the fastest corner that
    ended inside a wall, or of any corner when a wall corner pokes in.
    """
    hit = [box for box in walls if overlaps(after, box)]
    if not hit:
        return None
    moved = [math.dist(a, b) for a, b in zip(before, after)]
    inside = [
        m
        for m, (x, y) in zip(moved, after)
        if any(box.contains(x, y) for box in hit)
    ]
    return max(inside) if inside else max(moved)
