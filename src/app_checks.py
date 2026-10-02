"""Checking a command's arguments before anything runs (roadmap 7h,
decision 065): every named file it reads exists, and its stage is a kind
it can play (only training takes a curriculum; training and recording
take a mix). A problem says what's wrong in plain words instead of a
crash halfway in. `app.py -check ...` checks and stops; every command is
checked first anyway.

Agents aren't checked here: each command already says clearly when one
doesn't exist. No torch: it's fast.
"""

from pathlib import Path

from src.utils import curricula, mixes, named_files

STAGE, MIX, CURRICULUM = "stage", "mix", "curriculum"
# Which kinds of stage each command plays (the rest play one stage).
PLAYS = {
    "train": (STAGE, MIX, CURRICULUM),
    "record_rounds": (STAGE, MIX),
}
DRIVEN = ("run", "record_rounds", "demo")  # commands with a --driver
HEADLESS = ("run", "record_rounds")  # no window: not the keyboard


def command_of(cl_args) -> str | None:
    """The command these arguments run (its flag), if any."""
    for name in (
        "train", "resume", "resume_last", "eval", "eval_baselines",
        "preview_dataset", "imitate", "new_agent", "showcase", "edit_map",
        "run", "record_rounds", "demo",
    ):
        if getattr(cl_args, name, None):
            return name
    return None


def stage_kind(name: str, root: Path = named_files.REPO) -> str | None:
    """What `name` is: a stage, a mix, a curriculum, or None (nothing)."""
    if name.endswith(".json"):
        return STAGE if Path(name).exists() else None
    if name in named_files.names("stages", root):
        return STAGE
    if mixes.is_mix(name, root):
        return MIX
    if curricula.is_curriculum(name, root):
        return CURRICULUM
    return None


def problems(cl_args, config, root: Path = named_files.REPO) -> list[str]:
    """What's wrong with these arguments, in plain words ([]: nothing)."""
    command = command_of(cl_args)
    found: list[str] = []
    if command in ("train", "run", "record_rounds", "demo"):
        found += _stage(command, config.stage, root)
        found += _named("rules", config.rules, "--rules", root)
    if command in ("train", "run", "demo"):
        found += _named("rewards", cl_args.reward, "--reward", root)
    if command == "train":
        found += _trainer(cl_args.trainer, "rl", "--trainer", root)
    if command == "imitate":
        found += _named("datasets", cl_args.dataset, "--dataset", root)
        found += _trainer(
            cl_args.imitation_trainer, "imitation", "--imitation_trainer",
            root,
        )
    if command == "preview_dataset":
        found += _named("datasets", cl_args.dataset, "--dataset", root)
    if command == "new_agent" and not getattr(cl_args, "from", ""):
        found += _named("models", cl_args.model, "--model", root)
    if command in ("eval", "eval_baselines", "showcase"):
        found += _named("suites", cl_args.suite, "--suite", root)
    if getattr(cl_args, "corrections", False) and not (
        command == "demo" and cl_args.driver.startswith("agent:")
    ):
        found.append(
            "--corrections: only while watching an agent "
            "(-demo maze_car --driver agent:<id>)"
        )
    if command in DRIVEN:  # recording names its driver in its own flag
        driver = (
            cl_args.record_rounds
            if command == "record_rounds"
            else cl_args.driver
        )
        found += _driver(command, driver)
    if command == "showcase" and not found:
        found += _skill(cl_args.showcase_skill, cl_args.suite, root)
    return found


def _stage(command: str, name: str, root: Path) -> list[str]:
    kind = stage_kind(name, root)
    if kind is None:
        return [f"--stage {name}: no stage, mix, or curriculum of that name"]
    plays = PLAYS.get(command, (STAGE,))
    if kind in plays:
        return []
    takes = " or a ".join(plays)
    return [
        f"--stage {name} is a {kind}: this command takes a {takes} "
        "(a mix is for training and recording, a curriculum for training)"
    ]


def _named(kind: str, name: str, flag: str, root: Path) -> list[str]:
    if name.endswith(".json"):
        return [] if Path(name).exists() else [f"{flag} {name}: no such file"]
    if name in named_files.names(kind, root):
        return []
    return [f"{flag} {name}: no {kind} file of that name"]


def _trainer(name: str, algorithm: str, flag: str, root: Path) -> list[str]:
    found = _named("trainers", name, flag, root)
    if found:
        return found
    import json

    data = json.loads(named_files.path_of("trainers", name, root).read_text())
    imitation = data.get("algorithm") == "imitation"
    if imitation == (algorithm == "imitation"):
        return []
    wanted = "an imitation" if algorithm == "imitation" else "a PPO (RL)"
    return [f"{flag} {name}: not {wanted} trainer"]


def _driver(command: str, name: str) -> list[str]:
    from src.drivers.registry import BASELINES

    if name == "keyboard":
        if command in HEADLESS:
            return [
                "--driver keyboard needs the window: pick random, "
                "heuristic, or agent:<id>"
            ]
        return []
    if name in BASELINES or (name.startswith("agent:") and len(name) > 6):
        return []
    known = ", ".join(["keyboard", *BASELINES, "agent:<id>"])
    return [f"--driver {name}: unknown (known: {known})"]


def _skill(skill: str, suite: str, root: Path) -> list[str]:
    from src.utils import skills

    names = [s.name for s in skills.load(suite, root)]
    if skill in names:
        return []
    return [f"--showcase_skill {skill}: not a skill of {suite}"]
