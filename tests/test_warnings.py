import pytest

from src.config import get_maze_car_config
from src.render import warnings
from src.render.warnings import CAUTION, DANGER, NORMAL

HUD = get_maze_car_config().hud
BRAKE = get_maze_car_config().car.brake_deceleration  # 600 px/s²


def test_stopping_distance_at_max_speed_is_150_px():
    # 300 px/s: 75 px reaction (0.25 s) + 75 px braking (300² / 1200).
    assert warnings.stopping_distance(300, 0.25, BRAKE) == pytest.approx(150)
    assert warnings.stopping_distance(-300, 0.25, BRAKE) == pytest.approx(150)
    assert warnings.stopping_distance(0, 0.25, BRAKE) == 0


@pytest.mark.parametrize(
    "angle, speed, expected",
    [
        (0, 100, True),
        (45, 100, True),
        (-45, 100, True),
        (90, 100, False),
        (180, 100, False),
        (180, -50, True),
        (-135, -50, True),
        (0, -50, False),
        (0, 0, False),
    ],
)
def test_travel_path(angle, speed, expected):
    assert warnings.on_travel_path(angle, speed) is expected


def test_ray_ahead_uses_stopping_distance():
    stop = 150  # max speed
    assert warnings.ray_level(0, 400, 300, stop, HUD) == NORMAL
    assert warnings.ray_level(0, 250, 300, stop, HUD) == CAUTION  # < 2x
    assert warnings.ray_level(0, 100, 300, stop, HUD) == DANGER  # < stop


def test_same_distance_is_safe_when_slow():
    stop = warnings.stopping_distance(40, 0.25, BRAKE)  # about 11 px
    assert warnings.ray_level(0, 100, 40, stop, HUD) == NORMAL


def test_proximity_applies_to_every_ray():
    stop = 150
    for angle in (90, -90, 135, 180):  # off the travel path when driving
        assert warnings.ray_level(angle, 100, 300, stop, HUD) == NORMAL
        assert warnings.ray_level(angle, 30, 300, stop, HUD) == CAUTION
        assert warnings.ray_level(angle, 10, 300, stop, HUD) == DANGER


def test_proximity_applies_even_when_stopped():
    assert warnings.ray_level(90, 30, 0, 0, HUD) == CAUTION  # < 40
    assert warnings.ray_level(0, 10, 0, 0, HUD) == DANGER  # < 15


def test_the_more_severe_rule_wins():
    # 30 px is only amber by proximity, but red on the path at speed.
    assert warnings.ray_level(0, 30, 300, 150, HUD) == DANGER


def test_speed_is_danger_when_the_wall_ahead_is_too_close():
    assert warnings.speed_level(100, 300, 150) == DANGER
    assert warnings.speed_level(200, 300, 150) == NORMAL
    assert warnings.speed_level(None, 300, 150) == NORMAL
    assert warnings.speed_level(1, 0, 0) == NORMAL


def test_fps_levels():
    assert warnings.fps_level(120, 120, HUD) == NORMAL
    assert warnings.fps_level(100, 120, HUD) == CAUTION  # < 90 %
    assert warnings.fps_level(50, 120, HUD) == DANGER  # < 50 %
    assert warnings.fps_level(0, 120, HUD) == NORMAL  # not measured yet
