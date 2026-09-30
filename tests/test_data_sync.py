"""Data in sync across the control center (roadmap 7c7). Everything is in
tmp_path: your agents, runs, and maps are never read or touched here.
"""

import json
import os
import shutil
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pytest  # noqa: E402

from src.control.watch import DataWatch  # noqa: E402

REPO = __import__("src.utils.named_files", fromlist=["REPO"]).REPO


def _later():
    """Folder times have fine grain, but let a change land after it."""
    time.sleep(0.01)


def _agent(agents, name):
    folder = agents / name
    (folder / "checkpoints").mkdir(parents=True)
    (folder / "model.json").write_text('{"name": "small", "hidden": [64]}')
    return folder


# The watcher


def test_the_first_look_sees_nothing_then_each_change_once(tmp_path):
    watch = DataWatch(tmp_path)
    assert watch.changed() == set()
    _later()
    _agent(tmp_path / "agents", "a")
    assert "agents" in watch.changed()
    assert watch.changed() == set()  # nothing new since
    _later()
    (tmp_path / "agents" / "a" / "checkpoints" / "d0100.pt").write_bytes(b"")
    assert watch.changed() == {"checkpoints"}
    _later()
    (tmp_path / "user" / "stages").mkdir(parents=True)
    (tmp_path / "user" / "stages" / "mine.json").write_text("{}")
    assert "stages" in watch.changed()
    _later()
    (tmp_path / "runs" / "r1").mkdir(parents=True)
    assert "runs" in watch.changed()
    _later()
    (tmp_path / "runs" / "r1").rmdir()  # a delete is a change too
    assert watch.changed() == {"runs"}


# The window


@pytest.fixture
def window(tmp_path):
    from src.control.window import ControlCenter

    for folder in ("stages", "rules", "rewards", "trainers", "models",
                   "datasets", "suites"):
        shutil.copytree(REPO / folder, tmp_path / folder)
    _agent(tmp_path / "agents", "rookie")
    (tmp_path / "runs").mkdir()
    center = ControlCenter(
        files_root=tmp_path,
        runs_dir=tmp_path / "runs",
        agents_dir=tmp_path / "agents",
    )
    yield center
    center.jobs.stop_all()


def _options(menu):
    return [option[1] for option in menu.options_list]


def test_a_deleted_agent_leaves_the_training_tab_at_once(window, tmp_path):
    window.open_tab("Training")
    tab = window.training_tab
    agent = tab.form.widgets["Agent"]
    assert "rookie" in _options(agent)
    agent.selected_option = ("rookie", "rookie")
    tab.rebuild()  # the form for an existing agent
    assert tab.values()["Agent"] == "rookie"
    _later()
    shutil.rmtree(tmp_path / "agents" / "rookie")  # deleted elsewhere
    window._refresh(force=True)
    assert "rookie" not in _options(tab.form.widgets["Agent"])
    assert tab.values()["Agent"] != "rookie"
    assert "rookie is gone" in tab.message[0]


def test_a_hidden_tab_catches_up_when_opened(window, tmp_path):
    window.open_tab("Training")
    _later()
    stage = json.loads((tmp_path / "stages" / "box.json").read_text())
    (tmp_path / "user" / "stages").mkdir(parents=True)
    (tmp_path / "user" / "stages" / "fresh.json").write_text(
        json.dumps({**stage, "name": "fresh"})
    )
    window._refresh(force=True)
    assert "stages" in window._pending["Maps"]  # queued, not applied
    window.open_tab("Maps")
    assert not window._pending["Maps"]
    assert "fresh" in [m.name for m in window.maps_tab.maps]


def test_the_commands_tab_keeps_your_picks(window, tmp_path, monkeypatch):
    from src.control import choices

    window.open_tab("Commands")
    window._select("Drive")
    stage = window.field_widgets["Stage"]
    stage.selected_option = ("pillars", "pillars")
    # The Commands tab's choices come from the repo's files: here, a
    # stand-in list, so nothing is written to yours.
    real = choices.named

    def with_ruins(kind, *args):
        names = real(kind, *args)
        if kind == "stages":
            names = [*names, choices.Choice("ruins", "ruins · yours")]
        return names

    monkeypatch.setattr(choices, "named", with_ruins)
    _later()
    (tmp_path / "user" / "stages").mkdir(parents=True)  # a change to see
    window._refresh(force=True)
    rebuilt = window.field_widgets["Stage"]
    assert rebuilt is not stage  # new choices
    assert window.values()["Stage"] == "pillars"  # your pick kept
    assert ("ruins · yours", "ruins") in rebuilt.options_list


def test_an_open_dropdown_waits(window, tmp_path, monkeypatch):
    window.open_tab("Training")
    monkeypatch.setattr(window, "_any_dropdown_open", lambda: True)
    _later()
    _agent(tmp_path / "agents", "newcomer")
    window._refresh(force=True)
    options = _options(window.training_tab.form.widgets["Agent"])
    assert "newcomer" not in options  # not under your cursor
    monkeypatch.setattr(window, "_any_dropdown_open", lambda: False)
    window._refresh(force=True)
    assert "newcomer" in _options(window.training_tab.form.widgets["Agent"])
