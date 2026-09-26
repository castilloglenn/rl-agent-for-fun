"""Recording your own demo rounds (roadmap step 4i)."""

import os

import pytest

from src.config import get_maze_car_config
from src.envs.maze_car.env import MazeCarEnv
from src.replay.format import read_replay
from src.replay.recorder import human_driver
from src.replay.recordings import (
    LibraryRecorder,
    RecordingLibrary,
    folder_name,
    format_recordings,
    latest_recording,
    list_recordings,
)
from src.replay.replayer import Replayer

GAS = (False, False, True, False, False)
CIRCLE = (True, False, True, False, False)  # never reaches a wall


def _env(tmp_path, player="zen", limit=50):
    config = get_maze_car_config()
    config.show_gui = False
    library = RecordingLibrary(player, root=tmp_path, limit=limit)
    recorder = LibraryRecorder({"1": human_driver(player)}, library)
    return MazeCarEnv(config, recorder=recorder), recorder, library


def _drive(env, action, steps):
    for _ in range(steps):
        env.step_world(action)


def test_folder_names_are_safe():
    assert folder_name("You") == "You"
    assert folder_name("zen") == "zen"
    assert folder_name("Mr. Glenn / 2") == "Mr_Glenn_2"
    assert folder_name("///") == "player"


def test_a_finished_round_is_saved_automatically(tmp_path):
    env, recorder, library = _env(tmp_path)
    while not env.is_game_over:
        env.step_world(GAS)  # straight into the wall
    path = recorder.last_saved
    assert path.parent == tmp_path / "zen"
    assert path.name.endswith("_all_out.jsonl.gz")
    assert Replayer(read_replay(path)).run().ok


def test_restarting_mid_round_saves_it_as_stopped(tmp_path):
    env, recorder, library = _env(tmp_path)
    _drive(env, CIRCLE, 300)
    env.reset()  # what R does
    assert len(library.recent()) == 1
    saved = library.recent()[0]
    assert saved.name.endswith("_stopped.jsonl.gz")
    assert Replayer(read_replay(saved)).run().ok


def test_very_short_rounds_are_not_saved(tmp_path):
    env, recorder, library = _env(tmp_path)
    _drive(env, CIRCLE, 60)  # half a second
    env.reset()
    assert library.recent() == []


def test_quitting_saves_the_round(tmp_path):
    env, recorder, library = _env(tmp_path)
    _drive(env, CIRCLE, 300)
    env.finish_recording()  # what quitting the demo does
    assert len(library.recent()) == 1


def test_only_the_latest_are_kept_unless_kept(tmp_path):
    env, recorder, library = _env(tmp_path, limit=3)
    _drive(env, CIRCLE, 200)
    env.reset()
    kept = recorder.keep_last()
    assert kept.parent == tmp_path / "zen" / "kept"
    for _ in range(5):
        _drive(env, CIRCLE, 200)
        env.reset()
    assert len(library.recent()) == 3  # the oldest were removed
    assert library.kept() == [kept]  # the kept one survives


def test_keeping_twice_does_nothing(tmp_path):
    env, recorder, library = _env(tmp_path)
    _drive(env, CIRCLE, 200)
    env.reset()
    assert recorder.keep_last() is not None
    assert recorder.keep_last() is None
    assert len(library.kept()) == 1


def test_players_have_their_own_folders(tmp_path):
    for player in ("zen", "guest"):
        env, _, _ = _env(tmp_path, player=player)
        _drive(env, CIRCLE, 200)
        env.finish_recording()
    rows = list_recordings(tmp_path)
    assert [row["player"] for row in rows] == ["guest", "zen"]
    assert all(row["recent"] == 1 and row["kept"] == 0 for row in rows)
    assert "guest" in format_recordings(rows)


def test_latest_recording(tmp_path):
    env, recorder, library = _env(tmp_path)
    _drive(env, CIRCLE, 200)
    env.reset()
    first = library.recent()[0]
    os.utime(first, (0, 0))  # make the first one clearly older
    _drive(env, CIRCLE, 200)
    env.finish_recording()
    second = next(p for p in library.recent() if p != first)
    assert latest_recording(tmp_path) == second
    assert library.recent() == [first, second]  # oldest first


def test_no_recordings_yet(tmp_path):
    assert list_recordings(tmp_path) == []
    assert "No recordings yet" in format_recordings([])
    with pytest.raises(FileNotFoundError):
        latest_recording(tmp_path)
