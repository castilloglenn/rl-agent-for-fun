"""Showcase mode: an agent's progression in the window (step 5c)."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

import src.experiments.evaluation as evaluation  # noqa: E402
import src.experiments.showcase as showcase  # noqa: E402
from src.agents.driver import AgentDriver  # noqa: E402
from src.agents.store import load_agent  # noqa: E402
from src.config import get_maze_car_config  # noqa: E402
from src.sim.resources import SimClock  # noqa: E402
from src.experiments.showcase import Showcase, highlights, plan  # noqa
from tests.test_evaluation import _tiny_suite  # noqa: E402
from tests.test_training import _train  # noqa: E402


def _rows(scores):
    return [
        {
            "checkpoint": f"c{i:02d}",
            "decisions": float(i),
            "score_mean": float(score),
            "survival": 1.0,
        }
        for i, score in enumerate(scores)
    ]


def test_highlights_keep_the_key_checkpoints(tmp_path):
    (tmp_path / "model.json").write_text(
        '{"name": "small", "hidden": [64], "activation": "tanh", '
        '"observation_version": 1}'
    )
    (tmp_path / "checkpoints").mkdir()
    scores = [0, 1, 2, 300, 500, 900, 1000, 800, 1500, 1200]
    scores += [1100, 1300, 1400, 900, 1000, 1100, 1200, 1250, 1300, 1350]
    rows = _rows(scores)
    chosen = [r["checkpoint"] for r in highlights(rows, tmp_path)]
    assert len(chosen) == 8
    assert chosen[0] == "c00" and chosen[-1] == "c19"  # first and last
    assert "c08" in chosen  # the best (1500)
    assert "c03" in chosen  # the first scoring 10 % of the best
    assert chosen == sorted(chosen)
    few = _rows([1, 2, 3])
    assert highlights(few, tmp_path) == few


@pytest.fixture
def trained(tmp_path, monkeypatch):
    """A tiny trained, scored agent, with the cut-down suite everywhere."""
    suite = _tiny_suite(tmp_path)
    monkeypatch.setattr(showcase, "load_suite", lambda name: suite)
    monkeypatch.setattr(evaluation, "load_suite", lambda name: suite)
    monkeypatch.setattr(
        evaluation,
        "baseline_scores",
        lambda *args: {"heuristic": {"score_mean": -1}},  # milestone at once
    )
    _train(tmp_path)
    folder, stops = plan(
        "pupil", root=tmp_path / "agents", runs_dir=tmp_path / "runs"
    )
    return tmp_path, folder, stops, suite


def test_the_plan(trained):
    _, folder, stops, _ = trained
    assert [s.checkpoint for s in stops] == ["initial", "d0000256", "d0000512"]
    assert stops[0].minutes == 0.0
    assert all(s.minutes is not None and s.minutes >= 0 for s in stops)
    badges = [b for s in stops for b in s.badges]
    assert badges.count("BEST") == 1 and "MILESTONE" in badges
    assert all("score_mean" in s.scores for s in stops)


def _show(trained):
    _, folder, stops, _ = trained
    return Showcase(folder, stops, get_maze_car_config())


def test_the_title_card_stays_until_enter(trained):
    show = _show(trained)
    messages = show.mode().messages
    assert messages[0][0].startswith("pupil · initial · 1 of 3")
    assert messages[-1][0] == "Enter starts"
    for _ in range(10):
        show.tick(1.0)
    assert show.env.world.resource(SimClock).step == 0  # still on the card
    show.handle_key(pygame.K_RETURN)
    show.tick(0.5)
    assert show.mode().messages == ()  # playing
    assert show.mode().label == "SHOWCASE 1/3"
    assert show.mode().playback.speed == 2.0  # shown in the playback bar


def test_a_big_stages_intro_waits_for_the_card(trained):
    from src.render.camera import Camera

    show = _show(trained)
    view = show.renderer.camera.view
    show.renderer.camera = Camera.for_stage(1200, 1200, view)  # a big one
    show.handle_key(pygame.K_RETURN)  # the card closes: the intro plays
    assert not show.card and show.renderer.camera.in_intro


def _play_to_end(show):
    for _ in range(10_000):
        if show.env.is_game_over:
            return
        show.tick(0.05)
    raise AssertionError("the round never ended")


def test_the_round_is_the_one_the_evaluation_played(trained):
    tmp_path, folder, stops, suite = trained
    show = _show(trained)
    show._start(2)
    show.handle_key(pygame.K_RETURN)
    _play_to_end(show)
    scenario = next(s for s in suite.scenarios if s.kind == "round")
    env = evaluation._env(scenario, None)
    driver = AgentDriver(load_agent(folder, stops[2].checkpoint))
    played = evaluation._play(env, driver, scenario.first_seed)
    assert show.env.score == played["score"]


def test_it_moves_on_and_ends_with_a_summary(trained):
    show = _show(trained)
    show.handle_key(pygame.K_RETURN)
    _play_to_end(show)
    assert show.mode().messages[1][0] == "Enter: the next checkpoint"
    for _ in range(10):
        show.tick(1.0)
    assert show.index == 0  # the result stays until Enter
    show.handle_key(pygame.K_RETURN)
    assert show.index == 1 and show.card  # the next card waits for Enter
    show.handle_key(pygame.K_RIGHT)
    show.handle_key(pygame.K_RIGHT)
    assert show.finished
    assert "3 checkpoints shown" in show.mode().messages[0][0]
    show.handle_key(pygame.K_LEFT)
    assert not show.finished and show.index == 2
    show.handle_key(pygame.K_LEFT)
    assert show.index == 1


def test_restart_and_pause(trained):
    show = _show(trained)
    show.handle_key(pygame.K_RETURN)
    show.tick(0.5)
    show.handle_key(pygame.K_SPACE)
    step = show.env.world.resource(SimClock).step
    show.tick(1.0)
    assert show.env.world.resource(SimClock).step == step
    show.handle_key(pygame.K_r)
    show.tick(0.1)
    assert show.card  # back to the title card


def test_navigating_shows_the_card_again(trained):
    show = _show(trained)
    show.handle_key(pygame.K_RETURN)
    show.handle_key(pygame.K_RIGHT)
    assert show.index == 1 and show.card
    show.handle_key(pygame.K_LEFT)
    assert show.index == 0 and show.card


def test_the_showcase_draws_a_trail_too(trained):
    show = _show(trained)
    assert len(show.trail) == 1  # the start
    show.handle_key(pygame.K_RETURN)
    for _ in range(30):
        show.tick(1 / 60)
    assert len(show.trail) > 10 and show.mode().trail is show.trail
    assert ("T", "trail: where the car has been") in show.mode().shortcuts
    show.handle_key(pygame.K_RIGHT)
    assert len(show.trail) == 1  # a new checkpoint starts a new trail

