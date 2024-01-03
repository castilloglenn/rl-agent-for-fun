import math

from pygame import Rect, Vector2


def get_angular_movement_deltas(angle: int, speed: int) -> tuple:
    angle_radians = math.radians(angle)
    delta_x = math.cos(angle_radians) * speed
    delta_y = math.sin(angle_radians) * -speed

    return delta_x, delta_y


def get_extended_point(
    start_point: Vector2,
    angle: int,
    distance: int,
) -> Vector2:
    angle_radians = math.radians(abs(360 - angle))
    end_point_x = start_point.x + distance * math.cos(angle_radians)
    end_point_y = start_point.y + distance * math.sin(angle_radians)
    return Vector2(end_point_x, end_point_y)


def get_triangle_coordinates_from_rect(rect: Rect) -> tuple:
    width_quarter = rect.width // 4
    width_half = rect.width // 2
    width_three_quarters = rect.width - width_quarter
    height_quarter = rect.height // 4
    height_half = rect.height // 2
    height_three_quarters = rect.height - height_quarter

    return (
        (width_half, height_quarter),
        (width_three_quarters, height_half),
        (width_half, height_three_quarters),
    )


def get_clamped_rect(
    rect: Rect,
    constraint: Rect,
    new_x: int,
    new_y: int,
) -> tuple[bool, Rect]:
    new_rect = rect.copy()
    new_rect.x += new_x
    new_rect.y += new_y
    future_rect = new_rect.clamp(constraint)

    if new_rect.center != future_rect.center:
        return True, rect
    return False, new_rect
