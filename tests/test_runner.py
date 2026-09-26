"""Experiment runs (roadmap step 4h)."""

import csv
import json

import pytest

from src.config import get_maze_car_config
from src.drivers.heuristic import CompassDriver
from src.drivers.random_driver import RandomDriver
from src.experiments.runner import METRICS_COLUMNS, run_experiment
from src.experiments.runs import best_replay, format_runs, list_runs
from src.replay.format import read_replay
from src.replay.replayer import Replayer
from src.sim.rules import load_rules

SHORT = load_rules("standard").with_round_seconds(3)  # quick episodes


def _run(tmp_path, driver=None, episodes=4, name="test", **kwargs):
    return run_experiment(
        name,
        driver or CompassDriver(),
        get_maze_car_config(),
        episodes=episodes,
        rules=kwargs.pop("rules", SHORT),
        runs_dir=tmp_path,
        **kwargs,
    )


def _metrics(folder):
    with open(folder / "metrics.csv") as file:
        return list(csv.DictReader(file))


def test_run_folder_layout(tmp_path):
    summary = _run(tmp_path)
    folder = summary.folder
    assert folder.parent == tmp_path
    assert folder.name.endswith("_test_seed0")
    for name in ("config.json", "metrics.csv", "summary.json", "notes.md"):
        assert (folder / name).exists()
    assert (folder / "replays").is_dir()


def test_config_records_everything_needed_to_reproduce(tmp_path):
    folder = _run(tmp_path, first_seed=7, reward="time_bonus").folder
    config = json.loads((folder / "config.json").read_text())
    assert config["driver"] == {"type": "baseline", "id": "heuristic"}
    assert (config["episodes"], config["first_seed"]) == (4, 7)
    assert config["stage"]["name"] == "box"
    assert config["rules"] == SHORT.to_dict()
    assert config["reward"]["name"] == "time_bonus"
    assert "car" in config["game_config"]
    assert config["code"] and config["observation_version"] == 1


def test_metrics_one_row_per_episode(tmp_path):
    folder = _run(tmp_path, episodes=5, first_seed=3).folder
    rows = _metrics(folder)
    assert len(rows) == 5
    assert tuple(rows[0]) == METRICS_COLUMNS
    assert [int(row["seed"]) for row in rows] == [3, 4, 5, 6, 7]
    assert all(row["ended_by"] in ("time", "wall") for row in rows)


def test_summary_matches_the_metrics(tmp_path):
    summary = _run(tmp_path, episodes=5)
    scores = [float(row["score"]) for row in _metrics(summary.folder)]
    assert summary.episodes == 5
    assert summary.mean_score == pytest.approx(sum(scores) / 5)
    assert summary.best_score == max(scores)
    assert summary.best_episode == scores.index(max(scores))
    saved = json.loads((summary.folder / "summary.json").read_text())
    assert saved["best_score"] == summary.best_score


def test_only_new_bests_are_saved_and_they_verify(tmp_path):
    summary = _run(tmp_path, driver=RandomDriver(), episodes=6)
    replays = sorted((summary.folder / "replays").glob("*.jsonl.gz"))
    assert 1 <= len(replays) <= 6
    scores = [float(p.name.split("_score")[1].split(".")[0]) for p in replays]
    assert scores == sorted(scores)  # each saved one beat the one before
    for path in replays:
        assert Replayer(read_replay(path)).run().ok, path.name


def test_runs_are_reproducible(tmp_path):
    first = _metrics(_run(tmp_path / "a").folder)
    second = _metrics(_run(tmp_path / "b").folder)
    assert first == second


def test_ctrl_c_keeps_what_was_done(tmp_path):
    class StopAfterOneEpisode(CompassDriver):
        resets = 0

        def reset(self, seed=None):
            self.resets += 1
            if self.resets == 2:
                raise KeyboardInterrupt

    summary = _run(tmp_path, driver=StopAfterOneEpisode(), episodes=5)
    assert summary.interrupted and summary.episodes == 1
    assert len(_metrics(summary.folder)) == 1
    saved = json.loads((summary.folder / "summary.json").read_text())
    assert saved["interrupted"] is True


def test_listing_and_best_replay(tmp_path):
    _run(tmp_path, name="alpha")
    summary = _run(tmp_path, name="beta", driver=RandomDriver())
    rows = list_runs(tmp_path)
    assert {row["folder"].split("_", 2)[2] for row in rows} == {
        "alpha_seed0",
        "beta_seed0",
    }
    table = format_runs(rows)
    assert "heuristic" in table and "random" in table

    path = best_replay(summary.folder)
    assert f"score{summary.best_score:.0f}" in path.name
    assert best_replay(summary.folder.name, runs_dir=tmp_path) == path


def test_listing_with_no_runs(tmp_path):
    assert list_runs(tmp_path) == []
    assert "No runs yet" in format_runs([])
