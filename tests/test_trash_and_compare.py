"""Step 6b3: the trash, the checkpoint box, and comparing runs. Every
folder here is in tmp_path: nothing touches runs/, agents/, or trash/.
"""

import json
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

from src.control.trash import Trash, TrashError, format_entries  # noqa
from tests.test_runs_tab import _folder, _job  # noqa: E402

RUN = "2026-09-27_003302_train-pupil_seed0"
OTHER = "2026-09-27_014849_train-pupil_seed0"


# The trash


def test_deleting_a_run_moves_it_into_the_trash(tmp_path):
    _folder(tmp_path / "runs", RUN, summary={"interrupted": False})
    trash = Trash(tmp_path)
    entry = trash.delete_run(RUN)
    assert not (tmp_path / "runs" / RUN).exists()
    kept = tmp_path / "trash" / entry.name
    assert (kept / "runs" / RUN / "config.json").exists()
    info = json.loads((kept / "trash.json").read_text())
    assert info["kind"] == "run" and info["paths"] == [f"runs/{RUN}"]
    assert [e.name for e in trash.entries()] == [entry.name]
    assert entry.name in format_entries(trash.entries())


def test_restore_puts_it_back(tmp_path):
    _folder(tmp_path / "runs", RUN, summary={})
    trash = Trash(tmp_path)
    entry = trash.delete_run(RUN)
    trash.restore(entry.name)
    assert (tmp_path / "runs" / RUN / "config.json").exists()
    assert trash.entries() == []  # the entry is gone
    assert not (tmp_path / "trash" / entry.name).exists()


def test_restore_is_refused_when_the_name_is_taken(tmp_path):
    _folder(tmp_path / "runs", RUN, summary={})
    trash = Trash(tmp_path)
    entry = trash.delete_run(RUN)
    _folder(tmp_path / "runs", RUN, summary={})  # a new one, same name
    with pytest.raises(TrashError, match="exists again"):
        trash.restore(entry.name)
    assert trash.entries()  # still safe in the trash


def test_a_live_or_missing_run_is_refused(tmp_path):
    live = _folder(tmp_path / "runs", RUN)
    (live / "training.lock").write_text(str(os.getpid()))
    trash = Trash(tmp_path)
    with pytest.raises(TrashError, match="still running"):
        trash.delete_run(RUN)
    with pytest.raises(TrashError, match="no run"):
        trash.delete_run("nothing")
    assert live.exists()


def test_emptying_deletes_for_good(tmp_path):
    for name in (RUN, OTHER):
        _folder(tmp_path / "runs", name, summary={})
    trash = Trash(tmp_path)
    trash.delete_run(RUN)
    trash.delete_run(OTHER)
    assert len(trash.empty()) == 2
    assert trash.entries() == [] and not any(
        (tmp_path / "trash").iterdir()
    )
    assert format_entries([]) == "The trash is empty."


def test_the_agent_digest_marks_a_deleted_run(tmp_path):
    from tests.test_training import _train

    from src.experiments.agents import agent_summary

    summary = _train(tmp_path)
    runs_dir = tmp_path / "runs"
    text = agent_summary("pupil", tmp_path / "agents", runs_dir)
    assert "(run deleted)" not in text
    Trash(tmp_path).delete_run(summary.folder.name)
    text = agent_summary("pupil", tmp_path / "agents", runs_dir)
    assert f"{summary.folder.name} (run deleted)" in text


# Asking first


@pytest.fixture
def window(tmp_path):
    from src.control.window import ControlCenter

    runs_dir = tmp_path / "runs"
    for name in (RUN, OTHER):
        _folder(
            runs_dir,
            name,
            summary={"interrupted": False},
            learning_csv="decisions,score_mean,seconds\n100,5,1\n200,9,2\n",
        )
    config = json.loads((runs_dir / RUN / "config.json").read_text())
    config["suite"] = {"name": "box", "version": 1}
    (runs_dir / RUN / "config.json").write_text(json.dumps(config))
    agent = tmp_path / "agents" / "pupil"
    agent.mkdir(parents=True)
    events = [
        {"event": "checkpoint_saved", "run": RUN, "checkpoint": "d0100",
         "decisions": 100},
        {"event": "scored", "checkpoint": "d0100", "suite": "box-v1",
         "score_mean": 7.0},
    ]
    (agent / "history.jsonl").write_text(
        "\n".join(json.dumps(e) for e in events) + "\n"
    )
    center = ControlCenter(runs_dir=runs_dir, agents_dir=tmp_path / "agents")
    started = []

    def start(label, argv):
        started.append((label, argv))
        return _job()

    center.jobs.start = start
    center.started = started
    yield center


def _key(window, key):
    window.handle(pygame.event.Event(pygame.KEYDOWN, key=key))


def test_deleting_asks_first(window):
    window.run_named("Delete a run", {"Run": RUN})
    assert window.box.title == "DELETE A RUN?" and window.started == []
    _key(window, pygame.K_ESCAPE)  # cancel
    assert window.box is None and window.started == []
    window.run_named("Delete a run", {"Run": RUN})
    _key(window, pygame.K_RETURN)  # confirm
    assert window.started[0][1][-2:] == ["-delete_run", RUN]
    assert window.running  # a delete box isn't the quit box


def test_closing_the_window_during_a_delete_asks_to_quit(window):
    window.run_named("Empty the trash", {})
    assert window.box.title == "EMPTY THE TRASH?"
    window.handle(pygame.event.Event(pygame.QUIT))
    assert window.confirm_quit and window.running


def test_the_runs_tab_delete_button(window):
    window.open_tab("Runs")
    tab = window.runs_tab
    tab.select(RUN)
    assert tab.buttons["Delete run"].is_enabled
    tab.press("Delete run")
    assert window.box.title == "DELETE A RUN?"


# The checkpoint box


def _open_box(window):
    window.open_tab("Runs")
    tab = window.runs_tab
    tab.select(RUN)
    window.draw()  # the chart says where it drew
    point = tab.data.suite_points[0]
    x, y = tab._plot.to_screen(point[1], point[2])
    tab.click((int(x), int(y)))
    return tab


def test_clicking_a_suite_dot_opens_its_box(window):
    tab = _open_box(window)
    assert tab.picked == ("d0100", 100.0, 7.0)
    window.draw()
    assert set(tab.popover_buttons) == {"watch", "branch"}
    _key(window, pygame.K_ESCAPE)  # closes the box, not the window
    assert tab.picked is None and not window.box


def test_a_click_elsewhere_closes_it(window):
    tab = _open_box(window)
    tab.click((tab.list_box.x + 5, tab.list_box.y + 5))
    assert tab.picked is None


def _release_on(window, tab, key):
    window.draw()
    center = tab.popover_buttons[key].center
    for kind in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
        window.handle(pygame.event.Event(kind, button=1, pos=center))


def test_watch_it_drive(window):
    tab = _open_box(window)
    _release_on(window, tab, "watch")
    label, argv = window.started[0]
    assert "agent:pupil@d0100" in argv


def test_branch_from_it_opens_the_training_tab(window):
    tab = _open_box(window)
    _release_on(window, tab, "branch")
    assert window.tab == "Training"
    form = window.training_tab.form.values()
    assert form["Start"] == "pupil@d0100" and form["Name"] == ""


# Comparing


def test_compare_lists_runs_of_the_same_kind(window):
    _folder(window.runs_tab.runs_dir, "2026-09-27_000000_x", kind="imitation")
    window.open_tab("Runs")
    tab = window.runs_tab
    tab.refresh(force=True)
    tab.select(RUN)
    names = [o[1] for o in tab._compare_options[1:]]
    assert names == [OTHER]  # not itself, not the imitation run


def test_a_compared_run_adds_muted_lines(window):
    window.open_tab("Runs")
    tab = window.runs_tab
    tab.select(RUN)
    tab._set_compare(("", OTHER))
    chart = tab._with_compare(
        tab.data.main_chart(), lambda c: c.main_chart(), ("line",)
    )
    tags = [s.label for s in chart.series]
    assert "pupil 01:48" in tags
    window.draw()


def test_the_box_widens_for_a_long_name(window):
    tab = _open_box(window)
    short = tab._popover_rect().w
    tab.data.who = "rookie-started-at-d1700k"
    wide = tab._popover_rect()
    title, _ = tab._popover_texts()
    from src.utils.ui import get_font
    from src.render import theme

    assert wide.w > short
    assert get_font(theme.TEXT_SIZE, True).size(title)[0] <= wide.w - 24
    assert tab.main_rect.contains(wide)
    window.draw()
