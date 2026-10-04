"""The Agents tab's data (roadmap step 6c): each agent's profile, skills,
skill history, and lineage, the leaderboard, and high scores, read from
the files agents and runs keep. No torch, so the tab stays quick.

    agents/<id>/profile.json          summary, phases, best, milestone
    agents/<id>/evaluations/<suite>.csv   suite results per checkpoint
    agents/baselines/<suite>.json     the heuristic's and random's
"""

import csv
import gzip
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from src.control import runs
from src.utils import skills as suite_skills

REPO = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO / "agents"
RECORDINGS_DIR = REPO / "recordings"
SUITE_FILE = REPO / "suites" / "skills.json"  # the default suite
HIGH_SCORES = 5  # per stage, rules, and round length

RADAR_RIM = 1.5  # the radar's rim, as a share of the heuristic's (7d4)
# The skill history's other choices: (label, suite metric). The average
# share and each skill's share come first (history_choices).
HISTORY = (
    ("Game score", "score_mean"),
    ("Survival", "survival"),
    ("Fuels per min", "fuels_per_min"),
    ("Wreck rate", "wreck_rate"),
    ("Wall contacts", "contacts"),
    ("Lowest score", "score_min"),
    ("Driving: forward", "style_forward"),  # 7c9
    ("Driving: reversing", "style_reverse"),
    ("Driving: backward", "style_backward"),
)
SHARE = "share:"  # a skill's share in history rows: "share:open_field"
_SCORE = re.compile(r"_score(-?\d+)_")


@dataclass
class AgentInfo:
    id: str
    folder: Path
    profile: dict
    live: str = ""  # the run training it right now, if any

    @property
    def nickname(self) -> str | None:
        """Your name for it ("Reverse Guy"), if you gave it one (7c10)."""
        return self.profile.get("nickname") or None

    @property
    def title(self) -> str:
        """How it's shown: "Reverse Guy · agent-1", or its id."""
        return f"{self.nickname} · {self.id}" if self.nickname else self.id

    @property
    def model(self) -> str:
        model = self.profile.get("model") or {}
        shape = "×".join(str(h) for h in model.get("hidden", []))
        return f"{model.get('name', '?')} {shape}".strip()

    @property
    def decisions(self) -> float:
        return self.profile.get("decisions", 0)

    @property
    def seconds(self) -> float:
        return (self.profile.get("training") or {}).get("seconds", 0.0)

    @property
    def best(self) -> dict:
        """Its best checkpoint's scores on the current suite ({} if it
        wasn't scored on it: an older suite's scores don't count).
        """
        best = self.profile.get("best") or {}
        return best if best.get("suite") == current_suite() else {}

    @property
    def stage(self) -> str | None:
        """The stage its newest training phase ran on (None if none)."""
        phases = self.profile.get("phases") or []
        return next(
            (p["stage"] for p in reversed(phases) if p.get("stage")), None
        )

    @property
    def best_checkpoint(self) -> str | None:
        return (self.profile.get("checkpoints") or {}).get("best")

    @property
    def score(self) -> float | None:
        """Its best average share of the heuristic's (the ranking)."""
        return self.best.get("share")

    @property
    def created(self) -> str:
        return self.profile.get("created", "")

    @property
    def branched_from(self) -> dict | None:
        return self.profile.get("branched_from")

    @property
    def milestone(self) -> dict | None:
        return self.profile.get("milestone")

    @property
    def imitation(self) -> bool:
        phases = self.profile.get("phases") or []
        return any(p.get("kind") == "imitation" for p in phases)

    def badges(self) -> list[str]:
        found = []
        if self.live:
            found.append("TRAINING")
        if self.milestone:
            found.append("MILESTONE")
        if self.branched_from:
            found.append("BRANCHED")
        if self.imitation:
            found.append("FROM YOUR DRIVING")
        return found


def load_agents(
    agents_dir: Path | None = None, busy: dict[str, str] | None = None
) -> list[AgentInfo]:
    """Every agent with a profile (the baselines aren't agents)."""
    agents_dir = agents_dir or AGENTS_DIR
    busy = busy or {}
    found = []
    for folder in sorted(agents_dir.glob("*/")):
        if not (folder / "model.json").exists():
            continue
        profile = runs.read_json(folder / "profile.json")
        profile.setdefault("id", folder.name)
        found.append(
            AgentInfo(folder.name, folder, profile, busy.get(folder.name, ""))
        )
    return found


def sort_agents(agents: list[AgentInfo], by: str) -> list[AgentInfo]:
    keys = {
        "score": lambda a: -(a.score or float("-inf")),
        "newest": lambda a: _negate(a.created),
        "name": lambda a: a.id.lower(),
        "decisions": lambda a: -a.decisions,
    }
    return sorted(agents, key=keys[by])


def _negate(text: str) -> tuple:
    return tuple(-ord(c) for c in text)


def current_suite(path: Path = SUITE_FILE) -> str:
    """The default suite as its results files name it: "skills-v1". Its
    version goes up when the suite is edited (6d1).
    """
    data = runs.read_json(path)
    return f"{data.get('name', 'skills')}-v{data.get('version', 1)}"


def baselines(agents_dir: Path | None = None, suite: str = "") -> dict:
    """{"heuristic": metrics, "random": metrics} on the suite."""
    suite = suite or current_suite()
    path = (agents_dir or AGENTS_DIR) / "baselines" / f"{suite}.json"
    return runs.read_json(path).get("scores", {})


def heuristic_ratio(agent: AgentInfo, base: dict) -> float | None:
    """The agent's best, as a multiple of the heuristic's: its average
    share across the skills (7d3b).
    """
    return agent.score or None


# Skills


def skills(metrics: dict, heuristic: dict, found: list) -> list[float]:
    """One value per radar axis (each of `found` skills): its share of the
    heuristic's over RADAR_RIM, so the heuristic sits at 1 / RADAR_RIM and
    the rim is 1.5 times as good. Clipped to 0..1.
    """
    shares = suite_skills.shares(metrics, heuristic, found)
    return [
        min(max(shares.get(s.name, 0.0) / RADAR_RIM, 0.0), 1.0) for s in found
    ]


def history_choices(found: list) -> list[tuple[str, str]]:
    """The skill history's picker: (label, row key)."""
    return (
        [("Average share", "share")]
        + [(f"{s.label} share", SHARE + s.name) for s in found]
        + list(HISTORY)
    )


def with_shares(rows: list[dict], heuristic: dict, found: list) -> list[dict]:
    """`rows` with each skill's share added, as "share:<skill>"."""
    return [
        {
            **row,
            **{
                SHARE + name: share
                for name, share in suite_skills.shares(
                    row, heuristic, found
                ).items()
            },
        }
        for row in rows
    ]


def history(agent: AgentInfo, suite: str = "") -> list[dict]:
    """The suite results of each scored checkpoint, by decisions."""
    suite = suite or current_suite()
    path = agent.folder / "evaluations" / f"{suite}.csv"
    try:
        with open(path, newline="") as file:
            rows = [
                {k: v if k == "checkpoint" else float(v) for k, v in r.items()}
                for r in csv.DictReader(file)
            ]
    except (FileNotFoundError, ValueError):
        return []
    return sorted(rows, key=lambda r: r["decisions"])


# Lineage


@dataclass
class Phase:
    text: str
    run: str | None = None  # its run folder, if it still exists


def lineage(
    agent: AgentInfo, agent_ids: set[str], runs_dir: Path | None = None
) -> list[Phase]:
    """How it started, then each training phase."""
    runs_dir = runs_dir or runs.RUNS_DIR
    source = agent.branched_from
    if source:
        parent = source.get("agent", "?")
        gone = "" if parent in agent_ids else " (deleted)"
        start = f"branched from {parent}@{source.get('checkpoint')}{gone}"
    else:
        start = f"created fresh with the {agent.model} model"
    phases = [Phase(start[0].upper() + start[1:])]
    for phase in agent.profile.get("phases") or []:
        run = phase.get("run", "?")
        exists = (runs_dir / run).exists()
        tag = "" if exists else " (run deleted)"
        if phase.get("kind") == "imitation":
            data = phase.get("dataset") or {}
            text = (
                f"cloned from {data.get('player', '?')} "
                f"({data.get('rounds', '?')} rounds, dataset "
                f"{data.get('dataset', '?')})"
            )
        else:
            text = (
                f"Reinforcement learning, trainer {phase.get('trainer')}, "
                f"{_place(phase)} / {phase.get('rules')}, "
                f"{phase.get('start_decisions', 0):,.0f} to "
                f"{phase.get('end_decisions', 0):,.0f} decisions"
            )
        status = phase.get("status", "")
        phases.append(
            Phase(
                f"{text} ({status}){tag}",
                run if exists else None,
            )
        )
    return phases


# The leaderboard and high scores


@dataclass
class Rank:
    place: int | None  # None for the baselines' reference rows
    name: str
    model: str
    decisions: float | None
    checkpoint: str
    metrics: dict = field(default_factory=dict)
    label: str = ""  # how it's shown, if not its name: with a nickname


def leaderboard(agents: list[AgentInfo], base: dict) -> list[Rank]:
    """Agents by their best average share of the heuristic's, with the
    baselines as unranked rows in their place.
    """
    rows = [
        Rank(
            None,
            a.id,
            a.model,
            a.decisions,
            a.best_checkpoint or "",
            a.best,
            a.title,
        )
        for a in agents
        if a.best
    ]
    for name in ("heuristic", "random"):
        if base.get(name):
            baseline = Rank(None, f"({name})", "baseline", None, "", base[name])
            rows.append(baseline)
    rows.sort(key=lambda r: -(r.metrics.get("share") or 0))
    place = 0
    for row in rows:
        if row.model != "baseline":
            place += 1
            row.place = place
    unscored = [a for a in agents if not a.best]
    for a in unscored:  # never scored: at the end, unranked
        rows.append(Rank(None, a.id, a.model, a.decisions, "", {}, a.title))
    return rows


def place_of(agent_id: str, ranks: list[Rank]) -> int | None:
    return next((r.place for r in ranks if r.name == agent_id), None)


@dataclass(frozen=True)
class HighScore:
    score: float
    who: str
    where: str  # "run <folder>" or "recording"


def high_scores(
    runs_dir: Path | None = None,
    recordings_dir: Path | None = None,
    cache: dict | None = None,
) -> dict[str, list[HighScore]]:
    """The best single rounds per stage, rules, and round length, from
    runs' best episodes and your recordings. `cache` keeps recording
    headers already read.
    """
    runs_dir = runs_dir or runs.RUNS_DIR
    recordings_dir = recordings_dir or RECORDINGS_DIR
    cache = {} if cache is None else cache
    found: dict[str, list[HighScore]] = {}
    for folder in runs_dir.glob("*/"):
        config = runs.read_json(folder / "config.json")
        best = runs.read_json(folder / "summary.json").get("best_score")
        if not config or best is None or "stage" not in config:
            continue
        if config.get("mix"):
            continue  # its best round could be on any of its maps
        key = _game_key(config["stage"], config["rules"])
        who = runs.run_who(config)
        found.setdefault(key, []).append(
            HighScore(float(best), who, f"run {folder.name}")
        )
    for path in recordings_dir.glob("*/**/*.jsonl*"):
        match = _SCORE.search(path.name)
        if not match:
            continue
        if path not in cache:
            cache[path] = recording_game(path)
        key = cache[path]
        if key is None:
            continue
        player = path.relative_to(recordings_dir).parts[0]
        found.setdefault(key, []).append(
            HighScore(float(match.group(1)), player, "recording")
        )
    return {
        key: sorted(scores, key=lambda s: -s.score)[:HIGH_SCORES]
        for key, scores in sorted(found.items())
    }


def _place(phase: dict) -> str:
    """A phase's map, or its mix: "mix basics" (7d5a)."""
    if phase.get("curriculum"):
        return f"curriculum {phase['curriculum']}"
    if phase.get("mix"):
        return f"mix {phase['mix']}"
    return str(phase.get("stage"))


def _game_key(stage: dict, rules: dict) -> str:
    seconds = rules.get("round_seconds")
    length = f", {seconds:g} s rounds" if seconds else ""
    return f"{stage.get('name', '?')} / {rules.get('name', '?')}{length}"


def recording_game(path: Path) -> str | None:
    opener = gzip.open if path.suffix == ".gz" else open
    try:
        with opener(path, "rt") as file:
            header = json.loads(file.readline())
        return _game_key(header["stage"], header["rules"])
    except (OSError, ValueError, KeyError):
        return None
