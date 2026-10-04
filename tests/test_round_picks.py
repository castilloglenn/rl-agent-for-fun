"""Choosing which rounds an imitation teaches (roadmap 7g2): the dataset
takes only the ticked rounds, the facts and defaults behind the picker,
and the picker in the Training tab. Recordings here are hand-made in
tmp_path (only their header and end line are read): nothing touches
recordings/ or agents/.
"""

import json
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

from src.control.round_picks import (  # noqa: E402
    FactsCache,
    dataset_rounds,
    default_picks,
    lineage,
    read_facts,
    summary,
)
from src.experiments.datasets import (  # noqa: E402
    DatasetSpec,
    choose,
    load_dataset_spec,
    recording_paths,
)
from src.replay.format import (  # noqa: E402
    REPLAY_FORMAT,
    Replay,
    write_replay,
)

CORRECTIONS, NAVIGATOR = "Corrections", "Navigator"


def _round(root, player, stamp, stage="arena", watched="agent_4", spans=1):
    """A recording: a correction (watching an agent, `spans` takeovers of
    120 steps each) or, with watched="", a round you drove.
    """
    slot = (
        {"type": "agent", "id": watched, "checkpoint": "d1100k"}
        if watched
        else {"type": "human", "name": "You"}
    )
    end = {"step": 7200, "reason": "time", "scores": {"1": 1500.0}}
    if watched:
        end["takeovers"] = [[i * 1000, i * 1000 + 120] for i in range(spans)]
    name = f"2026-10-04_{stamp}_seed1_score1500_time.jsonl.gz"
    return write_replay(
        Replay(
            header={
                "format": REPLAY_FORMAT,
                "stage": {"name": stage},
                "slots": {"1": slot},
                "steps_per_second": 120,
            },
            end=end,
        ),
        root / player / name,
    )


def _agent(agents, name, parent=None):
    folder = agents / name
    folder.mkdir(parents=True)
    branched = {"agent": parent, "checkpoint": "d1"} if parent else None
    (folder / "profile.json").write_text(
        json.dumps({"id": name, "branched_from": branched})
    )


# The dataset takes only the ticked rounds


def test_only_filters_the_players_own_rounds_not_the_others(tmp_path):
    root = tmp_path / "recordings"
    mine = _round(root, CORRECTIONS, "100000")
    _round(root, CORRECTIONS, "110000")
    nav = _round(root, NAVIGATOR, "120000", watched="")
    spec = DatasetSpec(name="c", player=CORRECTIONS, also=(NAVIGATOR,))
    assert len(recording_paths(spec, root)) == 3
    chosen = choose(spec, [mine.name])
    assert recording_paths(chosen, root) == [mine, nav]
    assert DatasetSpec.from_dict(chosen.to_dict()) == chosen  # recorded
    assert "only" not in spec.to_dict()  # none chosen: as before


def test_the_command_check_refuses_rounds_that_arent_there(tmp_path):
    from tests.test_guard_rails import _check

    found = _check(
        ["-imitate", "x", "--dataset", "corrections", "--recordings",
         "nope.jsonl.gz"]
    )
    assert found == [
        "--recordings: nope.jsonl.gz isn't one of Corrections's rounds"
    ]


# Facts and defaults


def test_a_rounds_facts(tmp_path):
    path = _round(tmp_path, CORRECTIONS, "182536", "skill_gaps", spans=3)
    facts = read_facts(path)
    assert facts.watched == "agent_4@d1100k" and facts.takeovers == 3
    assert facts.yours == pytest.approx(3.0)  # 3 x 120 steps at 120/s
    assert facts.test_map and "Threading" in facts.test_map
    plain = read_facts(_round(tmp_path, "You", "190000", watched=""))
    assert not plain.correction and plain.yours == pytest.approx(60.0)
    assert read_facts(_round(tmp_path, "You", "200000", "box", "")).test_map is None


def test_the_line_and_the_defaults(tmp_path):
    agents = tmp_path / "agents"
    _agent(agents, "agent_1")
    _agent(agents, "agent_4", parent="agent_1")
    _agent(agents, "other")
    assert lineage("agent_4@d1100k", agents) == {"agent_4", "agent_1"}
    root = tmp_path / "recordings"
    rounds = [
        read_facts(_round(root, CORRECTIONS, "100000", "arena", "agent_4")),
        read_facts(_round(root, CORRECTIONS, "110000", "arena", "agent_1")),
        read_facts(_round(root, CORRECTIONS, "120000", "arena", "other")),
        read_facts(_round(root, CORRECTIONS, "130000", "skill_gaps")),
    ]
    picked = default_picks(rounds, lineage("agent_4", agents))
    assert picked == {rounds[0].name, rounds[1].name}  # not another
    # agent's mistakes, not a test map
    assert summary(rounds, picked) == "2 of 4 rounds · 2.0 s of your driving"


def test_the_dataset_rounds_newest_first(tmp_path):
    root = tmp_path / "recordings"
    old = _round(root, CORRECTIONS, "100000")
    new = _round(root, CORRECTIONS, "200000")
    found = dataset_rounds("corrections", root, FactsCache())
    assert [f.path for f in found] == [new, old]


# The picker in the Training tab


@pytest.fixture
def tab(tmp_path):
    from src.control.window import ControlCenter

    (tmp_path / "runs").mkdir()
    agents = tmp_path / "agents"
    _agent(agents, "agent_1")
    _agent(agents, "agent_4", parent="agent_1")
    root = tmp_path / "recordings"
    _round(root, CORRECTIONS, "100000", "arena", "agent_4")
    _round(root, CORRECTIONS, "110000", "skill_gaps", "agent_4")
    _round(root, CORRECTIONS, "120000", "arena", "someone")
    center = ControlCenter(runs_dir=tmp_path / "runs", agents_dir=agents)
    training = center.training_tab
    training.recordings_dir = root
    from src.control.training_plan import IMITATION, NEW_AGENT
    from src.control.training_tab import form_fields

    values = {
        **training.values(), "Mode": IMITATION, "Agent": NEW_AGENT,
        "Name": "fixed", "Start": "agent_4@d1100k",
        "Dataset": "corrections", "Imitation trainer": "correct",
    }
    training.form.build(
        form_fields(IMITATION, NEW_AGENT, "agent_4@d1100k", agents), values
    )
    training.show()
    yield training
    center.jobs.stop_all()


def _clone(training):
    return training.plan.steps[-1]


def test_the_plan_teaches_the_default_rounds(tab):
    tab.refresh(force=True)
    step = _clone(tab)
    assert "1 of 3 rounds of dataset corrections, 1.0 s" in step.text
    assert step.values["Recordings"].endswith("100000_seed1_score1500_time.jsonl.gz")
    assert "--recordings" in tab.plan.command_lines()[-1]
    assert tab.form.widgets["Rounds"].text.startswith("1 of 3 ticked")


def test_ticking_in_the_picker_changes_the_plan(tab):
    tab.open_picker()
    picker = tab.picker
    assert not tab.form.visible  # the box covers the form
    assert [r.stage for r in picker.shown()] == ["arena"]  # filtered
    picker.handle(_key(pygame.K_SPACE))  # untick the one shown
    assert picker.handle(_key(pygame.K_RETURN)) == "use"
    tab.close_picker(use=True)
    assert tab.picker is None and tab.form.visible
    assert tab.plan.blockers == [
        "No rounds of corrections ticked: choose some (Rounds)."
    ]


def test_filters_hide_but_keep_ticks_and_esc_drops_changes(tab):
    tab.open_picker()
    picker = tab.picker
    picker.handle(_button(picker.tests_button))  # test maps shown
    picker.handle(_button(picker.mine_button))  # every agent's
    assert len(picker.shown()) == 3
    picker.handle(_button(picker.all_button))
    picker.handle(_button(picker.tests_button))  # hidden again
    assert picker.hidden_picked == 1  # skill_gaps: hidden, still ticked
    assert tab.escape()  # Esc: closed, nothing kept
    tab.refresh(force=True)
    assert "1 of 3 rounds" in _clone(tab).text


def test_every_round_ticked_needs_no_list(tab):
    tab.open_picker()
    picker = tab.picker
    picker.picked = {r.name for r in picker.rounds}
    tab.close_picker(use=True)
    assert _clone(tab).values["Recordings"] == ""
    assert "--recordings" not in tab.plan.command_lines()[-1]


def _key(key):
    return pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode="")


def _button(element):
    import pygame_gui

    return pygame.event.Event(
        pygame_gui.UI_BUTTON_PRESSED, ui_element=element
    )


# The preview (7g3)


@pytest.fixture(scope="module")
def recorded(tmp_path_factory):
    """A real correction: watching an agent, you took over once, after
    more than 2 s (recorded once for these tests).
    """
    from src.replay.recordings import CORRECTIONS as FOLDER
    from tests.test_corrections import _play, _watch

    where = tmp_path_factory.mktemp("recorded")
    with pytest.MonkeyPatch.context() as monkeypatch:
        demo, held = _watch(where, monkeypatch)
        _play(demo, held, frames_mine=30, frames_its=200)
    (path,) = (where / "recordings" / FOLDER).glob("*.jsonl.gz")
    return path


def test_a_rounds_path_marks_your_stretches(recorded):
    from src.control.round_picks import PATH_EVERY, PathCache, RoundPath

    found = PathCache().wait(recorded)
    assert isinstance(found, RoundPath)
    (low, high) = found.takeovers[0]
    assert found.first_takeover == low
    assert len(found.points) >= found.total_steps // PATH_EVERY
    mine = [step for _, _, step in found.points if found.yours(step)]
    assert mine and all(low <= s < high for s in mine)
    assert found.stage["name"]


def test_a_round_that_cant_be_replayed_says_why(tmp_path):
    from src.control.round_picks import PathCache

    broken = tmp_path / "broken.jsonl.gz"
    broken.write_bytes(b"not a replay")
    assert "can't be re-played" in PathCache().wait(broken)


def test_watch_starts_two_seconds_before_your_first_takeover(
    tmp_path, recorded
):
    import pygame_gui  # noqa: F401
    from src.control.round_picks import RoundPath, read_facts
    from src.control.rounds_picker import RoundsPicker

    pygame.init()
    gui = pygame_gui.UIManager((1280, 820))
    asked = []
    facts = read_facts(recorded)
    picker = RoundsPicker(
        gui, pygame.Rect(0, 0, 1240, 690), "T", [facts], set(), set(),
        watch=lambda path, step: asked.append((path, step)),
    )
    picker.mine_only = False
    picker._label_buttons()
    assert isinstance(picker.paths.wait(recorded), RoundPath)
    picker.handle(_button(picker.watch_button))
    first = picker.paths.get(recorded).first_takeover
    assert asked == [(recorded, max(first - 240, 0))]
    assert picker.watch_button.text == "Watch from your first takeover"


def test_the_replay_window_starts_at_a_step(recorded):
    from src.config import get_maze_car_config
    from src.control.actions import ACTIONS
    from src.replay.viewer import ReplayViewer
    from tests.test_guard_rails import _check

    viewer = ReplayViewer.open(recorded, get_maze_car_config())
    viewer.seek(150)
    assert viewer.replayer.step_index == 150
    assert len(viewer.trail) > 1  # the way there is drawn
    watch = next(a for a in ACTIONS if a.name == "Watch a replay")
    args = watch.build({"File": str(recorded), "From step": "150"})
    assert args[-2:] == ["--replay_step", "150"]
    assert _check(args) == []
    assert watch.build({"File": "x", "From step": ""}) == ["-replay", "x"]
