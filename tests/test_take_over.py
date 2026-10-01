"""Taking over while watching (7f9): held driving keys drive, the driver
goes on when they're released. Testing only: nothing is recorded.
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from src.config import get_maze_car_config  # noqa: E402
from src.envs.maze_car.demo import MazeCarDemo  # noqa: E402
from src.sim.components import Motion  # noqa: E402

REVERSE = (False, False, False, True, False)
NONE = (False,) * 5


def _watch():
    return MazeCarDemo(
        get_maze_car_config(), driver="heuristic", autorun=False,
        record=False,
    )


def test_held_keys_drive_and_letting_go_hands_back(monkeypatch):
    demo = _watch()
    held = {"keys": REVERSE}
    monkeypatch.setattr(demo.override, "act", lambda *a: held["keys"])
    for _ in range(30):
        demo.frame(1 / 60)
    speed = demo.env.world.component(demo.env.car, Motion).speed
    assert speed < 0  # your reverse, not the heuristic's gas
    assert demo.overriding and demo.mode().label == "YOU are driving"
    held["keys"] = NONE  # let go
    for _ in range(60):
        demo.frame(1 / 60)
    speed = demo.env.world.component(demo.env.car, Motion).speed
    assert speed > 0  # the heuristic drives again
    assert not demo.overriding and demo.takeovers == 1
    assert "you took over 1x" in demo.mode().label
    assert demo.recorder is None  # watching records nothing


def test_a_new_round_clears_the_tally(monkeypatch):
    demo = _watch()
    held = {"keys": REVERSE}
    monkeypatch.setattr(demo.override, "act", lambda *a: held["keys"])
    for _ in range(5):
        demo.frame(1 / 60)
    assert demo.takeovers == 1 and demo.override_steps > 0
    held["keys"] = NONE
    demo.env.reset()  # R: a new round
    demo.frame(1 / 60)
    assert demo.takeovers == 0 and demo.override_steps == 0


def test_your_own_driving_has_no_take_over():
    demo = MazeCarDemo(get_maze_car_config(), autorun=False, record=False)
    assert demo.override is None
