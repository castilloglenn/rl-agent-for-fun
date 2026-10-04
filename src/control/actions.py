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
from src.utils import named_files, test_maps

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
    readonly: bool = False  # shown, not edited (the Files tab, 6d1)
    # A button showing `default` (7g2: the rounds picker opens from it):
    # no value of its own; the tab handles its press.
    button: bool = False


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
    confirm_label: str = "Delete (Enter)"  # its box's button

    def argv(self, values: dict[str, str]) -> list[str]:
        filled = {f.name: values.get(f.name, f.default) for f in self.fields}
        return [sys.executable, *self.program, *self.build(filled)]

    def command_line(self, values: dict[str, str]) -> str:
        """How to type it in a terminal."""
        return " ".join(["python", *self.argv(values)[1:]])


# Choices


def _files(folder: str) -> Callable[[], list[str]]:
    return lambda: choices.named(folder)  # built-ins, then yours (tagged)


def _trainers(kind: str) -> Callable[[], list[str]]:
    def names() -> list[str]:
        found = []
        for name in named_files.names("trainers"):
            path = named_files.find("trainers", name)
            algorithm = json.loads(path.read_text()).get("algorithm")
            if (algorithm == "imitation") == (kind == "imitation"):
                found.append(name)
        return found

    return names


def _drivers(keyboard: bool) -> Callable[[], list[str]]:
    def names() -> list[str]:
        agents = [
            choices.Choice(f"agent:{a}", f"agent: {getattr(a, 'label', a)}")
            for a in choices.agents()
        ]
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


def _stages_and_mixes(curricula: bool = True) -> list[str]:
    """Stages, then map mixes ("mix: basics", 7d5a), then curricula
    ("curriculum: skills", 7f5, training only).
    """
    found = choices.named("stages") + [
        choices.Choice(name, f"mix: {getattr(name, 'label', name)}")
        for name in choices.named("mixes")
    ]
    if curricula:
        found += [
            choices.Choice(
                name, f"curriculum: {getattr(name, 'label', name)}"
            )
            for name in choices.named("curricula")
        ]
    return found


TRAIN_STAGE = Field("Stage", _stages_and_mixes, "box")
# Recording a driver: a stage or a mix, not a curriculum (its hard levels
# would teach a clone to get stuck).
RECORD_STAGE = Field(
    "Stage", lambda: _stages_and_mixes(curricula=False), "box"
)
RULES = Field("Rules", _files("rules"), "standard")


def _game_counts() -> list[str]:
    """1 up to the cores a training may use (the 2 kept free and its own
    process aside, step 8).
    """
    import os

    from src.utils.resources import FREE_CORES

    most = max((os.cpu_count() or 1) - FREE_CORES - 1, 1)
    return [str(n) for n in range(1, most + 1)]


GAMES = Field(
    "Games",
    _game_counts,
    str(min(4, len(_game_counts()))),  # game_count.DEFAULT_GAMES
    "fewer while the machine is busy",
)
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
        "--seed", v["Seed"], "--games", v["Games"], *_game(v),
    ]


def _resume(v: dict) -> list[str]:
    if v["Run"] == NEWEST_STOPPED:
        return ["-resume_last"]
    return ["-resume", v["Run"]]


def _evaluate(v: dict) -> list[str]:
    if v["Agent"] == BASELINES_ONLY:
        return ["-eval_baselines", "--suite", v["Suite"]]
    return ["-eval", v["Agent"], "--suite", v["Suite"]]


SHOWCASE_SKILL = "open_field"  # app.py's --showcase_skill default


def _skills() -> list[str]:
    """The suite's skills, shown by label ("Open field") (7c8)."""
    return [
        choices.Choice(name, label) for name, label in test_maps.skills()
    ]


def _showcase(v: dict) -> list[str]:
    args = ["-showcase", v["Agent"]]
    if v["Checkpoints"] == "all":
        args.append("--showcase_all")
    skill = v.get("Skill", SHOWCASE_SKILL)
    if skill != SHOWCASE_SKILL:  # the default stays out of the command
        args += ["--showcase_skill", skill]
    return args


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


def _confirm_delete_agent(v: dict) -> list[str]:
    from src.control import agents_data
    from src.control.trash import Trash, TrashError

    agent = v["Agent"]
    try:
        plan = Trash().agent_plan(agent)
    except TrashError as error:  # the command will say so too
        return [f"agents/{agent} moves into the trash.", str(error)]
    runs = _count(len(plan.runs), "run")
    lines = [f"agents/{agent} and {runs} move into the trash:"]
    shown = [p.name for p in plan.runs[:3]]
    lines += [f"runs/{name}" for name in shown]
    if len(plan.runs) > 3:
        lines.append(f"and {len(plan.runs) - 3} more")
    if plan.children:
        lines.append(
            f"Kept (their own weights): {', '.join(plan.children)}, "
            f"branched from {agent}."
        )
    ranks = agents_data.leaderboard(
        agents_data.load_agents(), agents_data.baselines()
    )
    place = agents_data.place_of(agent, ranks)
    if place:
        lines.append(f"It's #{place} on the leaderboard. Restore it anytime.")
    else:
        lines.append("You can restore it from the trash.")
    return lines


def _count(n: int, noun: str) -> str:
    return f"{n} {noun}" + ("" if n == 1 else "s")


def _recent_recordings() -> list[str]:
    return [p for p in choices.recordings(100) if "/kept/" not in p]


def _kept_recordings() -> list[str]:
    return [p for p in choices.recordings(100) if "/kept/" in p]


def _confirm_delete_recording(v: dict) -> list[str]:
    return [
        f"{v['File']} moves into the trash.",
        "You can restore it later.",
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
        "Edit a map",
        "Play",
        "The map editor: draw walls, place the spawn and fuel, and "
        "save to stages/. An existing stage opens; a new name starts one.",
        (Field("Map", None, "my_map", "a stage in stages/, or a new name"),),
        lambda v: ["-edit_map", v["Map"].strip()],
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
    Action(
        "Correct an agent",
        "Agents",
        "Watch an agent (its newest checkpoint) with REC corrections on: "
        "hold a driving key to take over where it goes wrong; the rounds "
        "you took over in are saved for the corrections dataset (C turns "
        "it off and on). Then Clone your driving with dataset corrections "
        "and trainer correct, and train again.",
        (Field("Agent", choices.agents), STAGE, RULES, SECONDS, REWARD),
        lambda v: [
            "-demo", "maze_car", "--driver", f"agent:{v['Agent']}",
            "--corrections", *_game(v),
        ],
        opens_window=True,
    ),
    # Replays
    Action(
        "Watch a replay",
        "Replays",
        "Play back a recording or a run's replay, verified as it loads.",
        (
            Field("File", _replays),
            Field("From step", None, "", "blank: the start"),
        ),
        lambda v: [
            "-replay", v["File"],
            *(
                ["--replay_step", v["From step"].strip()]
                if v.get("From step", "").strip()
                else []
            ),
        ],
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
        "One reinforcement learning phase from the agent's newest "
        "checkpoint. "
        "Checkpoints are scored as they're saved.",
        (
            Field("Agent", choices.agents),
            Field("Trainer", _trainers("rl"), "default"),
            Field("Seed", None, "0", "the first episode's seed"),
            GAMES,
            TRAIN_STAGE,
            RULES,
            SECONDS,
            REWARD,
        ),
        _train,
    ),
    Action(
        "Resume training",
        "Agents",
        "Continue a stopped training run from its last update, with fresh rounds.",
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
            # The rounds to teach (7g2: ticked in the Training tab).
            Field("Recordings", None, "", "blank: every round"),
        ),
        lambda v: [
            "-imitate", v["Agent"].strip(), "--dataset", v["Dataset"],
            "--imitation_trainer", v["Trainer"],
            # The rounds ticked in the Training tab (7g2); none: all.
            *(
                ["--recordings", v["Recordings"].strip()]
                if v.get("Recordings", "").strip()
                else []
            ),
        ],
    ),
    Action(
        "Record a driver's rounds",
        "Agents",
        "Plays a driver headless and saves every round to its recordings "
        "(the heuristic: recordings/Heuristic/), for an imitation dataset "
        "(datasets/heuristic.json). A mix plays its maps in turn.",
        (
            Field("Driver", _drivers(False), "heuristic"),
            RECORD_STAGE,
            Field("Rounds", None, "50"),
            Field("Seed", None, "0", "the first round's seed"),
            RULES,
            SECONDS,
        ),
        lambda v: [
            "-record_rounds", v["Driver"], "--rounds", v["Rounds"].strip(),
            "--seed", v["Seed"].strip() or "0",
            "--stage", v["Stage"], "--rules", v["Rules"],
            *(
                ["--round_seconds", v["Round seconds"].strip()]
                if v["Round seconds"].strip()
                else []
            ),
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
            Field("Suite", _files("suites"), "skills"),
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
            Field("Skill", _skills, SHOWCASE_SKILL),
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
        "Delete an agent",
        "Files",
        "Move an agent into the trash, with its training, imitation, and "
        "episode runs. Agents branched from it stay.",
        (Field("Agent", choices.agents),),
        lambda v: ["-delete_agent", v["Agent"]],
        confirm=_confirm_delete_agent,
    ),
    Action(
        "Keep a recording",
        "Files",
        "Move a recording into kept/, where the latest-50 limit never "
        "removes it.",
        (Field("File", _recent_recordings),),
        lambda v: ["-keep", v["File"]],
    ),
    Action(
        "Unkeep a recording",
        "Files",
        "Move a kept recording back with the recent ones. The latest-50 "
        "limit applies at your next saved round.",
        (Field("File", _kept_recordings),),
        lambda v: ["-unkeep", v["File"]],
    ),
    Action(
        "Delete a recording",
        "Files",
        "Move a recording into the trash.",
        (Field("File", lambda: choices.recordings(100)),),
        lambda v: ["-delete_recording", v["File"]],
        confirm=_confirm_delete_recording,
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
        "Stop every job",
        "Develop",
        "The manual dead switch: stops every job of this project, also ones "
        "started in a terminal (Ctrl+C first, so training keeps its resume "
        "state). Not this window.",
        (),
        lambda v: ["-stop_all"],
        confirm=lambda v: [
            "Every job of this project stops, also in terminals.",
            "Training keeps its resume state: make resume_last.",
        ],
        confirm_label="Stop all (Enter)",
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
    "edit_map": "Edit a map",
    "maze_car_heuristic": "Watch a driver",
    "maze_car_random": "Watch a driver",
    "maze_car_driver": "Watch a driver",
    "maze_car_agent": "Watch a driver",
    "correct": "Correct an agent",
    "imitate_corrections": "Clone your driving",
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
    "train_curriculum": "Train",
    "finetune": "Train",
    "resume": "Resume training",
    "resume_last": "Resume training",
    "imitate": "Clone your driving",
    "record_heuristic": "Record a driver's rounds",
    "imitate_heuristic": "Clone your driving",
    "record_navigator": "Record a driver's rounds",
    "imitate_navigator": "Clone your driving",
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
    "stop_all": "Stop every job",
    "delete_run": "Delete a run",
    "delete_agent": "Delete an agent",
    "keep": "Keep a recording",
    "unkeep": "Unkeep a recording",
    "delete_recording": "Delete a recording",
    "trash": "Trash",
    "restore": "Restore from the trash",
    "empty_trash": "Empty the trash",
    "main": None,  # the agent entry point stub: nothing to run here
}
