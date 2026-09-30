"""Roadmap step 7c3: the Maps tab. Four stages and the suites are copied
into tmp_path (not every stage: maps you add would change the results);
the repo's are only read.
"""

import json
import os
import shutil

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

from src.control import maps_data  # noqa: E402
from src.control.maps_data import MapError  # noqa: E402
from tests.test_runs_tab import _folder, _job  # noqa: E402

STAGES = ("arena", "box", "pillars", "s_curve")


@pytest.fixture
def root(tmp_path):
    shutil.copytree(maps_data.REPO / "suites", tmp_path / "suites")
    (tmp_path / "stages").mkdir()
    for stage in STAGES:
        name = f"{stage}.json"
        shutil.copy(maps_data.REPO / "stages" / name, tmp_path / "stages")
    yours = tmp_path / "user" / "stages"  # a map of yours, like pillars
    yours.mkdir(parents=True)
    pillars = json.loads((tmp_path / "stages" / "pillars.json").read_text())
    (yours / "ruins.json").write_text(json.dumps({**pillars, "name": "ruins"}))
    runs_dir = tmp_path / "runs"
    for name, stage, kind in (
        ("r1", "ruins", "training"),
        ("r2", "ruins", "training"),
        ("r3", "arena", None),
    ):
        folder = _folder(runs_dir, name, kind=kind)
        config = json.loads((folder / "config.json").read_text())
        config["stage"] = {"name": stage}
        (folder / "config.json").write_text(json.dumps(config))
    return tmp_path


def _maps(root):
    found = maps_data.load_maps(root, root / "runs")
    return {m.name: m for m in found}


# The data


def test_every_stage_with_what_uses_it(root):
    maps = _maps(root)
    assert set(maps) == {"arena", "box", "pillars", "ruins", "s_curve"}
    assert maps["ruins"].played == {("pupil", "training"): 2}
    assert maps["arena"].played == {("heuristic", "episodes"): 1}
    assert maps["box"].suites == ["skills"]
    assert maps["arena"].big and not maps["pillars"].big
    assert maps["box"].badges() == ["BUILT-IN", "DEFAULT", "SUITE"]
    assert maps["arena"].badges() == ["BUILT-IN", "BIG"]
    assert maps["ruins"].badges() == ["YOURS"]


def test_what_is_protected(root):
    maps = _maps(root)
    assert "built-in" in maps["box"].protected
    assert "built-in" in maps["pillars"].protected
    assert maps["ruins"].protected == ""
    suite = json.loads((root / "suites/skills.json").read_text())
    suite["scenarios"][0]["stage"] = "ruins"
    (root / "suites/skills.json").write_text(json.dumps(suite))
    assert "suite" in _maps(root)["ruins"].protected


def test_sorting(root):
    maps = list(_maps(root).values())
    by = maps_data.sort_maps
    assert [m.name for m in by(maps, "name")][0] == "arena"
    assert [m.name for m in by(maps, "walls")][0] == "arena"  # 7 walls


def test_new_names_and_duplicating(root):
    with pytest.raises(MapError, match="letters, digits"):
        maps_data.check_new_name(root, "my map")
    with pytest.raises(MapError, match="already exists"):
        maps_data.check_new_name(root, "box")
    path = maps_data.duplicate(root, "s_curve", " s_curve_2 ")
    data = json.loads(path.read_text())
    assert path.name == "s_curve_2.json" and data["name"] == "s_curve_2"
    assert data["walls"] == _maps(root)["s_curve"].data["walls"]


# The tab


@pytest.fixture
def window(root):
    from src.control.window import ControlCenter

    center = ControlCenter(files_root=root, runs_dir=root / "runs")
    started = []

    def start(label, argv):
        started.append(argv)
        return _job()

    center.jobs.start = start
    center.started = started
    center.open_tab("Maps")
    yield center


def test_cards_select_a_map(window):
    tab = window.maps_tab
    assert tab.selected == "arena"  # the first by name
    window.draw()
    names = [name for _, name in tab.hit]
    assert names == ["arena", "box", "pillars", "ruins", "s_curve"]
    tab.click(tab.hit[4][0].center)
    assert tab.selected == "s_curve"


def test_edit_drive_and_watch(window):
    tab = window.maps_tab
    tab.select("pillars")
    tab.press("Edit")
    assert window.started[-1][-2:] == ["-edit_map", "pillars"]
    tab.press("Drive")
    argv = window.started[-1]
    assert argv[argv.index("--stage") + 1] == "pillars"
    tab.press("Watch")
    argv = window.started[-1]
    assert argv[argv.index("--driver") + 1] == "heuristic"
    assert argv[argv.index("--stage") + 1] == "pillars"


def test_new_map_opens_the_editor(window):
    tab = window.maps_tab
    tab.new_name.set_text("box")
    tab.press("New map")
    assert "already exists" in tab.message[0] and window.started == []
    tab.new_name.set_text("my_track")
    tab.press("New map")
    assert window.started[-1][-2:] == ["-edit_map", "my_track"]


def test_duplicate_selects_the_copy(window, root):
    tab = window.maps_tab
    tab.select("s_curve")
    tab.new_name.set_text("s_curve_copy")
    tab.press("Duplicate")
    assert (root / "user/stages/s_curve_copy.json").exists()
    assert tab.selected == "s_curve_copy"


def test_delete_asks_and_protects_built_ins(window, root):
    tab = window.maps_tab
    tab.select("box")
    assert not tab.buttons["Delete"].is_enabled
    tab.press("Delete")
    assert window.box is None  # nothing asked: it's protected
    tab.select("pillars")  # built-in: protected too
    assert not tab.buttons["Delete"].is_enabled
    tab.select("ruins")
    tab.press("Delete")
    assert window.box.title == "DELETE A MAP?"
    assert any("2 runs" in text for text, _ in window.box.lines)
    window.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
    assert not (root / "user/stages/ruins.json").exists()
    assert "ruins" not in [m.name for m in tab.maps]
