"""Step 6c: the Agents tab, its data, and deleting an agent into the
trash. Every folder here is in tmp_path: nothing touches agents/, runs/,
recordings/, or trash/.
"""

import gzip
import json
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

from src.control import agents_data  # noqa: E402
from src.control.trash import Trash, TrashError  # noqa: E402
from tests.test_runs_tab import _folder, _job  # noqa: E402

BEST = {
    "suite": "skills-v1",
    "share": 2.0,
    "score_mean": 5000.0,
    "score_min": 4000.0,
    "checkpoints_per_min": 30.0,
    "survival": 1.0,
    "wreck_rate": 0.1,
    "contacts": 1.0,
    "braking": 0.8,
}
HEURISTIC = {
    **BEST, "share": 1.0, "score_mean": 2500.0, "checkpoints_per_min": 15.0,
}


def _agent(root, name, best=None, branched=None, phases=(), created="1"):
    folder = root / "agents" / name
    (folder / "evaluations").mkdir(parents=True)
    (folder / "model.json").write_text('{"name": "small"}')
    profile = {
        "id": name,
        "model": {"name": "small", "hidden": [64, 64]},
        "created": f"2026-09-2{created}T00:00:00+08:00",
        "decisions": 1000,
        "training": {"seconds": 120.0},
        "branched_from": branched,
        "phases": list(phases),
        "checkpoints": {"best": "d0001k" if best else None},
        "best": best,
        "milestone": None,
    }
    (folder / "profile.json").write_text(json.dumps(profile))
    return folder


def _baselines(root):
    folder = root / "agents" / "baselines"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "skills-v1.json").write_text(
        json.dumps({"scores": {"heuristic": HEURISTIC}})
    )


# The data


def test_skills_run_from_zero_to_one():
    refs = {"score_mean": 5000.0, "checkpoints_per_min": 30.0}
    values = agents_data.skills(BEST, refs)
    labels = [label for label, _, _ in agents_data.SKILLS]
    by = dict(zip(labels, values))
    assert by["Score"] == 1.0 and by["Hunting"] == 1.0
    assert by["Intact"] == pytest.approx(0.9)  # 10 % wrecks
    assert by["Clean"] == pytest.approx(0.5)  # one contact a round
    assert all(0 <= v <= 1 for v in agents_data.skills({}, refs))


def test_the_leaderboard_ranks_agents_and_places_the_baselines(tmp_path):
    _agent(tmp_path, "low", {**BEST, "share": 0.4, "score_mean": 9000.0})
    _agent(tmp_path, "high", BEST)
    _agent(tmp_path, "unscored")
    _baselines(tmp_path)
    agents = agents_data.load_agents(tmp_path / "agents")
    assert [a.id for a in agents] == ["high", "low", "unscored"]
    base = agents_data.baselines(tmp_path / "agents")
    ranks = agents_data.leaderboard(agents, base)
    names = [r.name for r in ranks]
    assert names == ["high", "(heuristic)", "low", "unscored"]
    assert [r.place for r in ranks] == [1, None, 2, None]
    assert agents_data.place_of("low", ranks) == 2


def test_sorting_the_roster(tmp_path):
    _agent(tmp_path, "b", {**BEST, "share": 0.1}, created="1")
    _agent(tmp_path, "a", BEST, created="2")
    agents = agents_data.load_agents(tmp_path / "agents")

    def ids(by):
        return [a.id for a in agents_data.sort_agents(agents, by)]

    assert ids("score") == ["a", "b"]
    assert ids("newest") == ["a", "b"]
    assert ids("name") == ["a", "b"]


def test_badges(tmp_path):
    _agent(
        tmp_path,
        "kid",
        branched={"agent": "gone", "checkpoint": "d0001k"},
        phases=[{"kind": "imitation", "run": "r", "dataset": {}}],
    )
    (agent,) = agents_data.load_agents(tmp_path / "agents", {"kid": "r"})
    assert agent.badges() == ["TRAINING", "BRANCHED", "FROM YOUR DRIVING"]


def test_lineage_marks_what_was_deleted(tmp_path):
    phase = {
        "kind": "rl", "run": "gone_run", "trainer": "default",
        "stage": "box", "rules": "standard", "start_decisions": 0,
        "end_decisions": 1000, "status": "done",
    }
    _agent(
        tmp_path,
        "kid",
        branched={"agent": "parent", "checkpoint": "d0001k"},
        phases=[phase],
    )
    (agent,) = agents_data.load_agents(tmp_path / "agents")
    start, run = agents_data.lineage(agent, {"kid"}, tmp_path / "runs")
    assert start.text == "Branched from parent@d0001k (deleted)"
    assert run.text.endswith("(done) (run deleted)") and run.run is None


def test_history_reads_the_suite_results(tmp_path):
    folder = _agent(tmp_path, "a", BEST)
    (folder / "evaluations" / "skills-v1.csv").write_text(
        "checkpoint,decisions,score_mean\nd2,200,9\nd1,100,5\n"
    )
    (agent,) = agents_data.load_agents(tmp_path / "agents")
    rows = agents_data.history(agent)
    assert [r["checkpoint"] for r in rows] == ["d1", "d2"]


def test_high_scores_from_runs_and_recordings(tmp_path):
    folder = _folder(tmp_path / "runs", "r1", summary={"best_score": 900})
    config = json.loads((folder / "config.json").read_text())
    config["stage"] = {"name": "box"}
    config["rules"] = {"name": "standard", "round_seconds": 60}
    (folder / "config.json").write_text(json.dumps(config))
    recordings = tmp_path / "recordings" / "You"
    recordings.mkdir(parents=True)
    header = {"stage": {"name": "box"},
              "rules": {"name": "standard", "round_seconds": 60}}
    path = recordings / "2026-09-27_000000_seed1_score1200_time.jsonl.gz"
    with gzip.open(path, "wt") as file:
        file.write(json.dumps(header) + "\n")
    scores = agents_data.high_scores(
        tmp_path / "runs", tmp_path / "recordings"
    )
    (key,) = scores
    assert key == "box / standard, 60 s rounds"
    assert [(s.score, s.who) for s in scores[key]] == [
        (1200.0, "You"),
        (900.0, "pupil"),
    ]


# Deleting an agent


def _runs_of(tmp_path):
    runs_dir = tmp_path / "runs"
    done = {"interrupted": False}
    _folder(runs_dir, "t1", summary=done)  # its training run (pupil)
    other = _folder(runs_dir, "t2", summary=done)
    config = json.loads((other / "config.json").read_text())
    config["agent"]["id"] = "someone_else"
    (other / "config.json").write_text(json.dumps(config))
    drove = _folder(runs_dir, "e1", kind=None, summary=done)
    config = json.loads((drove / "config.json").read_text())
    config["driver"] = {"type": "agent", "id": "pupil", "checkpoint": None}
    (drove / "config.json").write_text(json.dumps(config))


def test_deleting_an_agent_takes_its_runs(tmp_path):
    _agent(tmp_path, "pupil", BEST)
    _agent(tmp_path, "kid", branched={"agent": "pupil", "checkpoint": "x"})
    _runs_of(tmp_path)
    trash = Trash(tmp_path)
    plan = trash.agent_plan("pupil")
    assert [p.name for p in plan.runs] == ["e1", "t1"]
    assert plan.children == ["kid"]
    entry = trash.delete_agent("pupil")
    assert entry.kind == "agent"
    assert sorted(entry.paths) == ["agents/pupil", "runs/e1", "runs/t1"]
    assert (tmp_path / "agents" / "kid").exists()  # kept
    assert (tmp_path / "runs" / "t2").exists()  # someone else's
    trash.restore(entry.name)
    assert (tmp_path / "agents" / "pupil" / "profile.json").exists()
    assert (tmp_path / "runs" / "e1").exists()


def test_deleting_an_agent_with_a_live_run_is_refused(tmp_path):
    _agent(tmp_path, "pupil", BEST)
    live = _folder(tmp_path / "runs", "t1")
    (live / "training.lock").write_text(str(os.getpid()))
    with pytest.raises(TrashError, match="still running"):
        Trash(tmp_path).delete_agent("pupil")
    with pytest.raises(TrashError, match="no agent"):
        Trash(tmp_path).delete_agent("nobody")


# The tab


@pytest.fixture
def window(tmp_path):
    from src.control.window import ControlCenter

    _agent(tmp_path, "pupil", BEST, created="2")
    _agent(tmp_path, "second", {**BEST, "score_mean": 10.0}, created="1")
    _baselines(tmp_path)
    (tmp_path / "runs").mkdir()
    center = ControlCenter(
        runs_dir=tmp_path / "runs", agents_dir=tmp_path / "agents"
    )
    started = []

    def start(label, argv):
        started.append(argv)
        return _job()

    center.jobs.start = start
    center.started = started
    center.open_tab("Agents")
    yield center


def test_the_agents_tab_shows_cards_and_selects_the_best(window):
    tab = window.agents_tab
    assert tab.selected == "pupil"
    window.draw()
    assert [agent for _, agent in tab.hit] == ["pupil", "second"]
    rect = tab.hit[1][0]
    tab.click(rect.center)
    assert tab.selected == "second"


def test_the_leaderboard_view_selects_by_row(window):
    tab = window.agents_tab
    tab.view = "Leaderboard"
    window.draw()
    assert [agent for _, agent in tab.hit] == ["pupil", "second"]


def test_the_buttons_start_actions(window):
    tab = window.agents_tab
    tab.press("Watch best")
    assert "agent:pupil" in window.started[-1]
    argv = window.started[-1]
    assert argv[argv.index("--stage") + 1] == "box"  # no training phase


def test_watch_best_uses_its_newest_trainings_stage(window):
    tab = window.agents_tab
    tab.agent.profile["phases"] = [
        {"kind": "rl", "stage": "pillars"},
        {"kind": "rl", "stage": "arena"},
        {"kind": "imitation"},
    ]
    window.draw()
    assert any("on arena" in text for _, text in window.tips.targets)
    tab.press("Watch best")
    argv = window.started[-1]
    assert argv[argv.index("--stage") + 1] == "arena"
    tab.agent.profile["phases"] = [{"kind": "rl", "stage": "gone_map"}]
    tab.press("Watch best")
    argv = window.started[-1]
    assert argv[argv.index("--stage") + 1] == "box"  # its file is gone
    tab.press("Showcase")
    assert window.started[-1][-2:] == ["-showcase", "pupil"]
    tab.press("Evaluate")
    assert "-eval" in window.started[-1]


def test_train_more_and_branch_best_open_the_training_tab(window):
    window.agents_tab.press("Train more")
    assert window.tab == "Training"
    assert window.training_tab.values()["Agent"] == "pupil"
    window.open_tab("Agents")
    window.agents_tab.press("Branch best")
    assert window.training_tab.values()["Start"] == "pupil@d0001k"


def test_delete_agent_asks_first(window):
    window.agents_tab.press("Delete agent")
    assert window.box.title == "DELETE AN AGENT?"
    window.handle(
        pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)
    )
    assert window.box is None and window.started == []
