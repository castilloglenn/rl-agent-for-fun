"""8 rays around the car, starting at its body edge (roadmap step 3e)."""

import math

import pytest

from src.config import get_maze_car_config
from src.sim.components import Sensors, Transform
from src.sim.factories import create_car, create_world
from src.sim.geometry import body_edge_distance, car_corners
from src.sim.resources import Field
from src.utils.types import Colors

WIDTH, HEIGHT = 24, 16


def _car(x, y, angle=0.0):
    world = create_world(get_maze_car_config())
    car = create_car(
        world, x, y, WIDTH, HEIGHT, Colors.SKY_BLUE, angle=angle
    )
    return world, car


def _rays(world, car):
    return {ray.name: ray for ray in world.component(car, Sensors).rays}


def test_eight_rays_around_the_car():
    world, car = _car(400, 300)
    rays = world.component(car, Sensors).rays
    assert [(ray.name, ray.angle) for ray in rays] == [
        ("front", 0),
        ("front_left", 45),
        ("left", 90),
        ("back_left", 135),
        ("back", 180),
        ("back_right", -135),
        ("right", -90),
        ("front_right", -45),
    ]


def test_body_edge_distances():
    assert body_edge_distance(0, WIDTH, HEIGHT) == pytest.approx(12)
    assert body_edge_distance(180, WIDTH, HEIGHT) == pytest.approx(12)
    assert body_edge_distance(90, WIDTH, HEIGHT) == pytest.approx(8)
    # At 45°, the ray leaves through the long side, not the corner.
    assert body_edge_distance(45, WIDTH, HEIGHT) == pytest.approx(
        8 / math.sin(math.radians(45))
    )


@pytest.mark.parametrize("angle", [0, 30, 90, 200])
def test_rays_start_on_the_body_edge(angle):
    """Each start point lies on the car's outline (the hitbox polygon)."""
    world, car = _car(400, 300, angle)
    corners = car_corners(400, 300, angle, WIDTH, HEIGHT)
    edges = list(zip(corners, corners[1:] + corners[:1]))
    for ray in world.component(car, Sensors).rays:
        point = (ray.start.x, ray.start.y)
        assert min(_distance_to_segment(point, a, b) for a, b in edges) == (
            pytest.approx(0, abs=1e-9)
        )


def test_exact_distances_facing_right():
    world, car = _car(400, 300)
    field = world.resource(Field).rect
    rays = _rays(world, car)
    assert rays["front"].distance == pytest.approx(field.right - 412)
    assert rays["back"].distance == pytest.approx(388 - field.left)
    assert rays["left"].distance == pytest.approx(292 - field.top)
    assert rays["right"].distance == pytest.approx(field.bottom - 308)


def test_rays_rotate_with_the_car():
    world, car = _car(400, 300, angle=90)  # facing up
    field = world.resource(Field).rect
    rays = _rays(world, car)
    assert rays["front"].distance == pytest.approx(288 - field.top)
    assert rays["left"].distance == pytest.approx(392 - field.left)


def test_touching_the_border_reads_zero():
    field = get_maze_car_config().field
    right = int(field.x) + int(field.width)
    world, car = _car(right - WIDTH / 2, 300)
    assert _rays(world, car)["front"].distance == pytest.approx(0, abs=1e-9)


def test_ray_end_is_on_the_border():
    world, car = _car(400, 300, angle=33)
    field = world.resource(Field).rect
    for ray in world.component(car, Sensors).rays:
        x, y = ray.end
        on_vertical = math.isclose(x, field.left, abs_tol=1e-9) or math.isclose(
            x, field.right, abs_tol=1e-9
        )
        on_horizontal = math.isclose(
            y, field.top, abs_tol=1e-9
        ) or math.isclose(y, field.bottom, abs_tol=1e-9)
        assert on_vertical or on_horizontal


def test_rays_follow_the_car_each_step():
    world, car = _car(400, 300)
    transform = world.component(car, Transform)
    transform.x -= 50
    world.step()
    field = world.resource(Field).rect
    assert _rays(world, car)["front"].distance == pytest.approx(
        field.right - 362
    )


def _distance_to_segment(point, a, b) -> float:
    (px, py), (ax, ay), (bx, by) = point, a, b
    abx, aby = bx - ax, by - ay
    t = ((px - ax) * abx + (py - ay) * aby) / (abx * abx + aby * aby)
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (ax + t * abx), py - (ay + t * aby))
