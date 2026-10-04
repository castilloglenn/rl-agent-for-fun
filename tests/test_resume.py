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


def _same_start(whole, resumed, updates):
    """The rows up to the stop match the run that never stopped."""
    for name, rows in (("learning.csv", updates), ("metrics.csv", None)):
        drop = {"seconds"}
        mine = _rows(resumed / name, drop)
        theirs = _rows(whole / name, drop)
        if rows is None:  # the rounds finished by the stop's update
            rows = int(_rows(resumed / "learning.csv")[updates - 1]["episodes"])
        assert mine[:rows] == theirs[:rows], name


def _stopped_twice(tmp_path, stop, **kwargs):
    """The same stopped run in two places, each resumed (step 8: a
    resume starts fresh rounds, so it's compared with another resume).
    """
    found = []
    for where in ("a", "b"):
        stopped = _train(tmp_path / where, on_update=_stop_at(stop))
        state = torch.load(stopped.folder / "resume.pt", weights_only=True)
        found.append(
            (
                stopped,
                _resume(tmp_path / where, stopped.folder, **kwargs),
                state,
            )
        )
    return found


def test_a_resume_continues_from_the_last_update(tmp_path, uninterrupted):
    """Step 8: the rounds playing at the stop are dropped and fresh ones
    start (seeds go on from the last round started); from there, resuming
    the same state twice gives the same run.
    """
    (stopped, resumed, state), (_, again, _) = _stopped_twice(tmp_path, 3)
    assert stopped.interrupted and stopped.decisions == 384
    assert not resumed.interrupted and resumed.resumes == 1
    assert resumed.decisions == 512
    assert resumed.checkpoints == ("d0000256", "d0000384", "d0000512")
    _same_start(uninterrupted.folder, resumed.folder, 3)
    _same_run(resumed.folder, again.folder)
    _same_weights(_weights(tmp_path / "a"), _weights(tmp_path / "b"))
    rows = _rows(resumed.folder / "metrics.csv")
    fresh = rows[state["episode"]]  # the first round after the resume
    assert int(fresh["seed"]) == state["rounds"]  # a new seed, not replayed


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
    assert resumed.decisions == 512
    _same_start(uninterrupted.folder, resumed.folder, 2)


def test_resuming_twice(tmp_path):
    found = []
    for where in ("a", "b"):
        stopped = _train(tmp_path / where, on_update=_stop_at(1))
        again = _resume(
            tmp_path / where, stopped.folder, on_update=_stop_at(3)
        )
        assert again.interrupted and again.decisions == 384
        found.append(_resume(tmp_path / where, stopped.folder))
    assert found[0].resumes == 2
    _same_run(found[0].folder, found[1].folder)


def test_a_crashed_run_resumes_too(tmp_path):
    crashed = _train(tmp_path / "a", on_update=_stop_at(2))
    (crashed.folder / "summary.json").unlink()  # as if the process died
    resumed = _resume(tmp_path / "a", crashed.folder)
    stopped = _train(tmp_path / "b", on_update=_stop_at(2))
    _same_run(resumed.folder, _resume(tmp_path / "b", stopped.folder).folder)


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


def test_a_mixed_run_resumes_with_its_maps_even(tmp_path):
    """7d5a, step 8: the maps' counts carry across a stop, so the maps
    stay even; and resuming the same state twice gives the same run.
    """

    def train(where, **kwargs):
        from src.agents.store import create_agent

        root = where / "agents"
        create_agent("pupil", load_model_spec("small"), root=root)
        config = get_maze_car_config()
        config.stage = "basics"
        return training.train_agent(
            "pupil", TINY, config, rules=SHORT, runs_dir=where / "runs",
            agents_root=root, **kwargs,
        )

    resumed = []
    for where in ("a", "b"):
        stopped = train(tmp_path / where, on_update=_stop_at(3))
        resumed.append(_resume(tmp_path / where, stopped.folder))
    _same_run(resumed[0].folder, resumed[1].folder)
    rows = _rows(resumed[0].folder / "metrics.csv")
    counts = [
        sum(r["stage"] == m for r in rows)
        for m in ("box", "pillars", "s_curve", "arena")
    ]
    assert max(counts) - min(counts) <= 2  # a dropped round each, at most
