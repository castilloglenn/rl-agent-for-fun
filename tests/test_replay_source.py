"""Where a replay comes from (the SOURCE card), and a mixed run's best
replay per map (7d5). Runs here are in tmp_path.
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

from src.agents.model import load_model_spec  # noqa: E402
from src.agents.store import create_agent  # noqa: E402
from src.config import get_maze_car_config  # noqa: E402
from src.experiments.runs import best_replay, best_replays  # noqa: E402
from src.experiments.training import train_agent  # noqa: E402
from src.replay.format import read_replay  # noqa: E402
from src.replay.source import short_run, source_rows  # noqa: E402
from src.replay.viewer import ReplayViewer  # noqa: E402
from tests.test_training import SHORT, TINY  # noqa: E402

RUN = "2026-10-01_122341_train-agent_1_seed0"


def _training_header(stage="box", named="box"):
    return {
        "stage": {"name": stage},
        "config": {"stage": named},
        "slots": {
            "1": {
                "type": "agent",
                "id": "agent_1",
                "training": {"run": RUN, "decisions": 505925},
            }
        },
    }


def test_a_training_episode_says_its_run_episode_and_moment(tmp_path):
    path = tmp_path / RUN / "replays" / "ep0144_score895.jsonl.gz"
    rows = dict(source_rows(_training_header(), path))
    assert rows == {
        "From": "training",
        "Run": "train-agent_1 · 10-01 12:23",
        "Episode": "144",
        "At": "505.9k decisions",
    }
    mixed = dict(source_rows(_training_header("box", "basics"), path))
    assert mixed["Mix"] == "basics"


def test_your_recording_and_a_runs_episode(tmp_path):
    header = {
        "recorded_at": "2026-09-30T11:16:27+00:00",
        "slots": {"1": {"type": "human", "player": "You"}},
    }
    kept = tmp_path / "recordings" / "You" / "kept" / "x.jsonl.gz"
    rows = dict(source_rows(header, kept))
    assert rows["From"] == "your recording, kept" and rows["Player"] == "You"
    assert rows["Recorded"].startswith("2026-09-30")
    run = tmp_path / "2026-09-27_003302_heuristic_seed0" / "replays"
    header = {"slots": {"1": {"type": "baseline"}}, "stage": {"name": "box"}}
    rows = dict(source_rows(header, run / "ep0003_score10.jsonl.gz"))
    assert rows == {
        "From": "a run",
        "Run": "heuristic · 09-27 00:33",
        "Episode": "3",
    }
    assert short_run("odd-name") == "odd-name"


def _mixed_run(tmp_path):
    root = tmp_path / "agents"
    create_agent("pupil", load_model_spec("small"), root=root)
    config = get_maze_car_config()
    config.stage = "basics"  # box, pillars, s_curve, arena
    return train_agent(
        "pupil",
        TINY,
        config,
        rules=SHORT,
        runs_dir=tmp_path / "runs",
        agents_root=root,
    )


def test_a_mixed_run_keeps_a_best_replay_per_map(tmp_path):
    summary = _mixed_run(tmp_path)
    bests = best_replays(summary.folder)
    maps = [read_replay(p).header["stage"]["name"] for p in bests]
    assert maps == sorted(["box", "pillars", "s_curve", "arena"])
    assert best_replay(summary.folder) in bests  # the overall best too


def test_the_viewer_shows_the_source_and_offers_each_maps_best(tmp_path):
    summary = _mixed_run(tmp_path)
    path = best_replay(summary.folder)
    viewer = ReplayViewer.open(path, get_maze_car_config())
    viewer.offer_bests(best_replays(summary.folder))
    rows = dict(viewer.mode().source)
    assert rows["From"] == "training" and rows["Mix"] == "basics"
    renderer = viewer.renderer
    assert len(renderer.map_choices) == 4
    assert renderer.map_current == viewer.bests.index(path)
    other = (renderer.map_current + 1) % 4
    viewer.play_best(other)
    assert viewer.path == viewer.bests[other]
    assert viewer.renderer.map_current == other  # the new window's box
    viewer.renderer.draw(
        viewer.replayer.env.world, 1.0, None, viewer.mode()
    )  # the SOURCE card in place of the leaderboard


def test_a_single_map_run_offers_no_maps(tmp_path):
    from tests.test_training import _train

    summary = _train(tmp_path)
    path = best_replay(summary.folder)
    viewer = ReplayViewer.open(path, get_maze_car_config())
    viewer.offer_bests(best_replays(summary.folder))
    assert viewer.renderer.map_choices == []
    viewer.renderer._key(pygame.K_m, False, set())
    assert not viewer.renderer.show_maps
