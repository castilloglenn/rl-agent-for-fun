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
    fraction = 1.0
    for px, py in points:
        if dx > 0:
            fraction = min(fraction, (bounds.right - px) / dx)
        elif dx < 0:
            fraction = min(fraction, (bounds.left - px) / dx)
        if dy > 0:
            fraction = min(fraction, (bounds.bottom - py) / dy)
        elif dy < 0:
            fraction = min(fraction, (bounds.top - py) / dy)
    return max(fraction, 0.0)


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
