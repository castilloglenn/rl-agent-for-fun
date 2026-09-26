"""Agent history and profiles (roadmap step 5a6)."""

import json

import pytest

import src.experiments.evaluation as evaluation
import src.experiments.training as training
from src.agents.history import (
    HISTORY_FILE,
    build_profile,
    read_history,
    read_profile,
)
from src.agents.model import load_model_spec
from src.agents.store import branch_agent, create_agent
from src.experiments.agents import (
    agent_summary,
    format_agents,
    list_agents,
    sparkline,
)
from src.experiments.evaluation import evaluate_agent
from src.experiments.training import resume_training
from tests.test_evaluation import _tiny_suite
from tests.test_resume import _stop_at
from tests.test_training import _train


def _events(folder):
    return [event["event"] for event in read_history(folder)]


def test_creating_an_agent_starts_its_history(tmp_path):
    folder = create_agent("rookie", load_model_spec("small"), root=tmp_path)
    assert _events(folder) == ["created"]
    profile = read_profile(folder)
    assert profile["id"] == "rookie" and profile["model"]["name"] == "small"
    assert profile["decisions"] == 0 and profile["phases"] == []
    assert (folder / "profile.json").exists()


def test_a_training_phase_is_recorded(tmp_path, monkeypatch):
    monkeypatch.setattr(training, "EPISODE_SUMMARY", 2)
    summary = _train(tmp_path)
    folder = tmp_path / "agents" / "pupil"
    events = _events(folder)
    assert events[:2] == ["created", "phase_started"]
    assert events[-1] == "phase_ended"
    assert events.count("checkpoint_saved") == 2
    assert events.count("episodes") == summary.episodes // 2
    summaries = [e for e in read_history(folder) if e["event"] == "episodes"]
    assert (summaries[0]["first"], summaries[0]["last"]) == (0, 1)

    profile = read_profile(folder)
    assert profile["decisions"] == 512
    (phase,) = profile["phases"]
    assert phase["run"] == summary.folder.name
    assert (phase["start_decisions"], phase["end_decisions"]) == (0, 512)
    assert phase["status"] == "done" and phase["episodes"] == summary.episodes
    assert profile["checkpoints"]["newest"] == "d0000512"


def test_stopping_and_resuming_are_recorded(tmp_path):
    stopped = _train(tmp_path, on_update=_stop_at(2))
    folder = tmp_path / "agents" / "pupil"
    assert read_profile(folder)["phases"][0]["status"] == "stopped"
    resume_training(stopped.folder, agents_root=tmp_path / "agents")
    events = _events(folder)
    assert "phase_resumed" in events and events[-1] == "phase_ended"
    phase = read_profile(folder)["phases"][0]
    assert phase["status"] == "done" and phase["end_decisions"] == 512


def test_a_repeated_event_keeps_the_latest(tmp_path):
    _train(tmp_path)
    folder = tmp_path / "agents" / "pupil"
    ended = [e for e in read_history(folder) if e["event"] == "phase_ended"]
    again = {**ended[-1], "episodes": 999}
    with open(folder / HISTORY_FILE, "a") as file:
        file.write(json.dumps(again) + "\n")
    assert build_profile(folder)["phases"][0]["episodes"] == 999


def test_a_branch_records_where_it_came_from(tmp_path):
    _train(tmp_path)
    root = tmp_path / "agents"
    folder = branch_agent("kid", "pupil", "d0000256", root=root)
    (created,) = read_history(folder)
    assert created["branched_from"] == {
        "agent": "pupil",
        "checkpoint": "d0000256",
    }
    profile = read_profile(folder)
    assert profile["decisions"] == 256
    assert "branched from pupil@d0000256" in agent_summary("kid", root=root)


# Scores and the milestone


def _scored(tmp_path, monkeypatch, heuristic_score):
    suite = _tiny_suite(tmp_path)
    monkeypatch.setattr(
        evaluation,
        "baseline_scores",
        lambda *args: {"heuristic": {"score_mean": heuristic_score}},
    )
    _train(tmp_path)
    folder = tmp_path / "agents" / "pupil"
    evaluate_agent(folder, suite)
    return folder, suite


def test_scores_and_the_best_are_recorded(tmp_path, monkeypatch):
    folder, _ = _scored(tmp_path, monkeypatch, heuristic_score=1e9)
    events = _events(folder)
    assert events.count("scored") == 3  # initial and two checkpoints
    assert "new_best" in events
    assert "milestone" not in events  # nobody beats a score of 1e9
    profile = read_profile(folder)
    assert profile["checkpoints"]["best"] is not None
    assert profile["best"]["suite"] == "box-v1"
    assert profile["milestone"] is None


def test_the_milestone_is_recorded_once(tmp_path, monkeypatch):
    folder, suite = _scored(tmp_path, monkeypatch, heuristic_score=-1)
    assert _events(folder).count("milestone") == 1
    evaluation.evaluate_checkpoint(folder, "initial", suite)  # again
    assert _events(folder).count("milestone") == 1
    milestone = read_profile(folder)["milestone"]
    assert milestone["name"] == "first skilled agent"
    assert milestone["heuristic_score"] == -1
    assert "milestone: first skilled agent" in agent_summary(folder)


def test_the_milestone_needs_survival(tmp_path, monkeypatch):
    monkeypatch.setattr(
        evaluation,
        "best_row",
        lambda rows: {
            **max(rows, key=lambda r: r["score_mean"]),
            "wreck_rate": 0.5,
        },
    )
    folder, _ = _scored(tmp_path, monkeypatch, heuristic_score=-1)
    assert "milestone" not in _events(folder)


# Commands


def test_listing_agents(tmp_path, monkeypatch):
    _scored(tmp_path, monkeypatch, heuristic_score=1e9)
    create_agent("fresh", load_model_spec("medium"), root=tmp_path / "agents")
    profiles = list_agents(tmp_path / "agents")
    assert {p["id"] for p in profiles} == {"pupil", "fresh"}
    table = format_agents(profiles)
    assert "pupil" in table and "medium" in table
    assert "No agents yet" in format_agents([])


def test_the_digest(tmp_path, monkeypatch):
    folder, _ = _scored(tmp_path, monkeypatch, heuristic_score=1e9)
    text = agent_summary(folder)
    assert text.startswith("pupil  (model small: 64x64 tanh)")
    assert "512 decisions, 1 training phase," in text
    assert "trend (3 scored checkpoints)" in text
    assert "milestone: not yet" in text


def test_sparkline():
    assert sparkline([0, 5, 10]) == "▁▅█"
    assert sparkline([3, 3]) == "▁▁"
    with pytest.raises(ValueError):
        sparkline([])
