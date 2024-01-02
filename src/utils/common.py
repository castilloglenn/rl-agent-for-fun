import math


def get_angular_movement_deltas(angle: int, speed: int) -> tuple:
    angle_radians = math.radians(angle)
    delta_x = math.cos(angle_radians) * speed
    delta_y = math.sin(angle_radians) * -speed

    return delta_x, delta_y
