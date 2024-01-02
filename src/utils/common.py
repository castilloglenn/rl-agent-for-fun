import math

from pygame import Rect


def get_angular_movement_deltas(angle: int, speed: int) -> tuple:
    angle_radians = math.radians(angle)
    delta_x = math.cos(angle_radians) * speed
    delta_y = math.sin(angle_radians) * -speed

    return delta_x, delta_y


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
