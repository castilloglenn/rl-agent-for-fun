"""The car's hitbox is its 4 real corners (decision 004, roadmap 3d)."""

import math

import pytest

from src.config import get_maze_car_config
from src.sim.components import (
    ActionInput,
    Eliminated,
    Health,
    Hitbox,
    Motion,
    Transform,
)
from src.sim.factories import create_car, create_world
from src.sim.geometry import car_corners, inside, max_move_fraction
from src.sim.resources import Field, SimClock
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


def _world_with_car(x, y, angle=0.0, speed=0.0, rules="standard"):
    config = get_maze_car_config()
    config.rules = rules
    world = create_world(config)
    car = create_car(
        world, x, y, config.car.width, config.car.height, Colors.SKY_BLUE,
        angle=angle,
    )
    world.component(car, Motion).speed = speed
    return world, car


def _corners(world, car):
    transform = world.component(car, Transform)
    hitbox = world.component(car, Hitbox)
    return car_corners(
        transform.x, transform.y, transform.angle, hitbox.width, hitbox.height
    )


def _drive_into_right_border(angle, rules):
    stage = load_stage(get_maze_car_config().stage)
    world, car = _world_with_car(
        stage.width - 60, stage.height / 2, angle=angle, rules=rules
    )
    world.add_component(car, ActionInput(gas=True))
    for _ in range(600):
        world.step()
    return world, car, stage.width


def test_a_slow_head_on_hit_stops_the_car_on_exact_contact():
    world, car, right = _drive_into_right_border(0, "standard")
    corners = _corners(world, car)
    assert max(x for x, _ in corners) == pytest.approx(right, abs=1e-9)
    assert inside(corners, world.resource(Field).rect)
    assert world.component(car, Motion).speed == 0
    assert not world.try_component(car, Eliminated)  # 60 px: too slow


@pytest.mark.parametrize("angle", [30, 45, 60])
def test_an_angled_hit_slides_along_the_wall(angle):
    stage = load_stage(get_maze_car_config().stage)
    world, car = _world_with_car(
        stage.width - 40, stage.height / 2, angle=angle
    )
    health = world.component(car, Health)
    world.add_component(car, ActionInput(gas=True))
    while health.contact_step is None:
        world.step()
    y = world.component(car, Transform).y
    for _ in range(20):
        world.step()
    corners = _corners(world, car)
    assert max(x for x, _ in corners) == pytest.approx(stage.width, abs=1e-9)
    assert world.component(car, Transform).y < y - 5  # it slid up
    assert world.component(car, Motion).speed > 0
    assert health.contacts == 1  # one long scrape, one contact


def test_a_car_angled_into_a_wall_can_steer_away():
    """The trap an agent fell into before sliding: a corner on the wall,
    speed reset to 0 every step, so the car could never turn.
    """
    stage = load_stage(get_maze_car_config().stage)
    world, car = _world_with_car(
        stage.width - 40, stage.height / 2, angle=45
    )
    health = world.component(car, Health)
    world.add_component(car, ActionInput(gas=True))
    while health.contact_step is None:
        world.step()
    world.add_component(car, ActionInput(gas=True, turn_left=True))
    for _ in range(120):
        world.step()
    assert health.contact_step < world.resource(SimClock).step - 30  # left
    assert world.component(car, Transform).angle > 90  # heading away


@pytest.mark.parametrize("angle", [0, 30, 45, 60])
def test_classic_rules_wreck_on_any_contact(angle):
    world, car, right = _drive_into_right_border(angle, "classic")
    corners = _corners(world, car)
    assert max(x for x, _ in corners) == pytest.approx(right, abs=1e-9)
    assert world.component(car, Motion).speed == 0
    assert world.component(car, Eliminated).reason == "wrecked"


def _nose_on_right_border(rules):
    world, car = _world_with_car(0, 0, rules=rules)
    field = world.resource(Field).rect
    transform = world.component(car, Transform)
    transform.x, transform.y = field.right - 12, field.centery
    world.component(car, Motion).speed = 0.5
    world.add_component(car, ActionInput(turn_left=True, brake=True))
    world.step()
    return world, car, transform, field


def test_turning_into_the_border_is_blocked():
    world, car, transform, field = _nose_on_right_border("standard")
    assert transform.angle == 0  # the turn didn't happen
    assert inside(_corners(world, car), field)
    assert not world.try_component(car, Eliminated)  # a slow corner: a bump


def test_classic_rules_wreck_a_turn_into_the_border():
    world, car, transform, field = _nose_on_right_border("classic")
    assert transform.angle == 0
    assert world.component(car, Eliminated).reason == "wrecked"


def test_a_wrecked_car_stays_put():
    stage = load_stage(get_maze_car_config().stage)
    right = stage.width
    world, car = _world_with_car(right - 30, stage.height / 2, speed=2.0)
    world.add_component(car, ActionInput(gas=True))
    for _ in range(60):
        world.step()
    assert world.try_component(car, Eliminated)  # 240 px/s: lethal

    x_after_wreck = world.component(car, Transform).x
    world.add_component(car, ActionInput(reverse=True))
    for _ in range(60):
        world.step()
    assert world.component(car, Transform).x == x_after_wreck
