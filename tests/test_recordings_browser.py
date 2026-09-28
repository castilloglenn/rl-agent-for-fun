"""Step 6d2: the recordings browser. Recordings are copied into tmp_path
(from the repo's, read-only); nothing moves in recordings/ or trash/.
"""

import gzip
import json
import os
import shutil

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

from src.control import recordings_data  # noqa: E402
from src.control.recordings_data import parse  # noqa: E402
from src.control.trash import Trash  # noqa: E402
from src.replay.recordings import (  # noqa: E402
    RecordingError,
    keep_file,
    unkeep_file,
)
from tests.test_files_tab import FOLDERS  # noqa: E402
from tests.test_runs_tab import _job  # noqa: E402

HEADER = {
    "stage": {"name": "box"},
    "rules": {"name": "standard", "round_seconds": 60},
}
NAMES = (
    "2026-09-27_014237_seed136188_score3733_time.jsonl.gz",
    "2026-09-27_024305_seed22320_score2137_all_out.jsonl.gz",
    "2026-09-27_024912_seed114052_score0_stopped.jsonl.gz",
)


def _recording(folder, name, header=HEADER):
    folder.mkdir(parents=True, exist_ok=True)
    with gzip.open(folder / name, "wt") as file:
        file.write(json.dumps(header) + "\n")
    return folder / name


@pytest.fixture
def repo(tmp_path):
    for folder in (*FOLDERS, "stages"):
        shutil.copytree(recordings_data.REPO / folder, tmp_path / folder)
    you = tmp_path / "recordings" / "You"
    _recording(you, NAMES[0])
    _recording(you, NAMES[1])
    _recording(you / "kept", NAMES[2])
    return tmp_path


# Reading


def test_names_parse():
    r = parse(recordings_data.REPO / "x" / NAMES[1])
    assert (r.when, r.seed, r.score, r.ended) == (
        "09-27 02:43:05", 22320, 2137.0, "all out",
    )
    same_second = NAMES[0].replace("_time.", "_time_2.")
    again = parse(recordings_data.REPO / "kept" / same_second)
    assert again.ended == "time" and again.kept
    assert parse(recordings_data.REPO / "notes.txt") is None


def test_rows_with_game_and_datasets(repo):
    rows = recordings_data.recordings(
        "You", repo / "recordings", repo, "newest"
    )
    assert [r.path.name for r in rows] == [NAMES[2], NAMES[1], NAMES[0]]
    assert rows[0].kept and not rows[1].kept
    assert rows[0].game == "box / standard, 60 s rounds"
    assert rows[1].datasets == ["mine"]  # include all, min score 0
    by_score = recordings_data.recordings(
        "You", repo / "recordings", repo, "score"
    )
    assert [r.score for r in by_score] == [3733.0, 2137.0, 0.0]


def test_a_dataset_of_kept_rounds_and_a_min_score(repo):
    r = recordings_data.parse(repo / "recordings" / "You" / NAMES[1])
    assert not recordings_data.uses({"include": "kept"}, r)
    assert recordings_data.uses({"include": "all", "min_score": 2000}, r)
    assert not recordings_data.uses({"include": "all", "min_score": 3000}, r)


def test_players(repo):
    assert recordings_data.players(repo / "recordings") == [("You", 3)]


# Keeping, unkeeping, deleting


def test_keep_and_unkeep_move_the_file(repo):
    path = repo / "recordings" / "You" / NAMES[0]
    kept = keep_file(path)
    assert kept.parent.name == "kept" and not path.exists()
    with pytest.raises(RecordingError, match="already kept"):
        keep_file(kept)
    back = unkeep_file(kept)
    assert back == path and back.exists()  # not pruned
    with pytest.raises(RecordingError, match="isn't kept"):
        unkeep_file(back)


def test_delete_a_recording_into_the_trash(repo):
    path = repo / "recordings" / "You" / "kept" / NAMES[2]
    trash = Trash(repo)
    entry = trash.delete_recording(path)
    assert entry.kind == "recording" and not path.exists()
    trash.restore(entry.name)
    assert path.exists()


# The browser in the Files tab


@pytest.fixture
def window(repo):
    from src.control.window import ControlCenter

    center = ControlCenter(files_root=repo)
    started = []

    def start(label, argv):
        started.append(argv)
        return _job()

    center.jobs.start = start
    center.started = started
    center.open_tab("Files")
    center.files_tab._pick_kind("Recordings")
    yield center


def test_the_browser_lists_the_rounds(window):
    tab = window.files_tab
    view = tab.view
    assert tab.mode == "recordings" and view.player == "You"
    assert len(view.rows) == 3 and view.selected == view.rows[0].path
    assert not tab.form.widgets or not any(
        w.visible for w in tab.form.widgets.values()
    )  # the editor's fields hide
    window.draw()
    rect, path = view._hit[1]
    view.click(rect.center)
    assert view.selected == path


def test_keep_then_unkeep_follows_the_file(window, repo):
    view = window.files_tab.view
    view.selected = next(r.path for r in view.rows if not r.kept)
    view.press("Keep")
    assert view.row.kept and view.selected.parent.name == "kept"
    view.press("Unkeep")
    assert not view.row.kept
    assert "next saved round" in view.message[0]


def test_watch_starts_the_replay_action(window):
    view = window.files_tab.view
    view.press("Watch")
    argv = window.started[-1]
    assert argv[-2] == "-replay" and argv[-1].startswith("recordings/You/")


def test_delete_asks_then_moves_it(window, repo):
    view = window.files_tab.view
    doomed = view.selected
    view.press("Delete")
    assert window.box.title == "DELETE A RECORDING?"
    window.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
    assert not doomed.exists() and len(view.rows) == 2


def test_back_to_a_file_kind(window):
    tab = window.files_tab
    tab._pick_kind("Rules")
    assert tab.mode == "files" and tab.kind.folder == "rules"
    assert not tab.view.sort_menu.visible
    window.draw()
