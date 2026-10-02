"""The control center's Training tab: plans, chains, and the form (step
6b2). Nothing here trains: chains run tiny python commands, and the tab
is checked without pressing Start on a real plan.
"""

import json
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

from src.control.chains import CANCELLED, DONE, FAILED, Chain  # noqa: E402
from src.control.jobs import JobManager  # noqa: E402
from src.control.training_plan import (  # noqa: E402
    BOTH,
    FRESH,
    IMITATION,
    NEW_AGENT,
    RL,
    busy_agents,
    make_plan,
)
from src.control.training_tab import form_fields  # noqa: E402
from tests.test_control import _wait  # noqa: E402
from tests.test_runs_tab import _folder, _job  # noqa: E402

GAME = {
    "Trainer": "default",
    "Stage": "box",
    "Rules": "standard",
    "Round seconds": "",
    "Reward profile": "default",
    "Seed": "0",
}


def _values(mode=RL, agent=NEW_AGENT, **more):
    values = {"Mode": mode, "Agent": agent, **GAME}
    if agent == NEW_AGENT:
        values.update(Name="rookie2", Start=FRESH, Model="small")
    if mode in (IMITATION, BOTH):
        values.update(Dataset="mine")
        values["Imitation trainer"] = "imitate"
    return {**values, **more}


def _plan(values, agents=("rookie",), busy=None, runs_dir=None, **kw):
    return make_plan(values, list(agents), busy or {}, runs_dir, **kw)


# Plans


def test_rl_for_a_new_agent_creates_it_first(tmp_path):
    plan = _plan(_values(), runs_dir=tmp_path)
    assert [s.action for s in plan.steps] == ["Create an agent", "Train"]
    assert plan.agent == "rookie2" and not plan.blockers
    create, train = plan.command_lines()
    assert "-new_agent rookie2 --seed 0 --model small" in create
    assert "-train rookie2 --trainer default --seed 0" in train


def test_a_branch_starts_from_the_checkpoint(tmp_path):
    plan = _plan(_values(Start="rookie@d1700k"), runs_dir=tmp_path)
    assert "branched from rookie@d1700k" in plan.steps[0].text
    assert "--from rookie@d1700k" in plan.command_lines()[0]


def test_an_existing_agent_skips_creating(tmp_path):
    plan = _plan(_values(agent="rookie"), runs_dir=tmp_path)
    assert [s.action for s in plan.steps] == ["Train"]
    plan = _plan(_values(BOTH, agent="rookie"), runs_dir=tmp_path)
    assert [s.action for s in plan.steps] == ["Clone your driving", "Train"]
    plan = _plan(_values(IMITATION), runs_dir=tmp_path)
    assert [s.action for s in plan.steps] == [
        "Create an agent",
        "Clone your driving",
    ]


def test_what_blocks_starting(tmp_path):
    def blockers(**kw):
        return _plan(_values(**kw), runs_dir=tmp_path).blockers

    assert blockers(Name="") == ["Needs a name for the new agent."]
    assert "letters, digits" in blockers(Name="my agent")[0]
    assert "already exists" in blockers(Name="rookie")[0]
    assert blockers(Seed="x") == ["Seed must be a whole number."]
    assert "Round seconds" in blockers(**{"Round seconds": "soon"})[0]
    busy = _plan(
        _values(agent="rookie"), busy={"rookie": "run r"}, runs_dir=tmp_path
    )
    assert busy.blockers == ["rookie is training right now (run r)."]
    empty = _plan(_values(IMITATION), runs_dir=tmp_path, recordings=0)
    assert "no recordings yet" in empty.blockers[0]


def test_on_battery_warns(tmp_path):
    plan = _plan(_values(), runs_dir=tmp_path, on_battery=True)
    assert plan.warnings[0].startswith("On battery")


def test_the_estimate_comes_from_past_runs(tmp_path):
    assert _plan(_values(), runs_dir=tmp_path).estimate == "no estimate"
    _folder(tmp_path, "a", summary={"seconds": 100.0, "decisions": 400_000})
    _folder(tmp_path, "b", summary={"seconds": 200.0, "decisions": 600_000})
    plan = _plan(_values(), runs_dir=tmp_path)
    # 300 s per 1M decisions, and the default trainer runs 2M: 10 min.
    assert plan.estimate == "about 10 min"
    assert plan.basis == "the pace of your last 2 training runs"
    # Imitation then RL, without a past imitation run: RL alone.
    plan = _plan(_values(BOTH), runs_dir=tmp_path)
    assert plan.estimate == "about 10 min"


def test_busy_agents_from_live_runs(tmp_path):
    _folder(tmp_path, "live")
    from src.control.runs import scan

    rows = scan(tmp_path, [_job(run="live")])
    assert busy_agents(rows) == {"pupil": "live"}


# The form's fields follow the mode


def test_the_fields_follow_the_mode():
    def names(*args):
        return [f.name for f in form_fields(*args)]

    assert names(RL, NEW_AGENT, FRESH)[:5] == [
        "Mode", "Agent", "Name", "Start", "Model",
    ]
    assert "Model" not in names(RL, NEW_AGENT, "rookie@d1700k")
    imitation = names(IMITATION, "rookie", FRESH)
    assert "Dataset" in imitation and "Trainer" not in imitation
    assert "Seed" not in imitation  # neither weights nor episodes
    both = names(BOTH, "rookie", FRESH)
    assert "Dataset" in both and "Trainer" in both


# Chains


def _python(code: str) -> list[str]:
    return [sys.executable, "-c", code]


def _chain(tmp_path, codes):
    jobs = JobManager(cwd=tmp_path)
    said = []

    def start(code, i, n):
        return jobs.start(f"step {i + 1}/{n}", _python(code))

    chain = Chain(codes, start, say=lambda job, line: said.append(line))
    return jobs, chain, said


def _run(chain, seconds=10.0):
    def tick():
        chain.tick()
        return not chain.active

    assert _wait(tick, seconds)


def test_a_chain_runs_its_steps_in_order(tmp_path):
    marker = tmp_path / "order.txt"
    codes = [
        f"open({str(marker)!r}, 'a').write('{i}')" for i in range(3)
    ]
    jobs, chain, _ = _chain(tmp_path, codes)
    _run(chain)
    assert chain.state == DONE and len(chain.jobs) == 3
    assert marker.read_text() == "012"


def test_a_failed_step_cancels_the_rest(tmp_path):
    jobs, chain, said = _chain(tmp_path, ["raise SystemExit(3)", "pass"])
    _run(chain)
    assert chain.state == FAILED and len(chain.jobs) == 1
    assert "won't run" in said[0]


def test_stopping_a_step_cancels_the_rest(tmp_path):
    jobs, chain, said = _chain(
        tmp_path, ["import time; time.sleep(30)", "pass"]
    )
    chain.tick()
    jobs.stop(chain.job)
    _run(chain)
    assert chain.state == CANCELLED and len(chain.jobs) == 1


def test_a_chain_follows_its_newest_run(tmp_path):
    jobs, chain, _ = _chain(
        tmp_path, ["print('Run: first')", "print('Run: second')"]
    )
    _run(chain)
    assert chain.run == "second"


# The tab in the window


@pytest.fixture
def window(tmp_path):
    from src.control.window import ControlCenter

    (tmp_path / "runs").mkdir()
    center = ControlCenter(runs_dir=tmp_path / "runs")
    yield center
    center.jobs.stop_all()


def test_the_training_tab_opens(window):
    window.handle(
        pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            button=1,
            pos=window.tab_rects["Training"].center,
        )
    )
    assert window.tab == "Training"
    tab = window.training_tab
    assert tab.form.widgets["Mode"].visible
    assert not window.runs_tab.run_list.visible
    window.draw()
    window.open_tab("Commands")
    assert not tab.form.widgets["Mode"].visible


def test_start_is_disabled_while_blocked(window):
    window.open_tab("Training")
    tab = window.training_tab
    assert tab.values()["Name"].startswith("agent_")  # suggested
    tab.form.widgets["Name"].set_text("")  # no name
    tab.refresh(force=True)
    assert tab.plan.blockers
    assert not tab.start_button.is_enabled
    tab.form.widgets["Name"].set_text("brand_new_agent")
    tab.refresh(force=True)
    assert not tab.plan.blockers and tab.start_button.is_enabled


def test_start_runs_the_plan_as_a_chain(window, monkeypatch):
    started = []

    def start(label, argv):
        started.append((label, argv))
        return _job()

    monkeypatch.setattr(window.jobs, "start", start)
    window.open_tab("Training")
    tab = window.training_tab
    tab.form.widgets["Name"].set_text("brand_new_agent")
    tab.start()
    label, argv = started[0]
    assert label == "Create an agent: brand_new_agent (1/2)"
    assert argv[1:] == [
        "app.py", "-new_agent", "brand_new_agent", "--seed", "0",
        "--model", "small",
    ]
    assert window.tab == "Runs"  # it follows the new run
    assert window.runs_tab.follow is window.chains[0]
    assert "brand_new_agent" in window._chain_agents()


def test_the_next_step_starts_once(window, monkeypatch):
    """Starting a step refreshes the window, which ticks the chains: the
    chain must not start its step again from inside that tick (it once
    started 141 trainings in 4 s, until a RecursionError).
    """
    started = []

    def start(label, argv):
        started.append(label)
        if len(started) > 5:
            raise AssertionError(f"started {len(started)} jobs")
        return _job()

    monkeypatch.setattr(window.jobs, "start", start)
    window.open_tab("Training")
    tab = window.training_tab
    tab.form.widgets["Name"].set_text("brand_new_agent")
    tab.start()
    first = window.chains[0].job
    first.process.alive, first.process.returncode = False, 0
    window._refresh(force=True)
    assert started == [
        "Create an agent: brand_new_agent (1/2)",
        "Train: brand_new_agent (2/2)",
    ]


def test_mode_changes_rebuild_the_form(window):
    window.open_tab("Training")
    tab = window.training_tab
    tab.form.build(
        form_fields(BOTH, "rookie", FRESH), {"Mode": BOTH, "Agent": "rookie"}
    )
    assert "Dataset" in tab.form.widgets
    assert tab.values()["Mode"] == BOTH


def test_runs_written_here_are_json(tmp_path):
    # The estimate reads summaries; a broken one is skipped, not fatal.
    folder = _folder(tmp_path, "x")
    (folder / "summary.json").write_text("{not json")
    assert _plan(_values(), runs_dir=tmp_path).estimate == "no estimate"
    assert json.loads((folder / "config.json").read_text())["kind"]


def test_a_mode_picked_just_before_a_refresh_rebuilds_the_form(window):
    """A pick changes the dropdown at once; its change event comes a
    frame later. A refresh in between read "Imitation, then RL" with no
    Dataset field yet (KeyError, the control center closed). Now the
    form is rebuilt for the pick first.
    """
    from src.control.training_plan import BOTH

    window.open_tab("Training")
    tab = window.training_tab
    tab.form.widgets["Mode"].selected_option = (BOTH, BOTH)  # just picked
    tab.refresh(force=True)  # before its change event: no crash
    values = tab.values()
    assert values["Mode"] == BOTH and "Dataset" in values
    assert tab.plan.steps[-1].action == "Train"


def test_a_new_agent_is_named_the_next_agent_n(tmp_path):
    """agent_1 with none yet, then the next free number; yours to change."""
    from src.control.training_tab import next_agent_name

    agents = tmp_path / "agents"
    assert next_agent_name(agents) == "agent_1"
    for name in ("agent_1", "agent_3", "rookie", "agent_x"):
        (agents / name).mkdir(parents=True)
    assert next_agent_name(agents) == "agent_4"


def test_the_form_suggests_it_and_moves_on_once_its_taken(tmp_path):
    from src.control.window import ControlCenter

    (tmp_path / "runs").mkdir()
    agents = tmp_path / "agents"
    center = ControlCenter(runs_dir=tmp_path / "runs", agents_dir=agents)
    tab = center.training_tab
    tab.rebuild()
    assert tab.values()["Name"] == "agent_1"
    (agents / "agent_1").mkdir(parents=True)  # created meanwhile
    tab.rebuild()
    assert tab.values()["Name"] == "agent_2"
    tab.form.widgets["Name"].set_text("rookie")  # yours stays yours
    tab.rebuild()
    assert tab.values()["Name"] == "rookie"
    center.jobs.stop_all()
