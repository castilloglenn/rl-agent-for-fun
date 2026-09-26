"""The evaluation suite (roadmap step 5a5)."""

import csv
import json
import math
import random

import pytest

from src.agents.model import load_model_spec
from src.agents.store import AgentError, create_agent, load_agent
from src.config import get_maze_car_config
from src.drivers.heuristic import CompassDriver
from src.drivers.registry import make_driver
from src.envs.maze_car.env import MazeCarEnv
from src.experiments.evaluation import (
    COLUMNS,
    SUITES_DIR,
    Suite,
    SuiteError,
    best_row,
    evaluate,
    evaluate_agent,
    evaluate_checkpoint,
    format_results,
    load_suite,
    place_at_wall,
    read_results,
)
from src.sim.components import Hitbox, Motion, Transform
from src.sim.geometry import car_corners, inside
from src.sim.resources import Field
from tests.test_training import TINY, TrainerSpec, _rows, _train

BOX = json.loads((SUITES_DIR / "box.json").read_text())


def _tiny_suite(tmp_path, version=1):
    """The box suite (same name, so it also writes best.json), cut down to
    a few short games.
    """
    data = json.loads(json.dumps(BOX))
    data["version"] = version
    for scenario in data["scenarios"]:
        scenario["episodes"] = 2 if scenario["kind"] == "round" else 3
        if scenario["kind"] == "round":
            scenario["round_seconds"] = 3
    path = tmp_path / f"tiny-v{version}.json"
    path.write_text(json.dumps(data))
    return load_suite(str(path))


def _agent(tmp_path, name="pupil"):
    create_agent(name, load_model_spec("small"), root=tmp_path / "agents")
    return tmp_path / "agents" / name


# The suite file


def test_the_box_suite_loads():
    suite = load_suite("box")
    assert suite.label == "box-v1"
    assert [s.kind for s in suite.scenarios] == ["round", "braking"]
    assert all(s.first_seed >= 1_000_000 for s in suite.scenarios)


@pytest.mark.parametrize(
    "change, message",
    [
        (lambda d: d.update(format=2), "unsupported suite format"),
        (lambda d: d["scenarios"][0].update(kind="drift"), "unknown scenario"),
        (lambda d: d["scenarios"][0].update(episodes=0), "episodes"),
        (lambda d: d["scenarios"][1].update(start=None), "needs a start"),
        (lambda d: d["scenarios"].pop(), "one round and one braking"),
    ],
)
def test_invalid_suites_are_rejected(change, message):
    data = json.loads(json.dumps(BOX))
    change(data)
    with pytest.raises(SuiteError, match=message):
        Suite.from_dict(data)


def test_missing_suite_file():
    with pytest.raises(SuiteError, match="no suite file"):
        load_suite("nope")


# Braking starts


def _braking_env():
    config = get_maze_car_config()
    config.show_gui = False
    return MazeCarEnv(config)


def _pose(env):
    t = env.world.component(env.car, Transform)
    return (t.x, t.y, t.angle, env.world.component(env.car, Motion).speed)


def test_braking_starts_follow_the_seed():
    start = BOX["scenarios"][1]["start"]
    env = _braking_env()
    poses = []
    for seed in (5, 5, 6):
        env.reset(seed=0)
        place_at_wall(env, random.Random(seed), start)
        poses.append(_pose(env))
    assert poses[0] == poses[1] != poses[2]


@pytest.mark.parametrize("seed", range(12))
def test_braking_starts_face_a_wall_in_range(seed):
    start = BOX["scenarios"][1]["start"]
    env = _braking_env()
    env.reset(seed=0)
    place_at_wall(env, random.Random(seed), start)
    world, car = env.world, env.car
    t = world.component(car, Transform)
    hitbox = world.component(car, Hitbox)
    field = world.resource(Field).rect
    corners = car_corners(t.x, t.y, t.angle, hitbox.width, hitbox.height)
    assert inside(corners, field)
    assert world.component(car, Motion).speed * 120 == pytest.approx(300)
    # The front ray (nose to wall, along the heading) is in range.
    front = env.last_observation[0] * math.hypot(field.width, field.height)
    assert start["min_distance"] - 1e-6 <= front
    assert front <= start["max_distance"] + 1e-6


# Scoring


def test_scores_are_the_same_every_time(tmp_path):
    suite = _tiny_suite(tmp_path)
    first = evaluate(CompassDriver(), suite)
    assert evaluate(CompassDriver(), suite) == first
    assert set(first) == set(COLUMNS) - {"checkpoint", "decisions"}
    assert first["braking"] == 1.0  # the heuristic brakes in time


def test_scoring_a_checkpoint_saves_a_row_and_the_best(tmp_path):
    suite = _tiny_suite(tmp_path)
    folder = _agent(tmp_path)
    row = evaluate_checkpoint(folder, "initial", suite)
    evaluate_checkpoint(folder, "initial", suite)  # again: replaced
    rows = read_results(folder, suite)
    assert len(rows) == 1 and rows[0]["checkpoint"] == "initial"
    assert rows[0]["score_mean"] == pytest.approx(row["score_mean"])
    with open(folder / "evaluations" / "box-v1.csv") as file:
        assert tuple(next(csv.reader(file))) == COLUMNS


def test_suite_versions_are_never_mixed(tmp_path):
    folder = _agent(tmp_path)
    evaluate_checkpoint(folder, "initial", _tiny_suite(tmp_path, version=1))
    v2 = _tiny_suite(tmp_path, version=2)
    assert read_results(folder, v2) == []
    evaluate_checkpoint(folder, "initial", v2)
    names = sorted(p.name for p in (folder / "evaluations").glob("*.csv"))
    assert names == ["box-v1.csv", "box-v2.csv"]


def test_evaluating_an_agent_scores_only_new_checkpoints(tmp_path):
    suite = _tiny_suite(tmp_path)
    summary = _train(tmp_path)  # writes d0000256, d0000512
    folder = tmp_path / "agents" / "pupil"
    scored = []
    rows = evaluate_agent(folder, suite, on_checkpoint=scored.append)
    assert [r["checkpoint"] for r in rows] == [
        "initial",
        *summary.checkpoints,
    ]
    assert len(scored) == 3
    scored.clear()
    evaluate_agent(folder, suite, on_checkpoint=scored.append)
    assert scored == []
    assert "best:" in format_results(rows)


def test_the_best_is_the_highest_mean_score_then_survival():
    rows = [
        {"checkpoint": "a", "score_mean": 10, "survival": 0.5},
        {"checkpoint": "b", "score_mean": 30, "survival": 0.5},
        {"checkpoint": "c", "score_mean": 30, "survival": 0.9},
    ]
    assert best_row(rows)["checkpoint"] == "c"


# Loading the best


def _best_json(folder, checkpoint):
    (folder / "evaluations").mkdir(exist_ok=True)
    (folder / "evaluations" / "best.json").write_text(
        json.dumps({"suite": "box-v1", "checkpoint": checkpoint})
    )


def test_watching_loads_the_best_and_training_the_newest(tmp_path):
    _train(tmp_path)  # newest: d0000512
    folder = tmp_path / "agents" / "pupil"
    _best_json(folder, "d0000256")
    root = tmp_path / "agents"
    assert load_agent("pupil", root=root).checkpoint == "d0000512"
    assert load_agent("pupil", root=root, prefer_best=True).checkpoint == (
        "d0000256"
    )
    assert load_agent("pupil", "best", root=root).checkpoint == "d0000256"
    driver = make_driver(f"agent:{folder}")
    assert driver.record()["checkpoint"] == "d0000256"
    summary = _train(tmp_path)  # a new phase continues the newest
    config = json.loads((summary.folder / "config.json").read_text())
    assert config["agent"]["start_checkpoint"] == "d0000512"


def test_best_needs_scores(tmp_path):
    folder = _agent(tmp_path)
    with pytest.raises(AgentError, match="no scored checkpoints"):
        load_agent(folder, "best")
    assert load_agent(folder, prefer_best=True).checkpoint == "initial"


# Scoring during training


def test_scoring_during_training_changes_nothing_else(tmp_path, monkeypatch):
    import src.experiments.training as training

    suite = _tiny_suite(tmp_path)
    monkeypatch.setattr(training, "load_suite", lambda name: suite)
    scoring = TrainerSpec.from_dict({**TINY.to_dict(), "evaluate": True})
    reports = []
    plain = _train(tmp_path / "plain")
    scored = _train(
        tmp_path / "scored", trainer=scoring, on_update=reports.append
    )

    def learning(summary):
        rows = _rows(summary.folder / "learning.csv")
        return [{**row, "seconds": None} for row in rows]

    assert learning(plain) == learning(scored)
    evaluated = [r.saved for r in reports if r.evaluation]
    assert evaluated == ["d0000256", "d0000512"]
    folder = tmp_path / "scored" / "agents" / "pupil"
    assert [r["checkpoint"] for r in read_results(folder, suite)] == evaluated
    config = json.loads((scored.folder / "config.json").read_text())
    assert config["suite"] == {"name": "box", "version": 1}
    assert load_agent(folder, "best").checkpoint in evaluated
