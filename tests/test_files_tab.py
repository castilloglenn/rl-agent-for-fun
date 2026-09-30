"""Step 6d1: editing the named files. The repo's files are only read;
every edit, save, and delete happens in a scratch copy in tmp_path.
"""

import json
import os
import shutil

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

from src.control import agents_data, files  # noqa: E402
from src.control.files import KINDS, FileError  # noqa: E402

FOLDERS = ("rewards", "rules", "trainers", "models", "datasets", "suites")
KIND = {k.folder: k for k in KINDS}


@pytest.fixture
def repo(tmp_path):
    for folder in (*FOLDERS, "stages"):
        shutil.copytree(files.REPO / folder, tmp_path / folder)
    _yours(tmp_path, "rules", "sprint", "my_sprint")
    _yours(tmp_path, "suites", "skills", "my_suite")
    return tmp_path


def _yours(repo, folder, like, name):
    """A file of yours: a copy of a built-in in user/<folder>/."""
    data = json.loads((repo / folder / f"{like}.json").read_text())
    mine = repo / "user" / folder
    mine.mkdir(parents=True, exist_ok=True)
    (mine / f"{name}.json").write_text(files.dump({**data, "name": name}))


# Fields and files


def test_every_file_round_trips_exactly():
    """Saving an unchanged file changes nothing (read-only on the repo)."""
    for kind in KINDS:
        built_in = files.REPO / kind.folder  # yours never change a test
        for path in sorted(built_in.glob("*.json")):
            data = json.loads(path.read_text())
            assert files.dump(data) == path.read_text(), path
            values = {
                i.path: i.text
                for i in files.items(kind.folder, data)
                if i.type != "readonly"
            }
            back = files.rebuild(kind.folder, data, values)
            assert files.dump(back) == path.read_text(), path
            assert files.check(kind, data) is None, path


def test_fields_by_path_and_type(repo):
    data = files.load(repo, KIND["suites"], "skills")
    by = {i.path: i for i in files.items("suites", data, repo)}
    assert by["name"].type == "readonly"
    assert by["scenarios.0.kind"].type == "readonly"
    assert by["scenarios.0.start.speed"].type == "number"  # braking
    assert by["scenarios.0.stage"].type == "choice"
    assert "box" in by["scenarios.0.stage"].options
    model = files.load(repo, KIND["models"], "small")
    by = {i.path: i for i in files.items("models", model, repo)}
    assert by["hidden"].type == "list" and by["hidden"].text == "64, 64"
    assert by["activation"].type == "choice"


def test_a_list_and_numbers_parse_back(repo):
    model = files.load(repo, KIND["models"], "small")
    edited = files.rebuild("models", model, {"hidden": "128, 32"})
    assert edited["hidden"] == [128, 32]
    rules = files.load(repo, KIND["rules"], "standard")
    edited = files.rebuild("rules", rules, {"collisions.scrape_damage": "0.2"})
    assert edited["collisions"]["scrape_damage"] == 0.2
    with pytest.raises(FileError, match="isn't a number"):
        files.rebuild("rules", rules, {"round_seconds": "soon"})


def test_the_validators_catch_bad_values(repo):
    trainer = files.load(repo, KIND["trainers"], "default")
    bad = files.rebuild("trainers", trainer, {"gamma": "2"})
    assert "gamma" in files.check(KIND["trainers"], bad)
    bad = files.rebuild("trainers", trainer, {"rollout": "2048.5"})
    assert "rollout" in files.check(KIND["trainers"], bad)


def test_reward_terms_can_be_added_and_dropped(repo):
    reward = files.load(repo, KIND["rewards"], "default")
    values = {
        i.path: i.text for i in files.items("rewards", reward)
        if i.type != "readonly"
    }
    assert values["terms.time_up"] == ""  # known, unused
    values["terms.stopped"] = ""  # dropped
    values["terms.time_up"] = "-50"  # added
    edited = files.rebuild("rewards", reward, values)
    assert "stopped" not in edited["terms"]
    assert edited["terms"]["time_up"] == -50
    assert list(edited["terms"])[:3] == ["progress", "checkpoints", "contact"]
    values["terms.checkpoint_speed.window"] = "5"  # a parameter, no weight
    with pytest.raises(FileError, match="needs a weight"):
        files.rebuild("rewards", reward, values)
    values["terms.checkpoint_speed"] = "100"
    edited = files.rebuild("rewards", reward, values)
    assert edited["terms"]["checkpoint_speed"] == {"weight": 100, "window": 5}


def test_saving_a_changed_suite_makes_the_next_version(repo):
    kind = KIND["suites"]
    data = files.load(repo, kind, "my_suite")
    files.save(repo, kind, "my_suite", data)  # unchanged: same version
    assert files.load(repo, kind, "my_suite")["version"] == 1
    edited = files.rebuild("suites", data, {"scenarios.0.episodes": "30"})
    written = files.save(repo, kind, "my_suite", edited)
    assert written["version"] == 2
    path = repo / "user" / "suites" / "my_suite.json"
    assert agents_data.current_suite(path) == "my_suite-v2"


def test_a_built_in_file_is_never_saved(repo):
    kind = KIND["rules"]
    data = files.load(repo, kind, "standard")
    before = (repo / "rules" / "standard.json").read_text()
    with pytest.raises(FileError, match="built-in"):
        files.save(repo, kind, "standard", {**data, "round_seconds": 45})
    assert (repo / "rules" / "standard.json").read_text() == before


def test_duplicate(repo):
    kind = KIND["rules"]
    path = files.duplicate(repo, kind, "standard", "mine")
    assert json.loads(path.read_text())["name"] == "mine"
    with pytest.raises(FileError, match="already exists"):
        files.duplicate(repo, kind, "standard", "mine")
    with pytest.raises(FileError, match="letters, digits"):
        files.duplicate(repo, kind, "standard", "my rules")
    suite = files.duplicate(repo, KIND["suites"], "skills", "hard")
    assert json.loads(suite.read_text())["version"] == 1


# The tab


@pytest.fixture
def window(repo):
    from src.control.window import ControlCenter

    center = ControlCenter(files_root=repo)
    center.open_tab("Files")
    yield center
    center.jobs.stop_all()


def _show(tab, label, name):
    kind = next(k for k in KINDS if k.label == label)
    tab._show_kind(kind, name)


def test_editing_checks_as_you_type(window, repo):
    tab = window.files_tab
    _show(tab, "Rules", "my_sprint")
    assert tab.name == "my_sprint" and not tab.dirty
    assert not tab.buttons["Save"].is_enabled
    tab.form.widgets["round_seconds"].set_text("oops")
    tab.check(force=True)
    assert "isn't a number" in tab.problem
    assert not tab.buttons["Save"].is_enabled
    tab.form.widgets["round_seconds"].set_text("45")
    tab.check(force=True)
    assert tab.problem is None and tab.dirty
    assert tab.buttons["Save"].is_enabled
    tab.save()
    assert files.load(repo, KIND["rules"], "my_sprint")["round_seconds"] == 45
    assert not tab.dirty
    window.draw()


def test_revert(window):
    tab = window.files_tab
    _show(tab, "Rules", "my_sprint")
    tab.form.widgets["round_seconds"].set_text("45")
    tab.check(force=True)
    tab._open(tab.name)  # Revert
    assert not tab.dirty
    assert tab.form.widgets["round_seconds"].get_text() != "45"


def test_switching_with_unsaved_changes_asks(window):
    tab = window.files_tab
    _show(tab, "Rules", "my_sprint")
    tab.form.widgets["round_seconds"].set_text("45")
    tab.check(force=True)
    tab._unless_dirty(lambda: tab._open("standard"))
    assert window.box.title == "DISCARD CHANGES?"
    assert tab.name == "my_sprint"  # nothing changed until you answer
    window.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
    assert tab.name == "standard"


def test_quitting_mentions_unsaved_changes(window):
    tab = window.files_tab
    _show(tab, "Rules", "my_sprint")
    tab.form.widgets["round_seconds"].set_text("45")
    tab.check(force=True)
    window.ask_to_quit()
    assert any("user/rules/my_sprint.json" in t for t, _ in window.box.lines)


def test_a_built_in_is_read_only_in_the_tab(window):
    tab = window.files_tab
    _show(tab, "Rules", "standard")
    assert tab.built_in and tab.path == "rules/standard.json"
    for name in ("Save", "Revert", "Delete"):
        assert not tab.buttons[name].is_enabled
    assert tab.buttons["Duplicate as…"].is_enabled
    assert not tab.form.widgets["round_seconds"].is_enabled  # read-only
    rows = [item["text"] for item in tab.file_list.item_list]
    built_in, yours = "standard  · built-in", "my_sprint  · yours"
    assert rows.index(built_in) < rows.index(yours)  # built-ins first
    window.draw()


def test_yours_can_be_edited_and_deleted(window):
    tab = window.files_tab
    _show(tab, "Rules", "my_sprint")
    assert not tab.built_in and tab.path == "user/rules/my_sprint.json"
    assert tab.buttons["Delete"].is_enabled
    assert tab.form.widgets["round_seconds"].is_enabled


def test_delete_moves_the_file_into_the_trash(window, repo):
    tab = window.files_tab
    _show(tab, "Rules", "my_sprint")
    tab.delete()
    assert window.box.title == "DELETE A FILE?"
    window.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
    assert not (repo / "user" / "rules" / "my_sprint.json").exists()
    (entry,) = (repo / "trash").iterdir()
    assert list(entry.rglob("my_sprint.json"))
    assert tab.name != "my_sprint"


def test_the_tab_duplicates_and_opens_the_copy(window, repo):
    tab = window.files_tab
    _show(tab, "Trainers", "default")
    tab.new_name.set_text("quick")
    tab.duplicate()
    assert tab.name == "quick"
    assert (repo / "user" / "trainers" / "quick.json").exists()
    window.draw()
