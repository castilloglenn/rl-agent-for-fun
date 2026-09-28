"""Decision 030: units and tooltips. The help texts must cover every
field there is, and point at nothing that isn't (read-only on the repo).
"""

import os
import re

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

from src.control import files, help  # noqa: E402
from src.control.actions import ACTIONS  # noqa: E402
from src.control.agents_data import SKILLS  # noqa: E402
from src.control.runs import (  # noqa: E402
    EPISODE_CHARTS,
    IMITATION_CHARTS,
    STATUS_COLORS,
    TRAINING_CHARTS,
)
from src.control.tooltips import DELAY, Tooltips  # noqa: E402
from src.control.training_plan import BOTH, FRESH, NEW_AGENT  # noqa: E402
from src.control.training_tab import form_fields  # noqa: E402
from src.envs.maze_car.rewards import TERMS  # noqa: E402


def _generic(path: str) -> str:
    return re.sub(r"\.\d+(\.|$)", r".*\1", path)


def test_every_file_field_has_help():
    for kind in files.KINDS:
        for name in files.names(files.REPO / kind.folder):
            data = files.load(files.REPO, kind, name)
            for item in files.items(kind.folder, data):
                _, text = help.field(kind.folder, item.path)
                assert text, f"{kind.folder}/{name}: {item.path}"


def test_every_help_key_is_a_real_field():
    paths = {}
    for kind in files.KINDS:
        found = paths.setdefault(kind.folder, set())
        for name in files.names(files.REPO / kind.folder):
            data = files.load(files.REPO, kind, name)
            for item in files.items(kind.folder, data):
                found.add(item.path)
                found.add(_generic(item.path))
    for folder, table in help.FIELDS.items():
        for key in table:
            assert key in paths[folder], f"{folder}: {key}"


def test_reward_terms_and_their_parameters():
    assert set(help.TERMS) == set(TERMS)
    for key in help.TERM_PARAMS:
        term, param = key.split(".")
        assert param in TERMS[term].params


def test_units_where_they_belong():
    assert help.field("rules", "round_seconds")[0] == "s"
    assert help.field("rules", "collisions.safe_speed")[0] == "px/s"
    assert help.field("suites", "scenarios.1.start.max_angle")[0] == "°"
    assert help.field("rewards", "terms.contact")[0] == "per contact"
    assert help.field("rewards", "terms.checkpoint_speed.window")[0] == "s"
    assert help.field("rules", "name")[0] == ""
    assert help.form("Round seconds")[0] == "s"


def test_every_form_field_has_help():
    names = {f.name for action in ACTIONS for f in action.fields}
    names |= {f.name for f in form_fields(BOTH, NEW_AGENT, FRESH)}
    for name in names:
        assert help.form(name)[1], name


def test_every_topic_the_tabs_ask_for_exists():
    options = [name for name, _ in TRAINING_CHARTS + IMITATION_CHARTS]
    options += [name for name, _ in EPISODE_CHARTS]
    keys = [f"chart:{o}" for o in options]
    keys += ["chart:score", "chart:accuracy", "chart:episodes"]
    keys += [f"status:{s}" for s in STATUS_COLORS]
    keys += [f"skill:{label}" for label, _, _ in SKILLS]
    keys += [f"column:{c}" for c in ("#", "score", "survive", "wrecks")]
    keys += [f"column:{c}" for c in ("cp/min", "brake", "best")]
    keys += [f"badge:{b}" for b in ("TRAINING", "MILESTONE", "BRANCHED")]
    keys += ["badge:FROM YOUR DRIVING", "skills", "history", "estimate"]
    keys += [f"stat:{s}" for s in ("CPU", "MEMORY", "BATTERY", "DISK")]
    keys += ["stat:JOBS", "compare", "high scores", "heuristic ratio"]
    keys += ["legend:suite", "legend:best", "legend:heuristic"]
    from src.control.recordings_view import COLUMNS

    keys += [f"recording:{name}" for name, _, _, _ in COLUMNS]
    for key in keys:
        assert help.topic(key), key


# The tooltip itself


def test_a_tooltip_opens_after_resting_and_closes_on_leaving():
    pygame.init()
    surface = pygame.Surface((800, 600))
    tips = Tooltips()
    target = pygame.Rect(100, 100, 80, 20)

    def frame(mouse, seconds, blocked=False):
        tips.begin()
        tips.add(target, "What it means.")
        return tips.draw(surface, mouse, seconds, blocked)

    assert frame((110, 110), DELAY / 2) is None  # not yet
    assert frame((110, 110), DELAY) == "What it means."
    assert frame((300, 300), 1.0) is None  # left it
    assert frame((110, 110), 0.1) is None  # the wait starts over
    assert frame((110, 110), 1.0, blocked=True) is None  # a box is open


def test_a_label_gets_a_marker_only_with_help():
    pygame.init()
    surface = pygame.Surface((400, 100))
    tips = Tooltips()
    with_help = tips.label(surface, "gamma", (10, 10), "Future reward.")
    without = tips.label(surface, "gamma", (10, 40), "")
    assert with_help.w > without.w  # the marker
    assert len(tips.targets) == 1


def test_the_window_shows_a_tooltip(monkeypatch, tmp_path):
    from src.control.window import ControlCenter

    center = ControlCenter(runs_dir=tmp_path, agents_dir=tmp_path)
    center.draw()
    rect, text = center.tips.targets[0]  # the vital signs strip
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: rect.center)
    center._frame_seconds = DELAY
    center.draw()
    center.draw()
    assert center.tips._since >= DELAY and "CPU" in text
    center.jobs.stop_all()
