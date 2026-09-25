"""Reward profiles: the agent reward, separate from the game score
(decisions 010 and 011).
"""

import json

import pytest

from src.config import get_maze_car_config
from src.envs.maze_car.env import MazeCarEnv
from src.sim.components import Score
from src.sim.rules import load_rules
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
    rules = load_rules("standard")
    if seconds != 60:
        rules = rules.with_round_seconds(seconds)
    return MazeCarEnv(config, rules=rules, **kwargs)


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
        ("distance_points", _events(points=107, distance_points=7), 7),
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


def test_description_is_optional():
    assert _profile(points=1.0).description == ""
    assert load_reward_profile("default").description.startswith("Game points")


def test_demo_path_tracks_the_reward_too():
    """step_world (the human demo) scores steps with the profile as well."""
    env = _env(reward=_profile(points=1.0, per_step=-0.01))
    env.reset()
    points = sum(env.step_world(GAS)[0] for _ in range(100))
    status = env.reward_status()
    assert status.profile == "test"
    assert status.total == pytest.approx(points - 100 * 0.01)
    assert status.last == pytest.approx(env.last_reward)

    env.reset()
    assert env.reward_status().total == 0


def test_step_returns_the_same_reward_the_hud_shows():
    env = _env(reward=_profile(points=2.0, per_step=-0.5))
    env.reset()
    total = 0.0
    for _ in range(150):
        _, reward, *_ = env.step(GAS)
        total += reward
        assert reward == env.reward_status().last
    assert total == pytest.approx(env.reward_status().total)


# Parameterized terms and the checkpoint time bonus


def test_terms_can_be_a_weight_or_a_weight_with_parameters():
    profile = RewardProfile.from_dict(
        {
            "format": 1,
            "name": "fast",
            "terms": {
                "points": 1.0,
                "checkpoint_speed": {"weight": 100, "window": 4},
            },
        }
    )
    assert dict(profile.terms) == {"points": 1.0, "checkpoint_speed": 100.0}
    assert dict(profile.params["checkpoint_speed"]) == {"window": 4.0}
    assert RewardProfile.from_dict(profile.to_dict()) == profile
    assert profile.to_dict()["terms"]["checkpoint_speed"] == {
        "weight": 100.0,
        "window": 4.0,
    }


@pytest.mark.parametrize(
    "spec, message",
    [
        ({"weight": 1, "speed_limit": 3}, "unknown parameter"),
        ({"window": 10}, "weight of"),
        ({"weight": "1", "window": 10}, "weight of"),
        ({"weight": 1, "window": 0}, "must be positive"),
        ({"weight": 1, "window": -5}, "must be positive"),
    ],
)
def test_invalid_term_parameters(spec, message):
    data = {"format": 1, "name": "x", "terms": {"checkpoint_speed": spec}}
    with pytest.raises(RewardProfileError, match=message):
        RewardProfile.from_dict(data)


def test_parameters_on_a_term_without_any():
    spec = {"weight": 1, "k": 2}
    data = {"format": 1, "name": "x", "terms": {"points": spec}}
    with pytest.raises(RewardProfileError, match="known: none"):
        RewardProfile.from_dict(data)


@pytest.mark.parametrize(
    "seconds, expected",
    [((1.0,), 0.9), ((5.0,), 0.5), ((10.0,), 0.0), ((12.0,), 0.0), ((), 0.0)],
)
def test_checkpoint_speed_pays_more_for_faster_pickups(seconds, expected):
    events = _events(checkpoint_seconds=seconds, checkpoints=len(seconds))
    assert TERMS["checkpoint_speed"](events) == pytest.approx(expected)


def test_checkpoint_speed_window_is_tunable():
    events = _events(checkpoint_seconds=(1.0,), checkpoints=1)
    assert TERMS["checkpoint_speed"](events, {"window": 4}) == pytest.approx(
        0.75
    )


def _collect_one_checkpoint(env, distance_ahead):
    """Drives straight at a checkpoint placed ahead, and returns the reward
    of the step that reached it and how many steps that took.
    """
    from src.sim.components import Checkpoint, Transform

    env.reset(seed=1)
    car = env.world.component(env.car, Transform)
    spot = env.world.query(Transform, Checkpoint)[0][1][0]
    spot.x, spot.y = car.x + distance_ahead, car.y
    for steps in range(1, 600):
        _, reward, *_ = env.step(GAS)
        if env.world.component(env.car, Score).checkpoints:
            return reward, steps
    raise AssertionError("never reached the checkpoint")


def test_faster_checkpoints_earn_a_bigger_bonus_and_the_score_stays_put():
    speedy = _profile(checkpoint_speed=100.0)  # default window: 10 s
    near_reward, near_steps = _collect_one_checkpoint(_env(reward=speedy), 60)
    far_reward, far_steps = _collect_one_checkpoint(_env(reward=speedy), 300)

    assert near_steps < far_steps
    assert near_reward > far_reward > 0
    assert near_reward == pytest.approx(100 * (1 - near_steps / 120 / 10))

    plain = _env()
    _collect_one_checkpoint(plain, 60)
    game = _env(reward=speedy)
    _collect_one_checkpoint(game, 60)
    assert game.score == plain.score  # the game score is untouched


def test_age_restarts_when_the_checkpoint_respawns():
    from src.sim.components import Checkpoint, SpawnedAt

    env = _env(reward=_profile(checkpoint_speed=100.0))
    _, steps = _collect_one_checkpoint(env, 60)
    checkpoint = env.world.query(Checkpoint)[0][0]
    assert env.world.component(checkpoint, SpawnedAt).step == steps


def test_every_profile_file_loads_and_round_trips():
    for path in PROFILES_DIR.glob("*.json"):
        profile = load_reward_profile(str(path))
        assert profile.to_dict() == json.loads(path.read_text()), path.name


def test_time_bonus_profile_pays_nothing_for_a_slow_checkpoint():
    """The checkpoint's worth comes only from the speed bonus: the game's
    own +100 isn't part of this profile (regression: it used to be).
    """
    from src.sim.components import Checkpoint, Transform

    rewards = []
    for wait_steps in (0, 12 * 120):
        env = _env(reward="time_bonus")
        env.reset(seed=1)
        car = env.world.component(env.car, Transform)
        spot = env.world.query(Transform, Checkpoint)[0][1][0]
        spot.x, spot.y = car.x + 60, car.y
        for _ in range(wait_steps):
            env.step(NONE)
        score = env.world.component(env.car, Score)
        while not score.checkpoints:
            _, reward, *_ = env.step(GAS)
        rewards.append(reward)
        assert score.last_step == 100  # the game still pays its +100

    fast, slow = rewards
    assert fast > 90
    assert slow == pytest.approx(0, abs=1e-9)
