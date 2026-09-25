"""Drivers: one interface, the canonical actions, and the baselines (4f)."""

import itertools
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pytest  # noqa: E402

from src.config import get_maze_car_config  # noqa: E402
from src.drivers.actions import (  # noqa: E402
    CANONICAL_ACTIONS,
    CANONICAL_NAMES,
    canonical_index,
)
from src.drivers.base import Driver  # noqa: E402
from src.drivers.episode import run_episode  # noqa: E402
from src.drivers.heuristic import CompassDriver  # noqa: E402
from src.drivers.random_driver import RandomDriver  # noqa: E402
from src.drivers.registry import make_driver  # noqa: E402
from src.envs.maze_car.env import MazeCarEnv  # noqa: E402
from src.sim.components import ActionInput  # noqa: E402
from src.sim.factories import _car_spec  # noqa: E402
from src.sim.resources import SimConfig  # noqa: E402
from src.sim.systems.movement import next_speed  # noqa: E402
from src.sim.systems.steering import next_steering  # noqa: E402

ALL_COMBINATIONS = list(itertools.product((False, True), repeat=5))


@pytest.fixture(autouse=True)
def _window():
    """Reading keys needs a window, as in the demo (dummy video here)."""
    import pygame

    pygame.display.init()
    pygame.display.set_mode((1, 1))


def _env():
    config = get_maze_car_config()
    config.show_gui = False
    return MazeCarEnv(config)


# Canonical actions


def test_twelve_distinct_canonical_actions():
    assert len(CANONICAL_ACTIONS) == len(set(CANONICAL_ACTIONS)) == 12
    assert CANONICAL_NAMES[0] == "left+none"
    for index, action in enumerate(CANONICAL_ACTIONS):
        assert canonical_index(action) == index


def test_every_key_combination_behaves_like_its_canonical_action():
    """Decision 012: 32 combinations collapse to 12 without any loss."""
    spec = _car_spec(SimConfig.from_config(get_maze_car_config()))
    speeds = (-spec.max_reverse_speed, -0.3, 0.0, 0.3, spec.max_speed)
    wheels = (-1.0, -0.4, 0.0, 0.4, 1.0)
    for combination in ALL_COMBINATIONS:
        canonical = CANONICAL_ACTIONS[canonical_index(combination)]
        pressed, same = ActionInput(*combination), ActionInput(*canonical)
        for speed in speeds:
            assert next_speed(speed, pressed, spec) == next_speed(
                speed, same, spec
            )
        for wheel in wheels:
            assert next_steering(wheel, pressed, spec) == next_steering(
                wheel, same, spec
            )


# The interface


@pytest.mark.parametrize("name", ["random", "heuristic", "keyboard"])
def test_every_driver_implements_the_interface(name):
    driver = make_driver(name)
    assert isinstance(driver, Driver)
    env = _env()
    observation, _ = env.reset(seed=1)
    driver.reset(1)
    action = driver.act(observation)
    assert len(action) == 5 and all(isinstance(a, bool) for a in action)
    assert driver.record()["type"] in ("baseline", "human")
    assert driver.label


def test_keyboard_driver_is_a_human_record():
    driver = make_driver("keyboard", player="zen")
    assert driver.record() == {
        "type": "human",
        "player": "zen",
        "device": "keyboard",
    }
    assert driver.label == "zen (keyboard)"
    assert driver.act() == (False,) * 5  # no keys pressed headless


def test_unknown_driver_name():
    with pytest.raises(ValueError, match="unknown driver"):
        make_driver("autopilot")


# Baselines


def test_random_driver_decides_every_4_steps_and_repeats_with_its_seed():
    driver = RandomDriver()
    driver.reset(7)
    first = [driver.act(None) for _ in range(40)]
    assert all(first[i] == first[i - i % 4] for i in range(40))
    driver.reset(7)
    assert [driver.act(None) for _ in range(40)] == first
    driver.reset(8)
    assert [driver.act(None) for _ in range(40)] != first


def test_heuristic_is_deterministic():
    env = _env()
    first = run_episode(env, CompassDriver(), seed=3)
    second = run_episode(env, CompassDriver(), seed=3)
    assert first == second


def test_heuristic_beats_random_by_far():
    env = _env()
    seeds = range(200, 205)
    heuristic = [run_episode(env, CompassDriver(), s) for s in seeds]
    random_ = [run_episode(env, RandomDriver(), s) for s in seeds]
    assert sum(r.checkpoints for r in heuristic) >= 5 * len(seeds)
    assert sum(r.score for r in heuristic) > 20 * sum(r.score for r in random_)


def test_run_episode_result():
    env = _env()
    result = run_episode(env, CompassDriver(), seed=5, max_steps=240)
    assert result.steps == 240
    assert result.seed == 5
    assert result.ended_by is None  # cut short, not finished
    assert result.score == result.reward  # default reward profile

    full = run_episode(env, RandomDriver(), seed=5)
    assert full.ended_by in ("time", "wall")
