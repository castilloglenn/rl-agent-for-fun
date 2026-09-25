"""Reward profiles: the agent reward, separate from the game score
(decisions 010 and 011).
"""

import json

import pytest

from src.config import get_maze_car_config
from src.envs.maze_car.env import MazeCarEnv
from src.envs.maze_car.rewards import (
    PROFILES_DIR,
    TERMS,
    RewardProfile,
    RewardProfileError,
    StepEvents,
    load_reward_profile,
)

GAS = (False, False, True, False, False)
LEFT = (True, False, False, False, False)
NONE = (False,) * 5


def _env(seconds: float = 60, **kwargs) -> MazeCarEnv:
    config = get_maze_car_config()
    config.show_gui = False
    config.round.seconds = seconds
    return MazeCarEnv(config, **kwargs)


def _profile(**terms) -> RewardProfile:
    return RewardProfile.from_dict(
        {"format": 1, "name": "test", "terms": terms}
    )


def _events(**overrides) -> StepEvents:
    values = dict(
        points=0.0,
        checkpoints=0,
        crashed=False,
        time_up=False,
        distance=0.0,
        speed=0.0,
        steering_change=0.0,
        closest_wall=0.0,
    )
    return StepEvents(**{**values, **overrides})


# Profiles


def test_default_profile_is_points_only():
    profile = load_reward_profile("default")
    assert profile.name == "default"
    assert dict(profile.terms) == {"points": 1.0}
    assert profile(_events(points=3)) == 3


def test_round_trip_matches_the_file():
    data = json.loads((PROFILES_DIR / "default.json").read_text())
    profile = load_reward_profile("default")
    assert profile.to_dict() == data
    assert RewardProfile.from_dict(profile.to_dict()) == profile


def test_load_by_path():
    path = str(PROFILES_DIR / "default.json")
    assert load_reward_profile(path) == load_reward_profile("default")


@pytest.mark.parametrize(
    "term, events, expected",
    [
        ("points", _events(points=7), 7),
        ("checkpoints", _events(checkpoints=1), 1),
        ("crash", _events(crashed=True), 1),
        ("time_up", _events(time_up=True), 1),
        ("per_step", _events(), 1),
        ("distance", _events(distance=2.5), 2.5),
        ("speed", _events(speed=-0.25), -0.25),
        ("steering_change", _events(steering_change=0.1), 0.1),
        ("closest_wall", _events(closest_wall=0.3), 0.3),
    ],
)
def test_each_term(term, events, expected):
    assert TERMS[term](events) == pytest.approx(expected)


def test_reward_is_the_weighted_sum():
    profile = _profile(points=1.0, crash=-200, per_step=-0.01)
    assert profile(_events(points=3)) == pytest.approx(2.99)
    assert profile(_events(crashed=True)) == pytest.approx(-200.01)


@pytest.mark.parametrize(
    "data, message",
    [
        ({"format": 2, "name": "x", "terms": {"points": 1}}, "format"),
        ({"format": 1, "name": "x", "terms": {}}, "needs terms"),
        ({"format": 1, "name": "x", "terms": {"speeed": 1}}, "unknown"),
        ({"format": 1, "name": "x", "terms": {"points": "1"}}, "number"),
        ({"format": 1, "name": "x", "terms": {"points": True}}, "number"),
    ],
)
def test_invalid_profiles_are_rejected(data, message):
    with pytest.raises(RewardProfileError, match=message):
        RewardProfile.from_dict(data)


# Env


def test_env_uses_the_default_profile():
    env = _env()
    assert env.reward_profile.name == "default"
    env.reset()
    for _ in range(200):
        _, reward, terminated, truncated, info = env.step(GAS)
        assert reward == info["points"]
        if terminated or truncated:
            break


def test_a_crash_penalty_never_changes_the_game_score():
    penalized = _env(reward=_profile(points=1.0, crash=-1000))
    plain = _env()
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
    assert penalized_total == plain_total - 1000  # the penalty, once
    assert penalized.score == plain.score  # the game score is untouched


def test_time_up_is_rewarded_once_and_nothing_after_game_over():
    env = _env(seconds=0.5, reward=_profile(time_up=1.0, per_step=0.001))
    env.reset()
    rewards = [env.step(NONE)[1] for _ in range(80)]  # the round is 60 steps
    assert sum(rewards) == pytest.approx(1 + 60 * 0.001)
    assert rewards[60:] == [0.0] * 20


def test_steering_change_adds_up_the_wheel_travel():
    env = _env(reward=_profile(steering_change=1.0))
    env.reset()
    total = sum(env.step(LEFT)[1] for _ in range(40))  # to full left lock
    total += sum(env.step(NONE)[1] for _ in range(40))  # back to center
    assert total == pytest.approx(2.0)


def test_distance_and_speed_terms_while_driving():
    env = _env(reward=_profile(distance=1.0))
    env.reset()
    for _ in range(120):
        _, reward, *_ = env.step(GAS)
        assert reward >= 0
    assert reward > 0

    reversing = _env(reward=_profile(distance=1.0, speed=1.0))
    reversing.reset()
    for _ in range(60):
        _, reward, *_ = reversing.step((False, False, False, True, False))
    assert reward < 0  # no forward distance, negative speed


def test_closest_wall_term_is_a_fraction():
    env = _env(reward=_profile(closest_wall=1.0))
    env.reset()
    for _ in range(600):  # about 630 px to the wall
        _, reward, terminated, truncated, _ = env.step(GAS)
        assert 0 <= reward <= 1
        if terminated:
            break
    assert terminated
    assert reward == pytest.approx(0, abs=1e-6)  # touching the wall


def test_unknown_profile_name_fails_early():
    with pytest.raises(FileNotFoundError):
        _env(reward="no_such_profile")
