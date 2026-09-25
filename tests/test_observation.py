"""The agent-facing API: observation and Gymnasium-style steps (3h)."""

import math
import random

import numpy as np
import pytest

from src.config import get_maze_car_config
from src.envs.maze_car.env import MazeCarEnv
from src.sim.components import Checkpoint, Transform
from src.sim.factories import create_game
from src.sim.observation import OBSERVATION_NAMES, observe
from src.sim.resources import Field

GAS = (False, False, True, False, False)


def _env(seconds: float = 60) -> MazeCarEnv:
    config = get_maze_car_config()
    config.show_gui = False
    config.round.seconds = seconds
    return MazeCarEnv(config)


def _value(observation, name):
    return float(observation[OBSERVATION_NAMES.index(name)])


def _place_checkpoint(world, car, dx, dy):
    transform = world.component(car, Transform)
    spot = world.query(Transform, Checkpoint)[0][1][0]
    spot.x, spot.y = transform.x + dx, transform.y + dy


def test_layout_is_14_named_float32_values():
    env = _env()
    observation, info = env.reset()
    assert len(OBSERVATION_NAMES) == 14 == observation.shape[0]
    assert observation.dtype == np.float32
    assert env.observation_version == 1
    assert env.action_names == (
        "turn_left",
        "turn_right",
        "gas",
        "reverse",
        "brake",
    )
    assert info["score"] == 0 and info["eliminated"] is None


def test_start_values():
    world, car = create_game(get_maze_car_config())
    observation = observe(world, car)
    field = world.resource(Field).rect
    diagonal = math.hypot(field.width, field.height)
    transform = world.component(car, Transform)

    front = (field.right - (transform.x + 12)) / diagonal
    assert _value(observation, "ray_front") == pytest.approx(front, rel=1e-6)
    assert _value(observation, "speed") == 0
    assert _value(observation, "steering") == 0
    assert _value(observation, "time_left") == 1


@pytest.mark.parametrize(
    "dx, dy, sin, cos",
    [
        (100, 0, 0, 1),  # ahead
        (0, -100, 1, 0),  # left (screen up, car faces right)
        (-100, 0, 0, -1),  # behind
        (0, 100, -1, 0),  # right
    ],
)
def test_checkpoint_compass(dx, dy, sin, cos):
    world, car = create_game(get_maze_car_config())
    _place_checkpoint(world, car, dx, dy)
    observation = observe(world, car)
    assert _value(observation, "checkpoint_sin") == pytest.approx(sin, abs=1e-6)
    assert _value(observation, "checkpoint_cos") == pytest.approx(cos, abs=1e-6)
    field = world.resource(Field).rect
    distance = 100 / math.hypot(field.width, field.height)
    assert _value(observation, "checkpoint_distance") == pytest.approx(
        distance, rel=1e-6
    )


def test_compass_is_relative_to_the_heading():
    world, car = create_game(get_maze_car_config())
    world.component(car, Transform).angle = 90  # facing up
    _place_checkpoint(world, car, 0, -100)  # up = ahead now
    observation = observe(world, car)
    assert _value(observation, "checkpoint_cos") == pytest.approx(1, abs=1e-6)


def test_values_stay_in_range_during_random_driving():
    env = _env()
    rng = random.Random(3)
    lows = np.full(14, np.inf)
    highs = np.full(14, -np.inf)
    for episode in range(3):
        observation, _ = env.reset(seed=episode)
        for _ in range(2000):
            action = tuple(rng.random() < p for p in (0.3, 0.3, 0.6, 0.2, 0.1))
            observation, _, terminated, truncated, _ = env.step(action)
            lows = np.minimum(lows, observation)
            highs = np.maximum(highs, observation)
            if terminated or truncated:
                break
    assert lows.min() >= -1 and highs.max() <= 1
    assert _value(lows, "speed") >= -1 / 3 - 1e-6


def test_crash_terminates():
    env = _env()
    env.reset()
    terminated = truncated = False
    for _ in range(1000):
        _, _, terminated, truncated, info = env.step(GAS)
        if terminated or truncated:
            break
    assert terminated and not truncated
    assert info["eliminated"] == "wall"


def test_time_up_truncates():
    env = _env(seconds=0.5)
    env.reset()
    results = [env.step((False,) * 5) for _ in range(60)]
    _, _, terminated, truncated, info = results[-1]
    assert truncated and not terminated
    assert not any(r[3] for r in results[:-1])
    assert info["step"] == 60


def test_step_rewards_sum_to_the_score():
    env = _env()
    env.reset()
    total = 0.0
    for _ in range(300):
        _, reward, terminated, truncated, info = env.step(GAS)
        total += reward
        if terminated or truncated:
            break
    assert total == info["score"] == env.score


def test_same_seed_and_actions_give_the_same_observations():
    def run():
        env = _env()
        observations = [env.reset(seed=11)[0]]
        rng = random.Random(5)
        for _ in range(500):
            action = tuple(rng.random() < 0.4 for _ in range(5))
            observations.append(env.step(action)[0])
        return np.stack(observations)

    assert np.array_equal(run(), run())
