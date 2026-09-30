"""What the Training tab will do (roadmap step 6b2): the form's values
turned into a plan of steps, each one a Commands tab action, with an
estimate from your past runs, warnings, and what blocks starting.

    RL, new agent:          Create an agent, then Train
    Imitation, new agent:   Create an agent, then Clone your driving
    Imitation then RL:      (Create an agent), Clone, then Train

An existing agent skips the first step. Nothing here runs anything, and
nothing here imports torch, so the form stays quick.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from src.control import runs
from src.control.actions import ACTIONS, NONE
from src.utils import named_files, test_maps

REPO = Path(__file__).resolve().parents[2]
RL = "Reinforcement learning"
IMITATION = "Imitation"
BOTH = "Imitation, then reinforcement learning"
MODES = (RL, IMITATION, BOTH)
NEW_AGENT = "(new agent)"
FRESH = "(fresh from the model)"
AGENT_ID = re.compile(r"^[A-Za-z0-9_-]+$")  # the agent store's rule
PACE_RUNS = 3  # the recent runs an estimate is based on


@dataclass(frozen=True)
class Step:
    text: str  # in plain words
    action: str  # the Commands tab action that runs it
    values: dict  # its fields


@dataclass
class Plan:
    steps: list[Step] = field(default_factory=list)
    estimate: str = ""  # "about 9 min"
    basis: str = ""  # what the estimate comes from
    warnings: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)  # Start refuses

    @property
    def agent(self) -> str:
        return self.steps[-1].values["Agent"] if self.steps else ""

    def command_lines(self) -> list[str]:
        """The terminal equivalent, one line per step."""
        actions = {a.name: a for a in ACTIONS}
        return [
            actions[s.action].command_line(_filled(actions[s.action], s))
            for s in self.steps
        ]


def _filled(action, step: Step) -> dict:
    return {f.name: step.values.get(f.name, f.default) for f in action.fields}


def uses_rl(mode: str) -> bool:
    return mode in (RL, BOTH)


def uses_imitation(mode: str) -> bool:
    return mode in (IMITATION, BOTH)


def make_plan(
    values: dict,
    agents: list[str],
    busy: dict[str, str],
    runs_dir: Path | None = None,
    recordings: int | None = None,
    on_battery: bool = False,
) -> Plan:
    """`values`: the form's fields. `agents`: the existing ones. `busy`:
    agent -> what's training it right now. `recordings`: how many the
    dataset would read (None: not checked).
    """
    plan = Plan()
    mode = values["Mode"]
    new = values["Agent"] == NEW_AGENT
    agent = values.get("Name", "").strip() if new else values["Agent"]
    seed = values.get("Seed", "0").strip() or "0"
    shown = agent or "(name)"  # in the steps' text, until it's typed

    if new:
        if not agent:
            plan.blockers.append("Needs a name for the new agent.")
        elif not AGENT_ID.match(agent):
            plan.blockers.append(
                "A name uses letters, digits, - and _ only."
            )
        elif agent in agents:
            plan.blockers.append(
                f"{agent!r} already exists: pick it as the agent instead."
            )
        start = values.get("Start", FRESH)
        if start == FRESH:
            text = f"Create {shown} with the {values.get('Model')} model"
            branch = NONE
        else:
            text = f"Create {shown}, branched from {start}"
            branch = start
        plan.steps.append(
            Step(
                text + f" (seed {seed}).",
                "Create an agent",
                {
                    "Name": agent,
                    "Model": values.get("Model", "small"),
                    "Branch from": branch,
                    "Seed": seed,
                },
            )
        )
    elif agent in busy:
        plan.blockers.append(f"{agent} is training right now ({busy[agent]}).")

    if not seed.lstrip("-").isdigit():
        plan.blockers.append("Seed must be a whole number.")
    seconds = values.get("Round seconds", "").strip()
    if seconds and not _is_number(seconds):
        plan.blockers.append("Round seconds must be a number (or blank).")

    total = 0.0
    basis = []
    if uses_imitation(mode):
        dataset = values["Dataset"]
        trainer = _trainer(values["Imitation trainer"])
        epochs = trainer.get("epochs", 0)
        plan.steps.append(
            Step(
                f"Clone your driving (dataset {dataset}) into {shown}"
                f": {epochs} epochs, trainer {values['Imitation trainer']}.",
                "Clone your driving",
                {
                    "Agent": agent,
                    "Dataset": dataset,
                    "Trainer": values["Imitation trainer"],
                },
            )
        )
        if recordings == 0:
            plan.blockers.append(
                f"Dataset {dataset} has no recordings yet: drive some "
                "rounds first (Play: Drive)."
            )
        pace = _pace(runs_dir, runs.IMITATION)
        if pace:
            total += pace[0] * epochs
            basis.append(f"your last {_count(pace[1], 'imitation run')}")
    if uses_rl(mode):
        trainer = _trainer(values["Trainer"])
        decisions = trainer.get("total_decisions", 0)
        game = f"{values['Stage']} / {values['Rules']}"
        if seconds:
            game += f", {seconds} s rounds"
        plan.steps.append(
            Step(
                f"Train {shown} for {decisions:,} decisions (PPO, "
                f"trainer {values['Trainer']}) on {game}, reward "
                f"{values['Reward profile']}, from episode seed {seed}.",
                "Train",
                {
                    "Agent": agent,
                    "Trainer": values["Trainer"],
                    "Seed": seed,
                    "Stage": values["Stage"],
                    "Rules": values["Rules"],
                    "Round seconds": seconds,
                    "Reward profile": values["Reward profile"],
                },
            )
        )
        pace = _pace(runs_dir, runs.TRAINING)
        if pace:
            total += pace[0] * decisions
            basis.append(f"your last {_count(pace[1], 'training run')}")
        elif total:
            total = 0.0  # half an estimate would mislead
            basis = []

    if total:
        plan.estimate = f"about {_duration(total)}"
        plan.basis = "the pace of " + " and ".join(basis)
    else:
        plan.estimate = "no estimate"
        plan.basis = "no past runs of this kind to estimate from"
    stage = values.get("Stage", "")
    test_map = test_maps.warning(stage) if uses_rl(mode) else None
    if test_map:
        plan.warnings.append(test_map + ".")
    if on_battery:
        plan.warnings.append(
            "On battery: training keeps a core busy and drains it fast."
        )
    return plan


def busy_agents(rows: list) -> dict[str, str]:
    """agent -> the live run training it, from the Runs tab's rows."""
    busy = {}
    for row in rows:
        live = row.status in runs.LIVE
        if live and row.kind in (runs.TRAINING, runs.IMITATION):
            busy[row.who] = row.name
    return busy


def _trainer(name: str) -> dict:
    try:
        return json.loads(named_files.find("trainers", name).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _pace(runs_dir: Path | None, kind: str) -> tuple[float, int] | None:
    """(seconds per decision, or per epoch for imitation, runs used) from
    the newest finished runs of `kind`.
    """
    runs_dir = runs_dir or runs.RUNS_DIR
    seconds = units = 0.0
    used = 0
    for folder in sorted(runs_dir.glob("*/"), reverse=True):
        if used == PACE_RUNS:
            break
        config = runs.read_json(folder / "config.json")
        summary = runs.read_json(folder / "summary.json")
        if runs.run_kind(config) != kind or not summary.get("seconds"):
            continue
        if kind == runs.TRAINING:
            done = summary.get("decisions", 0)
        else:
            done = (config.get("trainer") or {}).get("epochs", 0)
        if done:
            seconds += summary["seconds"]
            units += done
            used += 1
    return (seconds / units, used) if units else None


def _is_number(text: str) -> bool:
    try:
        float(text)
    except ValueError:
        return False
    return True


def _count(n: int, noun: str) -> str:
    return f"{noun}" if n == 1 else f"{n} {noun}s"


def _duration(seconds: float) -> str:
    if seconds < 60:
        return f"{max(seconds, 1):.0f} s"
    minutes = round(seconds / 60)
    if minutes < 60:
        return f"{minutes} min"
    return f"{minutes // 60} h {minutes % 60:02d} min"
