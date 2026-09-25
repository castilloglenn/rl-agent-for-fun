"""Replay mode in the window (roadmap step 4e)."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

from src.config import get_maze_car_config  # noqa: E402
from src.envs.maze_car.env import MazeCarEnv  # noqa: E402
from src.render import theme  # noqa: E402
from src.replay.recorder import ReplayRecorder, human_driver  # noqa: E402
from src.replay.viewer import PlaybackControl, ReplayViewer  # noqa: E402

GAS = (False, False, True, False, False)


def _replay(steps=600):
    config = get_maze_car_config()
    config.show_gui = False
    recorder = ReplayRecorder({"1": human_driver("zen")})
    env = MazeCarEnv(config, recorder=recorder)
    env.reset(seed=4)
    # Circling (gas + left, with a brake now and then) never hits a wall.
    for i in range(steps):
        env.step_world((True, False, True, False, i % 300 > 280))
    env.finish_recording()
    assert not env.is_game_over
    return recorder.replay


@pytest.fixture
def viewer():
    return ReplayViewer(_replay(), get_maze_car_config())


def test_playback_keys():
    control = PlaybackControl()
    assert control.speed == 1.0 and not control.paused
    control.handle_key(pygame.K_4)
    assert control.speed == 4.0
    control.handle_key(pygame.K_1)
    assert control.speed == 0.5
    control.handle_key(pygame.K_n)
    assert control.step_requests == 0  # only while paused
    control.handle_key(pygame.K_SPACE)
    control.handle_key(pygame.K_n)
    assert control.paused and control.step_requests == 1
    control.handle_key(pygame.K_r)
    assert control.restart_requested


def test_speed_scales_the_steps_per_second(viewer):
    viewer.control.handle_key(pygame.K_3)  # 2x
    for _ in range(60):
        viewer.tick(1 / 60)
    assert viewer.replayer.step_index in (239, 240)  # 2 x 120 steps/s


def test_pause_and_single_steps(viewer):
    viewer.tick(0.5)
    at = viewer.replayer.step_index
    viewer.control.handle_key(pygame.K_SPACE)
    for _ in range(30):
        viewer.tick(1 / 60)
    assert viewer.replayer.step_index == at
    viewer.control.handle_key(pygame.K_n)
    viewer.control.handle_key(pygame.K_n)
    viewer.tick(1 / 60)
    assert viewer.replayer.step_index == at + 2


def test_restart(viewer):
    viewer.tick(1.0)
    viewer.control.handle_key(pygame.K_r)
    viewer.tick(0.0)
    assert viewer.replayer.step_index == 0


def test_playback_stops_at_the_end_with_the_verification(viewer):
    viewer.control.handle_key(pygame.K_4)
    for _ in range(200):
        viewer.tick(1 / 60)
    assert viewer.replayer.done
    mode = viewer.mode()
    assert "verified" in mode.label and mode.label_color == theme.GOOD
    assert mode.messages[0][0].startswith("REPLAY ENDED: verified")


def test_out_of_date_replay_is_flagged_from_the_start():
    replay = _replay()
    replay.end["scores"]["1"] += 5
    viewer = ReplayViewer(replay, get_maze_car_config())
    mode = viewer.mode()
    assert "OUT OF DATE" in mode.label and mode.label_color == theme.BAD
    viewer.control.handle_key(pygame.K_4)
    for _ in range(200):
        viewer.tick(1 / 60)
    assert any("score" in text for text, _ in viewer.mode().messages)


def test_the_hud_shows_the_replay(viewer):
    viewer.tick(0.3)
    env = viewer.replayer.env
    viewer.renderer.draw(env.world, 1.0, env.reward_status(), viewer.mode())
    assert env.driver == "zen (replay)"
    assert viewer.mode().hints.startswith("SPACE pause")


def test_presentation_settings_come_from_the_viewer_config():
    config = get_maze_car_config()
    config.hud.near_caution = 99.0
    viewer = ReplayViewer(_replay(steps=50), config)
    assert viewer.replayer.env.config.hud.near_caution == 99.0
