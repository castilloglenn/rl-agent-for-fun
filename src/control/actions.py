"""The control center's actions: every command, consolidated and grouped
by the natural steps (roadmap step 6a).

The Makefile has one target per variant, since a terminal command takes at
most one parameter. Here an action has fields instead, so one "Run
episodes" covers run_heuristic, run_random, run_reward, run_rules, and the
rest. MAKE_TARGETS says which action covers each make target, and a test
checks that every target is covered.
"""

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from src.control import choices

REPO = Path(__file__).resolve().parents[2]
NONE = "(none)"
BASELINES_ONLY = "(baselines only)"
NEWEST_STOPPED = "(newest stopped)"
ALL_TESTS = "(all)"


@dataclass(frozen=True)
class Field:
    """One setting of an action. options: the choices (a dropdown), or
    None for a typed value (default fills it in).
    """

    name: str
    options: Callable[[], list[str]] | None = None
    default: str = ""
    hint: str = ""  # shown next to a typed field, for example "rules' own"


@dataclass(frozen=True)
class Action:
    name: str
    group: str
    description: str
    fields: tuple[Field, ...]
    build: Callable[[dict], list[str]]  # values -> app.py arguments
    opens_window: bool = False
    program: tuple[str, ...] = ("app.py",)  # or ("-m", "pytest")
    # Asks first: values -> the confirmation box's lines (6b3).
    confirm: Callable[[dict], list[str]] | None = None

    def argv(self, values: dict[str, str]) -> list[str]:
        filled = {f.name: values.get(f.name, f.default) for f in self.fields}
        return [sys.executable, *self.program, *self.build(filled)]

    def command_line(self, values: dict[str, str]) -> str:
        """How to type it in a terminal."""
        return " ".join(["python", *self.argv(values)[1:]])


# Choices


def _files(folder: str) -> Callable[[], list[str]]:
    return lambda: sorted(p.stem for p in (REPO / folder).glob("*.json"))


def _trainers(kind: str) -> Callable[[], list[str]]:
    def names() -> list[str]:
        found = []
        for path in sorted((REPO / "trainers").glob("*.json")):
            algorithm = json.loads(path.read_text()).get("algorithm")
            if (algorithm == "imitation") == (kind == "imitation"):
                found.append(path.stem)
        return found

    return names


def _drivers(keyboard: bool) -> Callable[[], list[str]]:
    def names() -> list[str]:
        agents = [f"agent:{a}" for a in choices.agents()]
        return (["keyboard"] if keyboard else []) + [
            *choices.BASELINES,
            *agents,
        ]

    return names


def _checkpoints() -> list[str]:
    """Every agent's checkpoints, as agent@checkpoint."""
    found = [NONE]
    for agent in choices.agents():
        folder = REPO / "agents" / agent / "checkpoints"
        paths = sorted(folder.glob("*.pt"), key=lambda p: p.stat().st_mtime)
        for path in paths:
            found.append(f"{agent}@{path.stem}")
    return found


def _stopped_runs() -> list[str]:
    stopped = []
    for run in choices.runs():
        folder = REPO / "runs" / run
        summary = folder / "summary.json"
        if not (folder / "resume.pt").exists():
            continue
        if not summary.exists() or json.loads(summary.read_text()).get(
            "interrupted"
        ):
            stopped.append(run)
    return [NEWEST_STOPPED, *stopped]


def _replays() -> list[str]:
    """Your recordings, then every run's saved replays, newest first."""
    replays = sorted(
        (REPO / "runs").glob("*/replays/*.jsonl*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return choices.recordings() + [
        str(p.relative_to(REPO)) for p in replays[:30]
    ]


# Fields the game actions share.
STAGE = Field("Stage", _files("stages"), "box")
RULES = Field("Rules", _files("rules"), "standard")
SECONDS = Field("Round seconds", None, "", "blank: the rules' own")
REWARD = Field("Reward profile", _files("rewards"), "default")


def _game(values: dict) -> list[str]:
    args = ["--stage", values["Stage"], "--rules", values["Rules"]]
    if values["Round seconds"].strip():
        args += ["--round_seconds", values["Round seconds"].strip()]
    return args + ["--reward", values["Reward profile"]]


def _drive(v: dict) -> list[str]:
    args = ["-demo", "maze_car", "--player", v["Player"], *_game(v)]
    if v["Record"] == "no":
        args.append("--norecord")
    if v["FPS cap"].strip() not in ("", "0"):
        args.append(f"--maze_car.display.max_fps={v['FPS cap'].strip()}")
    return args


def _run(v: dict) -> list[str]:
    name = v["Name"].strip() or v["Driver"].replace("agent:", "")
    return [
        "-run", name, "--driver", v["Driver"],
        "--episodes", v["Episodes"], "--seed", v["Seed"], *_game(v),
    ]


def _new_agent(v: dict) -> list[str]:
    args = ["-new_agent", v["Name"].strip(), "--seed", v["Seed"]]
    if v["Branch from"] != NONE:
        return args + ["--from", v["Branch from"]]
    return args + ["--model", v["Model"]]


def _train(v: dict) -> list[str]:
    return [
        "-train", v["Agent"], "--trainer", v["Trainer"],
        "--seed", v["Seed"], *_game(v),
    ]


def _resume(v: dict) -> list[str]:
    if v["Run"] == NEWEST_STOPPED:
        return ["-resume_last"]
    return ["-resume", v["Run"]]


def _evaluate(v: dict) -> list[str]:
    if v["Agent"] == BASELINES_ONLY:
        return ["-eval_baselines", "--suite", v["Suite"]]
    return ["-eval", v["Agent"], "--suite", v["Suite"]]


def _showcase(v: dict) -> list[str]:
    args = ["-showcase", v["Agent"]]
    return args + (["--showcase_all"] if v["Checkpoints"] == "all" else [])


def _tests(v: dict) -> list[str]:
    return [] if v["File"] == ALL_TESTS else [v["File"]]


def _trash_entries() -> list[str]:
    from src.control.trash import Trash

    return [entry.name for entry in Trash().entries()]


def _confirm_delete_run(v: dict) -> list[str]:
    return [
        f"runs/{v['Run']} moves into the trash.",
        "Its checkpoints stay in its agent. You can restore it later.",
    ]


def _confirm_empty(v: dict) -> list[str]:
    count = len(_trash_entries())
    noun = "entry is" if count == 1 else "entries are"
    return [f"{count} trash {noun} deleted for good. This can't be undone."]


def _agents_or_baselines() -> list[str]:
    return [*choices.agents(), BASELINES_ONLY]


YES_NO = lambda: ["yes", "no"]  # noqa: E731

ACTIONS = (
    # Play
    Action(
        "Drive",
        "Play",
        "Drive with the keyboard. Your rounds are recorded unless Record "
        "is no.",
        (
            Field("Player", None, "You"),
            Field("Record", YES_NO, "yes"),
            STAGE,
            RULES,
            SECONDS,
            REWARD,
            Field("FPS cap", None, "0", "0: match the display"),
        ),
        _drive,
        opens_window=True,
    ),
    Action(
        "Watch a driver",
        "Play",
        "Watch a baseline or an agent drive (an agent uses its best "
        "scored checkpoint).",
        (Field("Driver", _drivers(False), "heuristic"), STAGE, RULES,
         SECONDS, REWARD),
        lambda v: ["-demo", "maze_car", "--driver", v["Driver"], *_game(v)],
        opens_window=True,
    ),
    # Replays
    Action(
        "Watch a replay",
        "Replays",
        "Play back a recording or a run's replay, verified as it loads.",
        (Field("File", _replays),),
        lambda v: ["-replay", v["File"]],
        opens_window=True,
    ),
    Action(
        "Watch newest recording",
        "Replays",
        "Play back your most recent recorded round.",
        (),
        lambda v: ["-replay_last"],
        opens_window=True,
    ),
    Action(
        "List recordings",
        "Replays",
        "Your recorded rounds per player: recent and kept.",
        (),
        lambda v: ["-list_recordings"],
    ),
    # Experiments
    Action(
        "Run episodes",
        "Experiments",
        "Play many episodes headless into a run folder: scores, metrics, "
        "and best replays.",
        (
            Field("Driver", _drivers(False), "heuristic"),
            Field("Name", None, "", "blank: the driver's name"),
            Field("Episodes", None, "100"),
            Field("Seed", None, "0", "the first episode's seed"),
            STAGE,
            RULES,
            SECONDS,
            REWARD,
        ),
        _run,
    ),
    Action(
        "List runs",
        "Experiments",
        "Every run folder: driver, stage, rules, reward, and scores.",
        (),
        lambda v: ["-list_runs"],
    ),
    Action(
        "Watch a run's best replay",
        "Experiments",
        "Play back the highest-scoring episode a run saved.",
        (Field("Run", choices.runs),),
        lambda v: ["-best_replay", v["Run"]],
        opens_window=True,
    ),
    # Agents
    Action(
        "Create an agent",
        "Agents",
        "A new, untrained agent from a model, or a branch of another "
        "agent's checkpoint.",
        (
            Field("Name", None, "rookie"),
            Field("Model", _files("models"), "small"),
            Field("Branch from", _checkpoints, NONE),
            Field("Seed", None, "0", "for the first weights"),
        ),
        _new_agent,
    ),
    Action(
        "Train",
        "Agents",
        "One RL training phase from the agent's newest checkpoint. "
        "Checkpoints are scored as they're saved.",
        (
            Field("Agent", choices.agents),
            Field("Trainer", _trainers("rl"), "default"),
            Field("Seed", None, "0", "the first episode's seed"),
            STAGE,
            RULES,
            SECONDS,
            REWARD,
        ),
        _train,
    ),
    Action(
        "Resume training",
        "Agents",
        "Continue a stopped training run exactly where it stopped.",
        (Field("Run", _stopped_runs, NEWEST_STOPPED),),
        _resume,
    ),
    Action(
        "Clone your driving",
        "Agents",
        "Imitation: an agent (new or existing) learns from a dataset of "
        "recordings.",
        (
            Field("Agent", None, "clone", "new or existing"),
            Field("Dataset", _files("datasets"), "mine"),
            Field("Trainer", _trainers("imitation"), "imitate"),
        ),
        lambda v: [
            "-imitate", v["Agent"].strip(), "--dataset", v["Dataset"],
            "--imitation_trainer", v["Trainer"],
        ],
    ),
    Action(
        "Preview a dataset",
        "Agents",
        "Which recordings a dataset uses, and which are skipped (and why).",
        (Field("Dataset", _files("datasets"), "mine"),),
        lambda v: ["-preview_dataset", "--dataset", v["Dataset"]],
    ),
    Action(
        "Evaluate",
        "Agents",
        "Score an agent's unscored checkpoints on the suite, next to the "
        "baselines, and pick the best.",
        (
            Field("Agent", _agents_or_baselines),
            Field("Suite", _files("suites"), "box"),
        ),
        _evaluate,
    ),
    Action(
        "Showcase",
        "Agents",
        "Watch an agent's progression, checkpoint by checkpoint, on the "
        "same round.",
        (
            Field("Agent", choices.agents),
            Field("Checkpoints", lambda: ["highlights", "all"], "highlights"),
        ),
        _showcase,
        opens_window=True,
    ),
    Action(
        "Agent digest",
        "Agents",
        "An agent's lineage, best scores, trend, and milestone.",
        (Field("Agent", choices.agents),),
        lambda v: ["-show_agent", v["Agent"]],
    ),
    Action(
        "List agents",
        "Agents",
        "Every agent: model, decisions, best score, milestone.",
        (),
        lambda v: ["-list_agents"],
    ),
    # Files
    Action(
        "Delete a run",
        "Files",
        "Move a run folder into the trash. The checkpoints it saved stay "
        "in its agent. A run still running is refused.",
        (Field("Run", choices.runs),),
        lambda v: ["-delete_run", v["Run"]],
        confirm=_confirm_delete_run,
    ),
    Action(
        "Trash",
        "Files",
        "What's in the trash: one entry per delete, newest first.",
        (),
        lambda v: ["-list_trash"],
    ),
    Action(
        "Restore from the trash",
        "Files",
        "Put a trash entry's folders back where they were.",
        (Field("Entry", _trash_entries),),
        lambda v: ["-restore", v["Entry"]],
    ),
    Action(
        "Empty the trash",
        "Files",
        "Delete everything in the trash for good.",
        (),
        lambda v: ["-empty_trash"],
        confirm=_confirm_empty,
    ),
    # Develop
    Action(
        "Run tests",
        "Develop",
        "The test suite, or one test file.",
        (Field("File", lambda: [ALL_TESTS, *choices.test_files()], ALL_TESTS),),
        _tests,
        program=("-m", "pytest"),
    ),
    Action(
        "Vitals log",
        "Develop",
        "The machine's readings while the control center was open (the "
        "last 30 rows of logs/vitals.csv), for looking into a crash.",
        (),
        lambda v: ["-vitals"],
    ),
    Action(
        "Regenerate fixtures",
        "Develop",
        "Rewrite the behavior fixtures. Only for an intended behavior "
        "change.",
        (),
        lambda v: [],
        program=("-m", "tests.generate_behavior_fixtures"),
    ),
)

GROUPS = tuple(dict.fromkeys(action.group for action in ACTIONS))

# Which action covers each make target (tests check none is missing).
MAKE_TARGETS = {
    "maze_car": "Drive",
    "maze_car_norecord": "Drive",
    "maze_car_player": "Drive",
    "maze_car_stage": "Drive",
    "maze_car_reward": "Drive",
    "maze_car_rules": "Drive",
    "maze_car_seconds": "Drive",
    "maze_car_fps": "Drive",
    "maze_car_heuristic": "Watch a driver",
    "maze_car_random": "Watch a driver",
    "maze_car_driver": "Watch a driver",
    "maze_car_agent": "Watch a driver",
    "replay": "Watch a replay",
    "replay_last": "Watch newest recording",
    "recordings": "List recordings",
    "runs": "List runs",
    "run_heuristic": "Run episodes",
    "run_random": "Run episodes",
    "run_driver": "Run episodes",
    "run_episodes": "Run episodes",
    "run_reward": "Run episodes",
    "run_rules": "Run episodes",
    "run_stage": "Run episodes",
    "run_seconds": "Run episodes",
    "run_agent": "Run episodes",
    "run_best": "Watch a run's best replay",
    "new_agent": "Create an agent",
    "train": "Train",
    "resume": "Resume training",
    "resume_last": "Resume training",
    "imitate": "Clone your driving",
    "dataset": "Preview a dataset",
    "eval": "Evaluate",
    "eval_baselines": "Evaluate",
    "showcase": "Showcase",
    "showcase_all": "Showcase",
    "agent": "Agent digest",
    "agents": "List agents",
    "test": "Run tests",
    "test_file": "Run tests",
    "fixtures": "Regenerate fixtures",
    "vitals": "Vitals log",
    "delete_run": "Delete a run",
    "trash": "Trash",
    "restore": "Restore from the trash",
    "empty_trash": "Empty the trash",
    "main": None,  # the agent entry point stub: nothing to run here
}
