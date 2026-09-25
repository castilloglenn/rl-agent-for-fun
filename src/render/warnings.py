"""When HUD values turn amber (caution) or red (danger).

Near-collision warnings use the stopping distance, so they scale with
speed: 50 px is safe when crawling, and too close at full speed.
"""

from ml_collections import ConfigDict

from src.render import theme
from src.utils.types import ColorValue

NORMAL, CAUTION, DANGER = 0, 1, 2

LABEL_COLORS = {NORMAL: theme.TEXT_DIM, CAUTION: theme.WARN, DANGER: theme.BAD}
VALUE_COLORS = {NORMAL: theme.TEXT, CAUTION: theme.WARN, DANGER: theme.BAD}


def label_color(level: int) -> ColorValue:
    return LABEL_COLORS[level]


def value_color(level: int) -> ColorValue:
    return VALUE_COLORS[level]


def stopping_distance(
    speed: float, reaction_time: float, brake_deceleration: float
) -> float:
    """px to stop from `speed` (px/s): reaction distance + braking
    distance.
    """
    speed = abs(speed)
    return speed * reaction_time + speed**2 / (2 * brake_deceleration)


def on_travel_path(ray_angle: float, speed: float) -> bool:
    """Rays pointing where the car is going: the front three when
    driving forward, the back three when reversing.
    """
    if speed > 0:
        return abs(ray_angle) <= 45
    if speed < 0:
        return abs(ray_angle) >= 135
    return False


def ray_level(
    ray_angle: float,
    distance: float,
    speed: float,
    stop_distance: float,
    hud: ConfigDict,
) -> int:
    if distance < hud.near_contact:
        return DANGER
    level = CAUTION if distance < hud.side_caution else NORMAL
    if on_travel_path(ray_angle, speed):
        if distance < stop_distance:
            return DANGER
        if distance < hud.caution_factor * stop_distance:
            level = CAUTION
    return level


def speed_level(
    ahead_distance: float | None, speed: float, stop_distance: float
) -> int:
    """Red when a wall ahead is closer than the car can stop."""
    if speed == 0 or ahead_distance is None:
        return NORMAL
    return DANGER if ahead_distance < stop_distance else NORMAL


def fps_level(fps: float, target: int, hud: ConfigDict) -> int:
    if fps <= 0:  # not measured yet
        return NORMAL
    if fps < hud.fps_danger * target:
        return DANGER
    if fps < hud.fps_caution * target:
        return CAUTION
    return NORMAL
