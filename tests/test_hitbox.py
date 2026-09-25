"""The car's hitbox is its 4 real corners (decision 004, roadmap 3d)."""

import math

import pytest

from src.config import get_maze_car_config
from src.sim.components import (
    ActionInput,
    Eliminated,
    Hitbox,
    Motion,
    Transform,
)
from src.sim.factories import create_car, create_world
from src.sim.geometry import car_corners, inside, max_move_fraction
from src.sim.resources import Field
from src.sim.stage import load_stage
from src.utils.types import Colors


def test_corners_unrotated():
    corners = car_corners(100, 100, 0, 24, 16)
    assert sorted(corners) == [(88, 92), (88, 108), (112, 92), (112, 108)]
    assert corners[0] == (112, 92)  # front-left: right side, screen up


def test_corners_rotated_90_swap_extents():
    corners = car_corners(100, 100, 90, 24, 16)
    xs = [x for x, _ in corners]
    ys = [y for _, y in corners]
    assert min(xs) == pytest.approx(92) and max(xs) == pytest.approx(108)
    assert min(ys) == pytest.approx(88) and max(ys) == pytest.approx(112)


@pytest.mark.parametrize("angle", [0, 17, 45, 90, 133, 222, 315])
def test_hitbox_never_grows(angle):
    """Unlike the old bounding box, the corners stay on the car."""
    half_diagonal = math.hypot(12, 8)
    for x, y in car_corners(0, 0, angle, 24, 16):
        assert math.hypot(x, y) == pytest.approx(half_diagonal)


def test_max_move_fraction_stops_at_the_edge():
    from pygame import Rect

    bounds = Rect(0, 0, 100, 100)
    points = [(90.0, 50.0)]
    assert max_move_fraction(points, 5, 0, bounds) == 1.0
    assert max_move_fraction(points, 20, 0, bounds) == 0.5
    assert max_move_fraction([(100.0, 50.0)], 5, 0, bounds) == 0.0


def _world_with_car(x, y, angle=0.0, speed=0.0):
    world = create_world(get_maze_car_config())
    config = get_maze_car_config().car
    car = create_car(
        world, x, y, config.width, config.height, Colors.SKY_BLUE, angle=angle
    )
    world.component(car, Motion).speed = speed
    return world, car


def _corners(world, car):
    transform = world.component(car, Transform)
    hitbox = world.component(car, Hitbox)
    return car_corners(
        transform.x, transform.y, transform.angle, hitbox.width, hitbox.height
    )


@pytest.mark.parametrize("angle", [0, 30, 45, 60])
def test_driving_into_the_border_crashes_on_exact_contact(angle):
    stage = load_stage(get_maze_car_config().stage)
    right = stage.width
    world, car = _world_with_car(right - 60, stage.height / 2, angle=angle)
    world.add_component(car, ActionInput(gas=True))

    for _ in range(600):
        world.step()

    corners = _corners(world, car)
    assert max(x for x, _ in corners) == pytest.approx(right, abs=1e-9)
    assert inside(corners, world.resource(Field).rect)
    assert world.component(car, Motion).speed == 0
    assert world.component(car, Eliminated).reason == "wall"


def test_turn_into_the_border_crashes():
    world, car = _world_with_car(0, 0)
    field = world.resource(Field).rect
    # Nose touching the right border, moving slowly.
    transform = world.component(car, Transform)
    transform.x, transform.y = field.right - 12, field.centery
    world.component(car, Motion).speed = 0.5
    world.add_component(car, ActionInput(turn_left=True, brake=True))

    world.step()

    assert transform.angle == 0  # the turn didn't happen
    assert inside(_corners(world, car), field)
    assert world.component(car, Eliminated).reason == "wall"


def test_crashed_car_stays_put():
    stage = load_stage(get_maze_car_config().stage)
    right = stage.width
    world, car = _world_with_car(right - 30, stage.height / 2, speed=2.0)
    world.add_component(car, ActionInput(gas=True))
    for _ in range(60):
        world.step()
    assert world.try_component(car, Eliminated)

    x_after_crash = world.component(car, Transform).x
    world.add_component(car, ActionInput(reverse=True))
    for _ in range(60):
        world.step()
    assert world.component(car, Transform).x == x_after_crash
