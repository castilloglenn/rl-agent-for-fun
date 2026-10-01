"""A sense of direction and of being stuck (7f7): a remembered waypoint
along the drivable route, its distance, and a stuck timer.
"""

import math

import pytest

from src.config import get_maze_car_config
from src.envs.maze_car.env import MazeCarEnv
from src.sim import route
from src.sim.components import Transform
from src.sim.observation import OBSERVATION_NAMES
from src.sim.resources import Walls
from src.sim.stage import load_stage

NONE = (False,) * 5


def _env(stage="skill_detour"):
    config = get_maze_car_config()
    config.show_gui = False
    env = MazeCarEnv(config, stage=load_stage(stage))
    env.reset(seed=0)
    return env


def _value(env, name):
    return float(env.last_observation[OBSERVATION_NAMES.index(name)])


def test_in_plain_sight_the_waypoint_is_the_checkpoint():
    env = _env("box")
    sense = route.sense(env.world, env.car)
    assert sense.waypoint == sense.goal
    assert _value(env, "route_sin") == pytest.approx(
        _value(env, "checkpoint_sin"), abs=1e-6
    )


def test_a_wall_in_between_points_the_way_around():
    """skill_detour: the checkpoint sits inside a U whose back wall faces
    the car. The compass points through it; the route goes around.
    """
    env = _env()
    sense = route.sense(env.world, env.car)
    car = env.world.component(env.car, Transform)
    assert sense.goal == (540, 240)
    assert sense.waypoint != sense.goal
    boxes = env.world.resource(Walls).boxes
    assert route._clear((car.x, car.y), sense.waypoint, boxes)  # in sight
    # Around an arm of the U (above 120 or below 360), not through it.
    assert sense.waypoint[1] < 120 or sense.waypoint[1] > 360
    straight = math.dist((car.x, car.y), sense.goal)
    assert sense.distance > straight + 100  # the route is longer
    assert abs(_value(env, "route_sin")) > 0.3  # it points to a side
    assert _value(env, "checkpoint_cos") > 0.99  # the compass: dead ahead


def test_the_stuck_timer_counts_and_resets_with_progress():
    env = _env("box")
    for _ in range(3 * 120):  # 3 s without moving
        env.step(NONE)
    stuck = 3 / route.STUCK_CAP
    assert _value(env, "stuck") == pytest.approx(stuck, abs=0.02)
    from src.drivers.registry import make_driver

    driver = make_driver("heuristic")  # then drive at the checkpoint
    for _ in range(120):
        env.step(driver.act(env.last_observation))
    assert _value(env, "stuck") < 0.05  # it got closer: reset


def test_the_waypoint_is_held_then_refreshed():
    env = _env()
    sense = route.sense(env.world, env.car)
    first = sense.refreshed
    env.step(NONE)
    assert route.sense(env.world, env.car).refreshed == first  # held
    for _ in range(int(route.REFRESH_SECONDS * 120)):
        env.step(NONE)
    assert route.sense(env.world, env.car).refreshed > first  # 2 s on


def test_the_reward_and_the_sense_share_one_route_field():
    env = _env()
    env.step((False, False, True, False, False))
    fields = route.route_fields(env.world).fields
    assert list(fields) == [(540, 240)]  # one field for this checkpoint
