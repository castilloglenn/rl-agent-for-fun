"""Expert labelling (7g): your takeovers while watching an agent, saved
as corrections, and a dataset of just those moments. Everything here is
in tmp_path: nothing touches agents/ or recordings/.
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import numpy as np  # noqa: E402
import pygame  # noqa: E402
import pytest  # noqa: E402

from src.agents.driver import AgentDriver  # noqa: E402
from src.agents.model import load_model_spec  # noqa: E402
from src.agents.store import create_agent, load_agent  # noqa: E402
from src.config import get_maze_car_config  # noqa: E402
from src.envs.maze_car.demo import MazeCarDemo  # noqa: E402
from src.experiments.datasets import (  # noqa: E402
    DatasetSpec,
    build_dataset,
    load_dataset_spec,
)
from src.replay.format import read_replay  # noqa: E402
from src.replay.recordings import CORRECTIONS  # noqa: E402

REVERSE = (False, False, False, True, False)
NONE = (False,) * 5


def _watch(tmp_path, monkeypatch, armed=True):
    folder = create_agent("pupil", load_model_spec("small"), root=tmp_path)
    monkeypatch.setattr(
        "src.envs.maze_car.demo.make_driver",
        lambda name, player="": AgentDriver(load_agent(folder)),
    )
    demo = MazeCarDemo(
        get_maze_car_config(),
        driver="agent:pupil",
        autorun=False,
        record=False,
        corrections=armed,
        corrections_root=tmp_path / "recordings",
    )
    held = {"keys": NONE}
    monkeypatch.setattr(demo.override, "act", lambda *a: held["keys"])
    return demo, held


def _play(demo, held, frames_mine=20, frames_its=40):
    for _ in range(frames_its):
        demo.frame(1 / 60)
    held["keys"] = REVERSE  # take over
    for _ in range(frames_mine):
        demo.frame(1 / 60)
    held["keys"] = NONE  # hand back
    for _ in range(frames_its):
        demo.frame(1 / 60)
    demo.env.reset()  # R: the round is saved
    demo.frame(1 / 60)


def test_a_round_you_took_over_in_is_saved_with_your_stretch(
    tmp_path, monkeypatch
):
    demo, held = _watch(tmp_path, monkeypatch)
    assert demo.corrections.armed
    _play(demo, held)
    (path,) = (tmp_path / "recordings" / CORRECTIONS).glob("*.jsonl.gz")
    replay = read_replay(path)
    (stretch,) = replay.end["takeovers"]
    assert stretch[1] - stretch[0] > 0
    assert replay.header["slots"]["1"]["type"] == "agent"
    assert demo.corrections.saved_count == 1


def test_untouched_or_unarmed_rounds_arent_saved(tmp_path, monkeypatch):
    demo, held = _watch(tmp_path, monkeypatch, armed=False)
    _play(demo, held)  # took over, but REC corrections is off
    for _ in range(30):
        demo.frame(1 / 60)
    demo.env.reset()  # and a round left alone
    demo.frame(1 / 60)
    assert not list((tmp_path / "recordings").rglob("*.jsonl.gz"))


def test_turning_it_off_before_the_round_ends_still_saves_it(
    tmp_path, monkeypatch
):
    """You turned C on, corrected, turned C off, then closed the window:
    the corrections made while it was on are saved.
    """
    demo, held = _watch(tmp_path, monkeypatch, armed=False)
    demo.corrections.armed = True  # C
    held["keys"] = REVERSE
    for _ in range(20):
        demo.frame(1 / 60)
    held["keys"] = NONE
    demo.corrections.armed = False  # C again
    held["keys"] = REVERSE  # this one isn't marked
    for _ in range(60):  # over 1 s in all: shorter rounds aren't saved
        demo.frame(1 / 60)
    demo.env.finish_recording()  # closing the window
    (path,) = (tmp_path / "recordings" / CORRECTIONS).glob("*.jsonl.gz")
    (stretch,) = read_replay(path).end["takeovers"]
    assert 0 < stretch[1] - stretch[0] <= 20 * 2 + 2


def test_c_toggles_it_and_the_driver_card_says_so(tmp_path, monkeypatch):
    demo, held = _watch(tmp_path, monkeypatch, armed=False)
    demo.env.renderer.keys_pressed = [pygame.K_c]
    demo.frame(1 / 60)
    assert demo.corrections.armed
    mode = demo.mode()
    assert mode.label == "REC corrections"
    assert mode.detail[0] == "this round: 0 (0 s) · saved: 0"
    held["keys"] = REVERSE
    for _ in range(30):
        demo.frame(1 / 60)
    assert demo.mode().label == "YOU are driving"  # that still wins
    assert demo.mode().detail[0].startswith("this round: 1 (")
    held["keys"] = NONE
    for _ in range(60):
        demo.frame(1 / 60)
    demo.env.reset()  # R: saved
    demo.frame(1 / 60)
    mode = demo.mode()
    assert mode.messages[0][0].startswith("Correction saved · 1 takeover")
    assert mode.detail[0].endswith("saved: 1")


def test_the_dataset_keeps_only_your_moments_counted_ten_times(
    tmp_path, monkeypatch
):
    demo, held = _watch(tmp_path, monkeypatch)
    _play(demo, held, frames_mine=30)
    spec = DatasetSpec(name="c", player=CORRECTIONS, correction_weight=10)
    (round_,) = build_dataset(spec, 4, tmp_path / "recordings").rounds
    assert round_.weight == 10
    # About 30 frames of yours at 120 steps/s, 4 steps a decision.
    assert 0 < len(round_.actions) <= 30 * 2 // 4 + 2
    from src.drivers.actions import CANONICAL_NAMES

    assert {CANONICAL_NAMES[a] for a in round_.actions} == {"none+reverse"}


def test_weighted_rounds_repeat_in_training(tmp_path):
    from src.agents.trainer import load_imitation_spec
    from src.experiments.datasets import Round
    from src.experiments.imitation import _tensors

    def round_(n, weight):
        return Round(
            tmp_path, 0, "time", "box", "standard",
            np.zeros((n, 23), np.float32), np.zeros(n, np.int64),
            np.zeros(n, np.float32), weight,
        )

    x, y, returns = _tensors(
        [round_(5, 1), round_(2, 10)], load_imitation_spec("correct")
    )
    assert len(y) == 5 + 2 * 10


def test_the_built_in_dataset_and_trainer():
    spec = load_dataset_spec("corrections")
    assert (spec.player, spec.also) == (CORRECTIONS, ("Navigator",))
    assert spec.correction_weight == 10


def test_corrections_need_an_agent_being_watched():
    from tests.test_guard_rails import _check

    assert _check(["-demo", "maze_car", "--driver", "agent:a",
                   "--corrections"]) == []
    (problem,) = _check(["-demo", "maze_car", "--driver", "heuristic",
                         "--corrections"])
    assert "only while watching an agent" in problem
    with pytest.raises(AssertionError):
        assert _check(["-run", "x", "--driver", "heuristic",
                       "--corrections"]) == []
