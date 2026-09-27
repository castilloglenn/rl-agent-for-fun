"""The control center: make commands, jobs, and the window (step 6a).

Only read-only commands run here (listings), so nothing is written into
agents/, runs/, or recordings/.
"""

import os
import re
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402
import pygame_gui  # noqa: E402
import pytest  # noqa: E402

from src.control import choices  # noqa: E402
from src.control.jobs import JobManager  # noqa: E402
from src.control.makefile import MAKEFILE, read_commands  # noqa: E402

COMMANDS = {command.name: command for command in read_commands()}


def _wait(predicate, seconds=10.0):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


# The Makefile is the one list of commands


def test_every_make_target_is_a_command():
    text = MAKEFILE.read_text()
    phony = re.search(r"\.PHONY:(.*?)\n\n", text, re.S).group(1)
    targets = set(phony.replace("\\\n", " ").split())
    assert set(COMMANDS) == targets - {"help", "control"}


def test_commands_have_their_group_description_and_params():
    train = COMMANDS["train"]
    assert train.group == "Agents"
    assert train.description.startswith("train an agent")
    assert [(p.name, p.example) for p in train.params] == [
        ("AGENT", "my_agent")
    ]
    assert COMMANDS["maze_car"].params == ()


def test_argv_fills_in_the_params():
    argv = COMMANDS["run_reward"].argv({"REWARD": "time_bonus"})
    assert argv[0] == sys.executable
    assert argv[1:] == [
        "app.py",
        "-run",
        "heuristic-time_bonus",
        "--driver",
        "heuristic",
        "--reward",
        "time_bonus",
    ]
    assert COMMANDS["test"].argv({})[1:] == ["-m", "pytest"]


def test_a_missing_param_says_how():
    with pytest.raises(ValueError, match=r"needs AGENT \(e.g. make train "):
        COMMANDS["train"].argv({})


def test_window_or_headless():
    assert COMMANDS["maze_car"].opens_window
    assert COMMANDS["showcase"].opens_window
    assert COMMANDS["replay_last"].opens_window
    assert not COMMANDS["train"].opens_window
    assert not COMMANDS["runs"].opens_window


def test_make_line():
    line = COMMANDS["train"].make_line({"AGENT": "rookie"})
    assert line == "make train AGENT=rookie"


# Choices


def test_param_choices():
    assert choices.options("new_agent", "AGENT") is None  # a new name
    assert choices.options("maze_car_player", "PLAYER") is None
    assert "keyboard" in choices.options("maze_car_driver", "DRIVER")
    assert "keyboard" not in choices.options("run_driver", "DRIVER")
    assert "standard" in choices.options("maze_car_rules", "RULES")
    assert "default" in choices.options("maze_car_reward", "REWARD")
    assert "tests/test_control.py" in choices.options("test_file", "FILE")


# Jobs


def _counter(manager, count=200):
    code = (
        "import time\n"
        f"for i in range({count}):\n"
        "    print(i, flush=True)\n"
        "    time.sleep(0.02)\n"
    )
    return manager.start("counter", [sys.executable, "-c", code])


def test_a_job_captures_its_output():
    manager = JobManager()
    job = manager.start("hello", [sys.executable, "-c", "print('hi')"])
    assert _wait(lambda: job.status == "done")
    assert _wait(lambda: job.log and job.log[-1].startswith("(exited"))
    assert "hi" in job.log


def test_pause_and_resume():
    manager = JobManager()
    job = _counter(manager)
    assert _wait(lambda: len(job.log) > 2)
    manager.pause(job)
    time.sleep(0.2)
    lines = len(job.log)
    time.sleep(0.3)
    assert job.status == "paused" and len(job.log) == lines
    manager.resume(job)
    assert _wait(lambda: len(job.log) > lines + 2)
    manager.stop(job)
    assert _wait(lambda: job.status == "stopped")


def test_stop_is_ctrl_c():
    manager = JobManager()
    code = (
        "import time\n"
        "try:\n"
        "    time.sleep(30)\n"
        "except KeyboardInterrupt:\n"
        "    print('saved', flush=True)\n"
    )
    job = manager.start("sleeper", [sys.executable, "-c", code])
    time.sleep(0.5)
    manager.stop(job)
    assert _wait(lambda: job.status == "stopped")
    assert _wait(lambda: "saved" in job.log)  # it cleaned up like Ctrl+C


def test_stop_all_and_clear():
    manager = JobManager()
    jobs = [_counter(manager) for _ in range(2)]
    assert _wait(lambda: all(len(j.log) > 1 for j in jobs))
    manager.stop_all()
    assert manager.running == []
    manager.clear_finished()
    assert manager.jobs == []


# Actions: the commands, consolidated

from src.config import get_maze_car_config  # noqa: E402
from src.control.actions import (  # noqa: E402
    ACTIONS,
    ALL_TESTS,
    BASELINES_ONLY,
    MAKE_TARGETS,
    NEWEST_STOPPED,
    NONE,
)

BY_NAME = {action.name: action for action in ACTIONS}


def _values(action, **changes):
    """Every field at its default (or a stand-in), with some changed."""
    values = {f.name: f.default or "x" for f in action.fields}
    return {**values, **changes}


def _args(name, **changes):
    action = BY_NAME[name]
    return action.argv(_values(action, **changes))[2:]  # after app.py


def test_every_make_target_is_covered_by_an_action():
    assert set(MAKE_TARGETS) == set(COMMANDS)
    for target, action in MAKE_TARGETS.items():
        assert action is None or action in BY_NAME, target


def test_fewer_actions_than_make_targets():
    assert len(ACTIONS) < len(COMMANDS) / 2  # consolidated


def test_every_action_uses_real_flags():
    from absl import flags

    import src.config  # noqa: F401  (defines the flags)

    config = get_maze_car_config()
    for action in ACTIONS:
        if action.program != ("app.py",):
            continue
        for token in action.argv(_values(action))[2:]:
            if not token.startswith("-"):
                continue
            name = token.lstrip("-").split("=")[0]
            if name.startswith("maze_car."):
                keys = name.split(".")[1:]
                assert config[keys[0]][keys[1]] is not None, token
            else:
                assert name in flags.FLAGS, (action.name, token)


def test_drive_options():
    args = _args("Drive", **{"Round seconds": "", "FPS cap": "0"})
    assert args[:4] == ["-demo", "maze_car", "--player", "You"]
    assert "--round_seconds" not in args and "--norecord" not in args
    args = _args(
        "Drive", Record="no", **{"Round seconds": "90", "FPS cap": "30"}
    )
    assert "--norecord" in args and "--maze_car.display.max_fps=30" in args
    assert args[args.index("--round_seconds") + 1] == "90"


def test_run_episodes_names_the_run_after_the_driver():
    args = _args("Run episodes", Driver="agent:rookie", Name="")
    assert args[:4] == ["-run", "rookie", "--driver", "agent:rookie"]
    assert _args("Run episodes", Name="try")[1] == "try"


def test_create_or_branch_an_agent():
    args = _args("Create an agent", Name="kid", Model="small")
    assert args == ["-new_agent", "kid", "--seed", "0", "--model", "small"]
    branch = _args(
        "Create an agent", Name="kid", **{"Branch from": "a@d0100k"}
    )
    assert branch[-2:] == ["--from", "a@d0100k"]
    assert NONE == BY_NAME["Create an agent"].fields[2].default


def test_choices_with_special_values():
    assert _args("Resume training", Run=NEWEST_STOPPED) == ["-resume_last"]
    assert _args("Resume training", Run="r1") == ["-resume", "r1"]
    assert _args("Evaluate", Agent=BASELINES_ONLY)[0] == "-eval_baselines"
    assert _args("Evaluate", Agent="rookie")[:2] == ["-eval", "rookie"]
    assert _args("Showcase", Agent="a", Checkpoints="all")[-1] == (
        "--showcase_all"
    )
    tests = BY_NAME["Run tests"]
    assert tests.argv(_values(tests, File=ALL_TESTS))[1:] == ["-m", "pytest"]


# The window



@pytest.fixture
def window():
    from src.control.window import ControlCenter

    center = ControlCenter()
    yield center
    center.jobs.stop_all()


def _frames(center, count=10):
    for _ in range(count):
        for event in pygame.event.get():
            center.handle(event)
        center._refresh(force=True)
        center.gui.update(0.05)
        center.draw()
        time.sleep(0.02)


def test_an_action_shows_its_fields(window):
    window._select("Watch a run's best replay")
    assert list(window.field_widgets) == ["Run"]
    window._select("List runs")
    assert window.field_widgets == {}
    window._select("Drive")
    assert window.values()["Player"] == "You"


def test_a_required_field_left_blank(window):
    window._select("Run episodes")
    values = {**window.values(), "Episodes": ""}
    window.run_action(window.selected, values)
    assert window.message[0] == "Needs: Episodes"
    assert window.jobs.jobs == []


def test_an_action_runs_as_a_job(window):
    window._select("List runs")
    window.run_action(window.selected, window.values())
    job = window.jobs.jobs[-1]
    assert job.label == "List runs"
    assert _wait(lambda: job.status == "done")


def test_a_typed_command_runs_as_a_job(window):
    window.run_typed("make runs")
    job = window.jobs.jobs[-1]
    assert job.label == "make runs"
    assert _wait(lambda: job.status == "done")
    _frames(window)
    assert window.job_list.item_list  # listed


def test_a_typed_command_needs_a_real_name(window):
    window.run_typed("nonsense X=1")
    assert window.message[0] == "No make command 'nonsense'"
    window.run_typed("train")  # AGENT is missing
    assert "needs AGENT" in window.message[0]
    assert window.jobs.jobs == []


def test_esc_asks_before_quitting(window):
    event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)
    window.handle(event)
    assert window.quit_dialog is not None and window.running
    window.handle(
        pygame.event.Event(
            pygame_gui.UI_CONFIRMATION_DIALOG_CONFIRMED,
            ui_element=window.quit_dialog,
        )
    )
    assert not window.running
