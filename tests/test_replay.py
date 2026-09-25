"""Replays: record, save, load, re-simulate, verify (roadmap step 4d)."""

import json
import random

import pytest

from src.config import game_config, get_maze_car_config
from src.envs.maze_car.env import MazeCarEnv
from src.envs.maze_car.rewards import RewardProfile
from src.replay.format import (
    Replay,
    ReplayError,
    read_replay,
    to_current_actions,
    write_replay,
)
from src.replay.recorder import ReplayRecorder, human_driver
from src.replay.replayer import Replayer
from src.sim.components import Score, Transform
from src.sim.stage import load_stage


def _config(seconds: float = 60):
    config = get_maze_car_config()
    config.show_gui = False
    config.round.seconds = seconds
    return config


def _held_inputs(seed: int, steps: int):
    """Human-like input: each key combination held for a while."""
    rng = random.Random(seed)
    actions = []
    while len(actions) < steps:
        action = (
            rng.random() < 0.3,
            rng.random() < 0.3,
            rng.random() < 0.7,
            rng.random() < 0.1,
            rng.random() < 0.1,
        )
        actions += [action] * rng.randint(10, 90)
    return actions[:steps]


def _record(seed=3, steps=2000, seconds=60, reward=None, finish=True):
    recorder = ReplayRecorder({"1": human_driver("zen")})
    env = MazeCarEnv(
        _config(seconds), reward=reward or "default", recorder=recorder
    )
    env.reset(seed=seed)
    for action in _held_inputs(seed, steps):
        env.step_world(action)
        if env.is_game_over:
            break
    if finish:
        env.finish_recording()
    return env, recorder.replay


def test_header_has_everything_needed_to_rebuild_the_game():
    env, replay = _record(steps=10)
    header = replay.header
    assert header["format"] == 1
    assert header["stage"] == load_stage("box").to_dict()
    assert header["seed"] == 3
    assert header["config"] == game_config(env.config)
    assert header["reward"] == env.reward_profile.to_dict()
    assert header["slots"] == {
        "1": {"type": "human", "player": "zen", "device": "keyboard"}
    }
    assert header["action_names"] == list(env.action_names)
    assert header["observation_version"] == 1
    assert header["steps_per_second"] == 120
    assert header["code"]


def test_only_action_changes_are_stored():
    env = MazeCarEnv(
        _config(), recorder=ReplayRecorder({"1": human_driver("zen")})
    )
    env.reset()
    for _ in range(100):
        env.step_world((False, False, True, False, False))
    for _ in range(50):
        env.step_world((True, False, True, False, False))
    changes = env.recorder.replay.changes
    assert [step for step, _ in changes] == [0, 100]


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_replay_reproduces_the_game_exactly(seed, tmp_path):
    env, replay = _record(seed=seed, steps=3000)
    path = write_replay(replay, tmp_path / "game.jsonl")

    replayer = Replayer(read_replay(path))
    verification = replayer.run()

    assert verification.ok, verification.problems
    original = env.world.component(env.car, Transform)
    rerun = replayer.env.world.component(replayer.env.car, Transform)
    assert (rerun.x, rerun.y, rerun.angle) == (
        original.x,
        original.y,
        original.angle,
    )


def test_a_finished_round_ends_with_its_reason(tmp_path):
    env, replay = _record(seed=4, steps=500, seconds=2)
    assert env.is_game_over
    assert replay.end["reason"] in ("time", "all_out")
    assert Replayer(replay).run().ok


def test_a_crash_round_verifies(tmp_path):
    recorder = ReplayRecorder({"1": human_driver("zen")})
    env = MazeCarEnv(_config(), recorder=recorder)
    env.reset(seed=0)
    while not env.is_game_over:
        env.step_world((False, False, True, False, False))
    assert recorder.replay.end["reason"] == "all_out"
    assert Replayer(recorder.replay).run().ok


def _safe_drive(recorder):
    """Gentle driving that can't reach a wall: gas, then brake to a stop."""
    env = MazeCarEnv(_config(), recorder=recorder)
    env.reset(seed=0)
    for action in [(False, False, True, False, False)] * 90 + [
        (True, False, False, False, True)
    ] * 610:
        env.step_world(action)
    return env


def test_a_stopped_recording_verifies_up_to_where_it_stopped():
    recorder = ReplayRecorder({"1": human_driver("zen")})
    env = _safe_drive(recorder)
    env.finish_recording()
    replay = recorder.replay
    assert replay.end["reason"] == "stopped"
    assert replay.end["step"] == 700
    assert Replayer(replay).run().ok


def test_tampered_replay_is_flagged(tmp_path):
    _, replay = _record(steps=1500)
    path = write_replay(replay, tmp_path / "game.jsonl")
    lines = path.read_text().splitlines()
    end = json.loads(lines[-1])
    end["end"]["scores"]["1"] += 1  # as if the simulation had changed
    lines[-1] = json.dumps(end)
    path.write_text("\n".join(lines) + "\n")

    verification = Replayer(read_replay(path)).run()
    assert not verification.ok
    assert "score" in verification.problems[0]


def test_changed_inputs_are_flagged():
    recorder = ReplayRecorder({"1": human_driver("zen")})
    _safe_drive(recorder).finish_recording()
    replay = recorder.replay
    assert Replayer(replay).run().ok
    # Change the first input from gas to nothing: the car never moves.
    replay.changes[0] = (0, {"1": [False] * 5})
    verification = Replayer(replay).run()
    assert not verification.ok
    assert "score" in verification.problems[0]


def test_gzipped_replays(tmp_path):
    _, replay = _record(steps=1000)
    path = write_replay(replay, tmp_path / "game.jsonl.gz")
    assert read_replay(path) == replay
    assert Replayer(read_replay(path)).run().ok


def test_replay_uses_its_recorded_settings_not_the_current_ones():
    """A custom reward profile and a changed game config come from the
    file, so the replay still verifies with today's defaults."""
    profile = RewardProfile.from_dict(
        {
            "format": 1,
            "name": "test",
            "terms": {"points": 1.0, "per_step": -0.01},
        }
    )
    recorder = ReplayRecorder({"1": human_driver("zen")})
    config = _config()
    config.car.max_speed = 250.0
    env = MazeCarEnv(config, reward=profile, recorder=recorder)
    env.reset(seed=8)
    for action in _held_inputs(8, 1200):
        env.step_world(action)
    env.finish_recording()

    replayer = Replayer(recorder.replay)
    assert replayer.env.config.car.max_speed == 250.0
    assert replayer.env.reward_profile == profile
    assert replayer.run().ok


def test_a_full_human_like_round_is_small(tmp_path):
    _, replay = _record(seed=5, steps=7200)
    size = write_replay(replay, tmp_path / "game.jsonl").stat().st_size
    assert size < 40_000  # header + a few hundred changes


def test_actions_are_read_by_name():
    stored_names = ["gas", "turn_left", "boost"]  # a future replay
    current = ("turn_left", "turn_right", "gas", "reverse", "brake")
    assert to_current_actions([True, True, True], stored_names, current) == (
        True,
        False,
        True,
        False,
        False,
    )


def test_wrong_format_is_rejected(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text(json.dumps({"format": 99}) + "\n")
    with pytest.raises(ReplayError, match="unsupported replay format"):
        read_replay(path)


def test_expanding_changes_per_step():
    replay = Replay(
        header={},
        changes=[(0, {"1": [1]}), (3, {"1": [2]})],
    )
    assert replay.actions_by_step(5) == [{"1": [1]}] * 3 + [{"1": [2]}] * 2


def test_recording_restarts_on_reset():
    recorder = ReplayRecorder({"1": human_driver("zen")})
    env = MazeCarEnv(_config(), recorder=recorder)
    env.reset(seed=1)
    for _ in range(50):
        env.step_world((False, False, True, False, False))
    env.reset(seed=2)
    assert recorder.replay.header["seed"] == 2
    assert recorder.replay.changes == []
    assert recorder.replay.end is None


def test_final_scores_match_the_game():
    env, replay = _record(seed=6, steps=3000)
    assert replay.end["scores"]["1"] == env.world.component(
        env.car, Score
    ).total
    assert replay.end["rewards"]["1"] == env.round_reward


def test_numpy_bool_actions_can_be_saved(tmp_path):
    """Agents compute actions with numpy; the file must still be JSON."""
    import numpy as np

    recorder = ReplayRecorder({"1": human_driver("zen")})
    env = MazeCarEnv(_config(), recorder=recorder)
    env.reset()
    action = tuple(np.array([0, 0, 1, 0, 0]) > 0)  # numpy bools
    for _ in range(30):
        env.step_world(action)
    env.finish_recording()
    path = write_replay(recorder.replay, tmp_path / "game.jsonl")
    assert Replayer(read_replay(path)).run().ok
