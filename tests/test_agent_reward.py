"""The agent reward is separate from the game score (decision 010)."""

import pytest

from src.config import get_maze_car_config
from src.envs.maze_car import rewards
from src.envs.maze_car.env import MazeCarEnv
from src.envs.maze_car.rewards import StepEvents, points_gained

GAS = (False, False, True, False, False)


def _env(**kwargs) -> MazeCarEnv:
    config = get_maze_car_config()
    config.show_gui = False
    return MazeCarEnv(config, **kwargs)


def test_default_reward_is_points_gained():
    env = _env()
    assert env.reward_name == "points_gained"
    env.reset()
    for _ in range(200):
        _, reward, terminated, truncated, info = env.step(GAS)
        assert reward == info["points"]
        if terminated or truncated:
            break


def test_step_events():
    events = StepEvents(points=3, checkpoints=0, crashed=False, time_up=False)
    assert points_gained(events) == 3


def test_a_custom_reward_never_changes_the_game_score(monkeypatch):
    def crash_penalty(events: StepEvents) -> float:
        return events.points - (1000 if events.crashed else 0)

    monkeypatch.setitem(
        rewards.REWARD_FUNCTIONS, "crash_penalty", crash_penalty
    )
    penalized, plain = _env(reward="crash_penalty"), _env()
    penalized.reset(seed=1)
    plain.reset(seed=1)

    penalized_total = plain_total = 0.0
    for _ in range(1000):
        _, reward, terminated, truncated, info = penalized.step(GAS)
        penalized_total += reward
        plain_total += plain.step(GAS)[1]
        if terminated or truncated:
            break

    assert info["eliminated"] == "wall"
    assert penalized_total == plain_total - 1000  # penalty exactly once
    assert penalized.score == plain.score  # the game score is unaffected


def test_crash_and_time_up_are_reported_once():
    seen = []

    def record(events: StepEvents) -> float:
        seen.append(events)
        return 0.0

    rewards.REWARD_FUNCTIONS["record"] = record
    try:
        config = get_maze_car_config()
        config.show_gui = False
        config.round.seconds = 0.5
        env = MazeCarEnv(config, reward="record")
        env.reset()
        for _ in range(80):  # past the 60-step round
            env.step((False,) * 5)
    finally:
        del rewards.REWARD_FUNCTIONS["record"]

    assert sum(events.time_up for events in seen) == 1
    assert not any(events.crashed for events in seen)


def test_unknown_reward_name_fails_early():
    with pytest.raises(KeyError):
        _env(reward="no_such_reward")
