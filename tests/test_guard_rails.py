"""Guard rails (7h): bugs that come from features meeting each other.

- Every default a form offers is one of its own choices (a deleted
  suite stayed the Evaluate default).
- Every action, run with every choice its dropdowns offer, passes the
  app's argument check (a curriculum in a shared Stage list reached the
  recorder, which couldn't play one).
- Every make target's command passes it too.

Nothing runs: `app_checks.problems` checks the arguments only.
"""

import re
import subprocess
from pathlib import Path

import pytest
from absl import flags
from ml_collections import config_flags

import src.config  # noqa: F401  (defines the flags)
from src.app_checks import problems, stage_kind
from src.config import get_maze_car_config
from src.control.actions import ACTIONS
from src.control.training_plan import BOTH, FRESH, IMITATION, MODES, RL
from src.control.training_tab import form_fields

REPO = Path(__file__).resolve().parents[1]
if "maze_car" not in flags.FLAGS:  # as app.py defines them
    from src.config import get_agent_config

    config_flags.DEFINE_config_dict("agent", get_agent_config())
    config_flags.DEFINE_config_dict("maze_car", get_maze_car_config())
# Dropdowns whose every choice is a named file or a driver: checked one
# by one. Others (agents, runs, recordings) are tried at their default.
NAMED = {
    "Stage", "Rules", "Reward profile", "Trainer", "Imitation trainer",
    "Dataset", "Suite", "Model", "Driver",
}


def _check(args: list[str]) -> list[str]:
    """The app's check of these arguments, as `app.py` would run it."""
    values = flags.FLAGS
    values.unparse_flags()
    try:
        values(["app.py", *args])
        config = values.maze_car.copy_and_resolve_references()
        if values.stage:
            config.stage = values.stage
        if values.rules:
            config.rules = values.rules
        return problems(values, config)
    finally:
        values.unparse_flags()


def _options(field) -> list[str]:
    try:
        return [str(o) for o in field.options()] if field.options else []
    except Exception:  # noqa: BLE001 - a list that can't be read is a bug
        pytest.fail(f"{field.name}: its choices can't be read")


@pytest.mark.parametrize("action", ACTIONS, ids=lambda a: a.name)
def test_every_default_is_one_of_its_choices(action):
    for field in action.fields:
        options = _options(field)
        if options and field.default:
            assert field.default in options, (action.name, field.name)


@pytest.mark.parametrize("mode", MODES)
def test_the_training_forms_defaults_are_its_choices_too(mode):
    for start in (FRESH,):
        for field in form_fields(mode, "(new agent)", start):
            options = _options(field)
            if options and field.default:
                assert field.default in options, (mode, field.name)


def _filled(action) -> dict:
    """Each field at its default; an empty dropdown gets a stand-in."""
    values = {}
    for field in action.fields:
        options = _options(field)
        values[field.name] = field.default or (options[0] if options else "")
        if field.options and not values[field.name]:
            values[field.name] = "probe"  # nothing to pick yet
    return values


APP_ACTIONS = [a for a in ACTIONS if a.program == ("app.py",)]


@pytest.mark.parametrize("action", APP_ACTIONS, ids=lambda a: a.name)
def test_every_choice_of_every_action_passes_the_check(action):
    base = _filled(action)
    tried = 0
    for field in action.fields:
        if field.name not in NAMED:
            continue
        for option in _options(field):
            values = {**base, field.name: option}
            try:
                args = action.build(values)
            except (KeyError, ValueError):
                continue  # a value this action builds no command from
            assert _check(args) == [], (action.name, field.name, option)
            tried += 1
    if any(f.name in NAMED for f in action.fields):
        assert tried, action.name


SAMPLES = {"stage": "box", "mix": "basics", "curriculum": "skills"}


@pytest.mark.parametrize(
    "command",
    [
        ["-train", "probe"],
        ["-record_rounds", "heuristic"],
        ["-run", "probe", "--driver", "heuristic"],
        ["-demo", "maze_car", "--driver", "heuristic"],
    ],
    ids=lambda c: c[0],
)
def test_each_kind_of_stage_runs_or_is_refused_in_plain_words(command):
    for kind, name in SAMPLES.items():
        assert stage_kind(name) == kind
        found = _check([*command, "--stage", name])
        assert found == [] or (
            len(found) == 1 and f"is a {kind}" in found[0]
        ), (command, kind, found)
    assert _check([*command, "--stage", "box"]) == []  # a stage: always


def _make_targets() -> list[str]:
    text = (REPO / "Makefile").read_text()
    phony = re.search(r"^\.PHONY:(.*?)(?:\n\n|\n[^\t ])", text, re.S | re.M)
    return phony.group(1).replace("\\", " ").split()


PROBE = [
    "AGENT=probe", "STAGE=box", "FILE=probe.jsonl", "RUN=probe",
    "DRIVER=heuristic", "PLAYER=You", "REWARD=default", "RULES=standard",
    "SECONDS=60", "FPS=60", "EPISODES=10", "TRASH=probe",
]


def _plain(arg: str) -> str:
    """A config override as its plain flag (overrides register only as
    the app starts; the check sees the same values): --maze_car.stage=x
    is --stage=x. A display setting changes nothing checked: dropped.
    """
    for key in ("stage", "rules"):
        if arg.startswith(f"--maze_car.{key}="):
            return f"--{key}=" + arg.split("=", 1)[1]
    return "" if arg.startswith("--maze_car.display.") else arg


def test_every_make_target_passes_the_check():
    checked = 0
    for target in _make_targets():
        shown = subprocess.run(
            ["make", "-n", target, *PROBE],
            cwd=REPO, capture_output=True, text=True,
        )
        assert shown.returncode == 0, (target, shown.stderr)
        for line in shown.stdout.splitlines():
            if not line.startswith("python app.py"):
                continue
            args = [_plain(arg) for arg in line.split()[2:]]
            assert _check([a for a in args if a]) == [], (target, line)
            checked += 1
    assert checked > 40  # most targets run app.py
