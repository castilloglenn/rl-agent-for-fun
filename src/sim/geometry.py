"""Car hitbox geometry: the car's 4 real corners, rotating with it.

See docs/decisions/004-polygon-hitbox-deferred.md.
"""

import math

from pygame import Rect

Point = tuple[float, float]


def car_corners(
    x: float, y: float, angle: float, width: float, height: float
) -> list[Point]:
    """Corners of a car centered at (x, y), heading `angle` degrees.

    Order: front-left, front-right, back-right, back-left. Screen y grows
    downward, so the heading vector is (cos, -sin).
    """
    radians = math.radians(angle)
    forward_x, forward_y = math.cos(radians), -math.sin(radians)
    left_x, left_y = -math.sin(radians), -math.cos(radians)
    half_length, half_width = width / 2, height / 2

    def corner(along: float, side: float) -> Point:
        return (
            x + forward_x * along + left_x * side,
            y + forward_y * along + left_y * side,
        )

    return [
        corner(half_length, half_width),
        corner(half_length, -half_width),
        corner(-half_length, -half_width),
        corner(-half_length, half_width),
    ]


def inside(points: list[Point], bounds: Rect) -> bool:
    """True when every point is within bounds (edges included)."""
    return all(
        bounds.left <= px <= bounds.right and bounds.top <= py <= bounds.bottom
        for px, py in points
    )


def max_move_fraction(
    points: list[Point], dx: float, dy: float, bounds: Rect
) -> float:
    """Largest fraction (0 to 1) of the move (dx, dy) that keeps every
    point within bounds. Below 1 means a point reached the border.
    """
    return move_until_contact(points, dx, dy, bounds)[0]


def move_until_contact(
    points: list[Point], dx: float, dy: float, bounds: Rect
) -> tuple[float, bool, bool]:
    """Like max_move_fraction, plus which borders stop the move: (fraction,
    a left or right border, a top or bottom border).
    """
    fraction_x = fraction_y = 1.0
    for px, py in points:
        if dx > 0:
            fraction_x = min(fraction_x, (bounds.right - px) / dx)
        elif dx < 0:
            fraction_x = min(fraction_x, (bounds.left - px) / dx)
        if dy > 0:
            fraction_y = min(fraction_y, (bounds.bottom - py) / dy)
        elif dy < 0:
            fraction_y = min(fraction_y, (bounds.top - py) / dy)
    fraction = max(min(fraction_x, fraction_y), 0.0)
    if fraction >= 1.0:
        return 1.0, False, False
    return fraction, fraction_x <= fraction, fraction_y <= fraction


def impact_speed(dx: float, dy: float, hit_x: bool, hit_y: bool) -> float:
    """Speed into the border(s) that stopped a move of (dx, dy) per step,
    in px per step: grazing a border hits it slower than meeting it
    head-on.
    """
    if hit_x and hit_y:  # a corner, into both at once
        return math.hypot(dx, dy)
    return abs(dx) if hit_x else abs(dy) if hit_y else 0.0


def rotation_impact(
    before: list[Point], after: list[Point], bounds: Rect
) -> float:
    """Speed into the border (px per step) of the fastest corner that a
    rotation from `before` to `after` pushes out of bounds.
    """
    speed = 0.0
    for (x0, y0), (x1, y1) in zip(before, after):
        if x1 > bounds.right or x1 < bounds.left:
            speed = max(speed, abs(x1 - x0))
        if y1 > bounds.bottom or y1 < bounds.top:
            speed = max(speed, abs(y1 - y0))
    return speed


def direction(angle: float) -> Point:
    """Unit vector for a heading in degrees (screen y grows downward)."""
    radians = math.radians(angle)
    return math.cos(radians), -math.sin(radians)


def body_edge_distance(angle: float, width: float, height: float) -> float:
    """Distance from a car's center to its body edge, along `angle`
    degrees relative to its heading. Rays start there.
    """
    along = abs(math.cos(math.radians(angle)))
    side = abs(math.sin(math.radians(angle)))
    limits = []
    if along > 1e-12:
        limits.append((width / 2) / along)
    if side > 1e-12:
        limits.append((height / 2) / side)
    return min(limits)


def distance_to_bounds(
    x: float, y: float, dx: float, dy: float, bounds: Rect
) -> float:
    """Distance from (x, y), inside bounds, along the unit vector
    (dx, dy) until it reaches the bounds' edge.
    """
    distance = math.inf
    if dx > 1e-12:
        distance = min(distance, (bounds.right - x) / dx)
    elif dx < -1e-12:
        distance = min(distance, (bounds.left - x) / dx)
    if dy > 1e-12:
        distance = min(distance, (bounds.bottom - y) / dy)
    elif dy < -1e-12:
        distance = min(distance, (bounds.top - y) / dy)
    return max(distance, 0.0)


def circle_touches_car(
    circle_x: float,
    circle_y: float,
    radius: float,
    x: float,
    y: float,
    angle: float,
    width: float,
    height: float,
) -> bool:
    """True when a circle overlaps a car's rotated hitbox (edges count).

    The circle's center is moved into the car's own frame, where the
    hitbox is an axis-aligned box, then clamped to that box.
    """
    forward_x, forward_y = direction(angle)
    left_x, left_y = direction(angle + 90)
    rel_x, rel_y = circle_x - x, circle_y - y
    along = rel_x * forward_x + rel_y * forward_y
    side = rel_x * left_x + rel_y * left_y
    nearest_along = max(-width / 2, min(along, width / 2))
    nearest_side = max(-height / 2, min(side, height / 2))
    return math.hypot(along - nearest_along, side - nearest_side) <= radius
