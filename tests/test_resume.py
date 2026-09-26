"""Exact resume, and branching agents (roadmap 5a3)."""

import csv
import json
import os

import pytest
import torch

import src.experiments.training as training
from src.agents.model import load_model_spec
from src.agents.store import AgentError, branch_agent, load_agent
from src.config import get_maze_car_config
from src.drivers.heuristic import CompassDriver
from src.experiments.runner import run_experiment
from src.experiments.training import (
    TrainingError,
    last_stopped_run,
    resume_training,
)
from tests.test_training import SHORT, TINY, _train


def _stop_at(update):
    def on_update(report):
        if report.update == update:
            raise KeyboardInterrupt

    return on_update


def _resume(tmp_path, folder, **kwargs):
    return resume_training(folder, agents_root=tmp_path / "agents", **kwargs)


def _rows(path, drop=()):
    with open(path) as file:
        return [
            {k: v for k, v in row.items() if k not in drop}
            for row in csv.DictReader(file)
        ]


def _same_run(first, second):
    """Everything but the wall-clock time matches."""
    assert _rows(first / "learning.csv", drop={"seconds"}) == _rows(
        second / "learning.csv", drop={"seconds"}
    )
    assert _rows(first / "metrics.csv") == _rows(second / "metrics.csv")
    names = [
        sorted(path.name for path in (folder / "replays").iterdir())
        for folder in (first, second)
    ]
    assert names[0] == names[1]


def _weights(root, checkpoint="d0000512"):
    return load_agent("pupil", checkpoint, root=root / "agents").network


def _same_weights(a, b):
    for x, y in zip(a.parameters(), b.parameters()):
        assert torch.equal(x, y)


@pytest.fixture
def uninterrupted(tmp_path):
    return _train(tmp_path / "whole")


def test_resume_matches_an_uninterrupted_run(tmp_path, uninterrupted):
    stopped = _train(tmp_path, on_update=_stop_at(3))  # mid-episode
    assert stopped.interrupted and stopped.decisions == 384
    resumed = _resume(tmp_path, stopped.folder)
    assert not resumed.interrupted and resumed.resumes == 1
    assert resumed.decisions == 512
    _same_run(uninterrupted.folder, resumed.folder)
    _same_weights(_weights(tmp_path / "whole"), _weights(tmp_path))
    assert resumed.checkpoints == ("d0000256", "d0000384", "d0000512")


def test_ctrl_c_mid_update_goes_back_to_the_last_update(
    tmp_path, uninterrupted, monkeypatch
):
    real_update = training.update
    calls = []

    def update_then_stop(*args):
        calls.append(1)
        if len(calls) == 3:  # stopped halfway through learning
            real_update(*args)
            raise KeyboardInterrupt
        return real_update(*args)

    monkeypatch.setattr(training, "update", update_then_stop)
    stopped = _train(tmp_path)
    monkeypatch.setattr(training, "update", real_update)

    assert stopped.interrupted and stopped.decisions == 256
    assert len(_rows(stopped.folder / "learning.csv")) == 2
    kept = load_agent("pupil", root=tmp_path / "agents")
    assert kept.decisions == 256  # the weights after update 2, not 3

    resumed = _resume(tmp_path, stopped.folder)
    _same_run(uninterrupted.folder, resumed.folder)
    _same_weights(_weights(tmp_path / "whole"), _weights(tmp_path))


def test_resuming_twice(tmp_path, uninterrupted):
    stopped = _train(tmp_path, on_update=_stop_at(1))
    again = _resume(tmp_path, stopped.folder, on_update=_stop_at(3))
    assert again.interrupted and again.decisions == 384
    resumed = _resume(tmp_path, stopped.folder)
    assert resumed.resumes == 2
    _same_run(uninterrupted.folder, resumed.folder)
    _same_weights(_weights(tmp_path / "whole"), _weights(tmp_path))


def test_a_crashed_run_resumes_too(tmp_path, uninterrupted):
    stopped = _train(tmp_path, on_update=_stop_at(2))
    (stopped.folder / "summary.json").unlink()  # as if the process died
    resumed = _resume(tmp_path, stopped.folder)
    _same_run(uninterrupted.folder, resumed.folder)


def test_what_cant_be_resumed(tmp_path):
    finished = _train(tmp_path)
    with pytest.raises(TrainingError, match="already finished"):
        _resume(tmp_path, finished.folder)

    baseline = run_experiment(
        "baseline",
        CompassDriver(),
        get_maze_car_config(),
        episodes=1,
        rules=SHORT,
        runs_dir=tmp_path / "runs",
    )
    with pytest.raises(TrainingError, match="not a training run"):
        _resume(tmp_path, baseline.folder)

    old = _train(tmp_path, on_update=_stop_at(2))
    (old.folder / "resume.pt").unlink()  # as if trained before 5a3
    with pytest.raises(TrainingError, match="no resume state"):
        _resume(tmp_path, old.folder)

    with pytest.raises(TrainingError, match="no run at"):
        _resume(tmp_path, tmp_path / "nowhere")


def test_resume_is_refused_after_another_run_trained_the_agent(tmp_path):
    stopped = _train(tmp_path, on_update=_stop_at(2))
    _train(tmp_path)  # a new phase from the stopped run's weights
    with pytest.raises(TrainingError, match="newer checkpoint"):
        _resume(tmp_path, stopped.folder)


def test_a_run_still_training_is_not_resumed(tmp_path):
    stopped = _train(tmp_path, on_update=_stop_at(2))
    (stopped.folder / "training.lock").write_text(str(os.getpid()))
    with pytest.raises(TrainingError, match="still training"):
        _resume(tmp_path, stopped.folder)
    (stopped.folder / "training.lock").write_text("999999999")  # dead
    assert _resume(tmp_path, stopped.folder).decisions == 512


def test_last_stopped_run(tmp_path):
    with pytest.raises(TrainingError, match="no stopped training run"):
        last_stopped_run(tmp_path / "runs")
    stopped = _train(tmp_path, on_update=_stop_at(2))
    assert last_stopped_run(tmp_path / "runs") == stopped.folder
    _resume(tmp_path, stopped.folder)
    with pytest.raises(TrainingError):
        last_stopped_run(tmp_path / "runs")  # it finished


# Branching


def test_branching_an_agent(tmp_path):
    _train(tmp_path)
    root = tmp_path / "agents"
    branch_agent("kid", "pupil", "d0000256", root=root)
    kid = load_agent("kid", root=root)
    parent = load_agent("pupil", "d0000256", root=root)
    assert kid.checkpoint == "initial" and kid.decisions == 256
    assert kid.branched_from == {"agent": "pupil", "checkpoint": "d0000256"}
    assert kid.spec == parent.spec
    _same_weights(kid.network, parent.network)

    summary = _train(tmp_path, agent="kid")
    assert summary.checkpoints == ("d0000512", "d0000768")  # count goes on
    config = json.loads((summary.folder / "config.json").read_text())
    assert config["agent"]["branched_from"]["agent"] == "pupil"


def test_branching_needs_a_new_id_and_a_real_checkpoint(tmp_path):
    _train(tmp_path)
    root = tmp_path / "agents"
    with pytest.raises(AgentError, match="already exists"):
        branch_agent("pupil", "pupil", root=root)
    with pytest.raises(AgentError, match="no checkpoint 'd9999k'"):
        branch_agent("kid", "pupil", "d9999k", root=root)
    with pytest.raises(AgentError, match="no agent at"):
        branch_agent("kid", "ghost", root=root)
    assert not (root / "kid").exists()


def test_the_model_file_is_unchanged_by_training(tmp_path):
    _train(tmp_path)
    model = json.loads((tmp_path / "agents/pupil/model.json").read_text())
    assert model == load_model_spec("small").to_dict()
    assert TINY.total_decisions == 512  # the tests above assume it
