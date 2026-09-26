"""Imitation agents: datasets from recordings, and cloning (step 5b)."""

import json

import numpy as np
import pytest

from src.agents.history import read_history, read_profile
from src.agents.store import load_agent
from src.agents.trainer import (
    ImitationSpec,
    TrainerError,
    load_imitation_spec,
    load_trainer_spec,
)
from src.config import get_maze_car_config
from src.drivers.actions import CANONICAL_NAMES
from src.drivers.heuristic import CompassDriver
from src.envs.maze_car.env import MazeCarEnv
from src.experiments.agents import agent_summary
from src.experiments.datasets import (
    DatasetError,
    DatasetSpec,
    build_dataset,
    format_dataset,
    load_dataset_spec,
)
from src.experiments.imitation import _returns, _split, imitate
from src.replay.format import read_replay, write_replay
from src.replay.recorder import human_driver
from src.replay.recordings import LibraryRecorder, RecordingLibrary
from tests.test_training import SHORT, TINY, TrainerSpec, _train

IDLE = (False,) * 5
GAS = (False, False, True, False, False)
LEFT_GAS = (True, False, True, False, False)
QUICK = ImitationSpec.from_dict(
    {**load_imitation_spec("imitate").to_dict(), "epochs": 3}
)
QUICK = ImitationSpec.from_dict({**QUICK.to_dict(), "evaluate": False})


def _library(tmp_path, player="Bot"):
    return RecordingLibrary(player, root=tmp_path / "recordings")


def _env(tmp_path, player="Bot"):
    config = get_maze_car_config()
    config.show_gui = False
    library = _library(tmp_path, player)
    recorder = LibraryRecorder({"1": human_driver(player)}, library)
    return MazeCarEnv(config, rules=SHORT, recorder=recorder), library


def _record_script(tmp_path, script, seed=1):
    """One recorded round of scripted actions: [(action, steps), ...]."""
    env, library = _env(tmp_path)
    env.reset(seed=seed)
    for action, steps in script:
        for _ in range(steps):
            env.step_world(action)
    env.finish_recording()
    return library


def _record_heuristic(tmp_path, rounds=4):
    env, library = _env(tmp_path)
    driver = CompassDriver()
    for seed in range(rounds):
        observation, _ = env.reset(seed=seed)
        driver.reset(seed)
        done = False
        while not done:
            observation, _, a, b, _ = env.step(driver.act(observation))
            done = a or b
    env.reset(seed=99)  # saves nothing new: the last round already ended
    return library


def _spec(**changes):
    return DatasetSpec(**{"name": "bot", "player": "Bot", **changes})


# Dataset files


def test_the_dataset_file_loads():
    spec = load_dataset_spec("mine")
    assert (spec.player, spec.include) == ("You", "all")


def test_invalid_datasets_are_rejected():
    with pytest.raises(DatasetError, match="include"):
        DatasetSpec.from_dict(
            {"format": 1, "name": "x", "player": "p", "include": "best"}
        )
    with pytest.raises(DatasetError, match="no dataset file"):
        load_dataset_spec("nope")


# Samples


def test_samples_skip_the_idle_start_and_take_the_most_pressed(tmp_path):
    # 10 idle steps (reaction time), then 3 steps of gas + 1 of left+gas
    # per decision, 30 times: every decision's label is "none+gas".
    script = [(IDLE, 12)] + [(GAS, 3), (LEFT_GAS, 1)] * 30
    _record_script(tmp_path, script)
    dataset = build_dataset(_spec(), 4, tmp_path / "recordings")
    (round_,) = dataset.rounds
    assert len(round_.actions) == 30  # the 3 idle decisions are left out
    assert {CANONICAL_NAMES[a] for a in round_.actions} == {"none+gas"}
    assert round_.observations.shape == (30, 15)
    assert round_.observations[0][8] == 0  # stopped, about to press gas


def test_rounds_without_keys_or_that_dont_verify_are_skipped(tmp_path):
    _record_script(tmp_path, [(IDLE, 200)], seed=1)
    library = _record_script(tmp_path, [(GAS, 200)], seed=2)
    path = next(p for p in library.recent() if "seed2" in p.name)
    replay = read_replay(path)
    replay.end["scores"]["1"] += 1  # as if the physics had changed
    write_replay(replay, path)
    dataset = build_dataset(_spec(), 4, tmp_path / "recordings")
    assert dataset.rounds == []
    reasons = sorted(why for _, why in dataset.skipped)
    assert reasons[0].startswith("doesn't verify")
    assert reasons[1] == "no keys pressed"
    assert "Record rounds first" in format_dataset(dataset)


def test_min_score_and_kept_only(tmp_path):
    library = _record_heuristic(tmp_path, rounds=3)
    library.keep(library.recent()[0])
    root = tmp_path / "recordings"
    assert len(build_dataset(_spec(), 4, root).rounds) == 3
    assert len(build_dataset(_spec(include="kept"), 4, root).rounds) == 1
    high = build_dataset(_spec(min_score=1e9), 4, root)
    assert high.rounds == [] and len(high.skipped) == 3


def test_held_out_rounds_are_whole_and_reproducible(tmp_path):
    _record_heuristic(tmp_path, rounds=5)
    rounds = build_dataset(_spec(), 4, tmp_path / "recordings").rounds
    train, held = _split(rounds, QUICK)
    assert len(held) == 1 and len(train) == 4  # 20 % of 5 rounds
    assert {r.path for r in train}.isdisjoint(r.path for r in held)
    assert _split(rounds, QUICK)[1][0].path == held[0].path


def test_value_targets_are_discounted_and_scaled():
    spec = ImitationSpec.from_dict({**QUICK.to_dict(), "gamma": 0.5})
    returns = _returns(np.array([100.0, 0.0, 100.0]), spec)
    assert returns.tolist() == pytest.approx([1.25, 0.5, 1.0])


# Cloning


def test_cloning_the_heuristic(tmp_path):
    _record_heuristic(tmp_path, rounds=4)
    summary = imitate(
        "clone",
        QUICK,
        _spec(),
        get_maze_car_config(),
        runs_dir=tmp_path / "runs",
        agents_root=tmp_path / "agents",
        recordings_root=tmp_path / "recordings",
    )
    assert summary.checkpoint == "clone-e3"
    assert summary.rounds == 4 and summary.held_out_rounds == 1
    assert summary.train_accuracy > 0.25  # 12 classes: chance is ~8 %
    config = json.loads((summary.folder / "config.json").read_text())
    assert config["kind"] == "imitation"
    assert sum(r["held_out"] for r in config["recordings"]) == 1

    folder = tmp_path / "agents" / "clone"
    agent = load_agent(folder)
    assert agent.checkpoint == "clone-e3" and agent.decisions == 0
    (phase,) = read_profile(folder)["phases"]
    assert phase["kind"] == "imitation"
    assert phase["dataset"]["player"] == "Bot"
    assert "cloned from Bot (4 rounds" in agent_summary(folder)


def test_cloning_is_reproducible(tmp_path):
    _record_heuristic(tmp_path, rounds=3)
    results = []
    for name in ("a", "b"):
        summary = imitate(
            name,
            QUICK,
            _spec(),
            get_maze_car_config(),
            runs_dir=tmp_path / "runs",
            agents_root=tmp_path / "agents",
            recordings_root=tmp_path / "recordings",
        )
        results.append(summary.train_accuracy)
    assert results[0] == results[1]


def test_rl_continues_from_the_clone(tmp_path):
    _record_heuristic(tmp_path, rounds=2)
    imitate(
        "pupil",
        QUICK,
        _spec(),
        get_maze_car_config(),
        runs_dir=tmp_path / "runs",
        agents_root=tmp_path / "agents",
        recordings_root=tmp_path / "recordings",
    )
    summary = _train(tmp_path)  # the tiny RL trainer, on agent "pupil"
    config = json.loads((summary.folder / "config.json").read_text())
    assert config["agent"]["start_checkpoint"] == "clone-e3"
    kinds = [
        e.get("kind", "rl")
        for e in read_history(tmp_path / "agents" / "pupil")
        if e["event"] == "phase_started"
    ]
    assert kinds == ["imitation", "rl"]


def test_no_usable_rounds_is_a_clear_error(tmp_path):
    with pytest.raises(DatasetError, match="no usable rounds"):
        imitate(
            "clone",
            QUICK,
            _spec(),
            get_maze_car_config(),
            runs_dir=tmp_path / "runs",
            agents_root=tmp_path / "agents",
            recordings_root=tmp_path / "recordings",
        )


# Trainer files


def test_trainer_kinds_dont_mix():
    with pytest.raises(TrainerError, match="imitation trainer"):
        load_trainer_spec("imitate")
    with pytest.raises(TrainerError, match="unknown trainer keys"):
        ImitationSpec.from_dict(load_trainer_spec("default").to_dict())
    assert TrainerSpec and TINY  # the RL trainer stays PPO


@pytest.mark.parametrize(
    "change, message",
    [
        ({"algorithm": "ppo"}, "algorithm imitation"),
        ({"validation": 1.0}, "validation"),
        ({"epochs": 0}, "epochs"),
        ({"value": "yes"}, "value"),
    ],
)
def test_invalid_imitation_trainers(change, message):
    with pytest.raises(TrainerError, match=message):
        ImitationSpec.from_dict({**QUICK.to_dict(), **change})
