"""The runs tab's data (roadmap step 6b1): every run folder, its status,
progress, and learning curves, read from the files the runs write.

No run reports to the control center: it reads what's on disk, and only
the lines a file has gained since the last read. A run is linked to the
job that started it by its first output line ("Run: <folder>"), or for
training by the process id in its training.lock.
"""

import csv
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from src.control import charts
from src.control.charts import (
    DASHED,
    DOTS,
    LEVEL,
    LINE,
    RING,
    Chart,
    Series,
)
from src.control.jobs import Job
from src.render import theme
from src.utils import skills

REPO = Path(__file__).resolve().parents[2]
RUNS_DIR = REPO / "runs"
AGENTS_DIR = REPO / "agents"
LIVE_SECONDS = 30.0  # a run whose files changed this recently is running
RATE_ROWS = 20  # recent rows that set the pace, for the time left

TRAINING, IMITATION, EPISODES = "training", "imitation", "episodes"
KIND_LABELS = {TRAINING: "train", IMITATION: "imitate", EPISODES: "episodes"}

# Statuses: running or paused as one of our jobs, running elsewhere (a
# terminal), stopped (Ctrl+C), done, or ended without a summary. Starting:
# our job hasn't written its run folder yet (7c16: an imitation builds its
# dataset first), shown as a row of its own until it does.
RUNNING, PAUSED, ELSEWHERE = "running", "paused", "running elsewhere"
STOPPED, DONE, ENDED = "stopped", "done", "ended unexpectedly"
STARTING = "starting"
STATUS_COLORS = {
    STARTING: theme.ACCENT,
    RUNNING: theme.GOOD,
    PAUSED: theme.WARN,
    ELSEWHERE: theme.GOOD,
    STOPPED: theme.WARN,
    DONE: theme.TEXT,
    ENDED: theme.BAD,
}
LIVE = (RUNNING, PAUSED, ELSEWHERE, STARTING)
# What makes a run: a job's flag, or a chain's step (the Training tab's).
RUN_FLAGS = {"-train": TRAINING, "-imitate": IMITATION, "-run": EPISODES}
STEP_KINDS = {"Train": TRAINING, "Clone your driving": IMITATION}

# Training's second chart: (option, learning.csv column). Skills is each
# skill's share over the checkpoints (7d4), the first and the default.
SKILLS_CHART = "Skills"
TRAINING_CHARTS = (
    (SKILLS_CHART, None),
    ("Agent reward", "reward_mean"),
    ("Entropy", "entropy"),
    ("Policy loss", "policy_loss"),
    ("Value loss", "value_loss"),
    ("KL divergence", "approx_kl"),
    ("Clip fraction", "clip_fraction"),
    # Not from learning.csv: each scored checkpoint's driving style (7c9).
    ("Driving style", None),
)
STYLE_CHART = "Driving style"
# One color per skill, in the suite's order (7d4).
SKILL_COLORS = (
    (230, 170, 70),
    (120, 200, 220),
    (70, 200, 120),
    (90, 150, 230),
    (220, 110, 110),
    (180, 130, 230),
    (230, 220, 120),
)
STYLE_LINES = (  # (label, column, color)
    ("forward", "style_forward", theme.GOOD),
    ("brake", "style_brake", theme.WARN),
    ("coast", "style_coast", theme.TEXT_DIM),
    ("reverse", "style_reverse", theme.BAD),
)
IMITATION_CHARTS = (
    ("Loss", ("train_loss", "held_out_loss")),
    ("Value loss", ("value_loss",)),
)
EPISODE_CHARTS = (
    ("Agent reward", "reward"),
    ("Checkpoints", "checkpoints"),
    ("Distance points", "distance_points"),
    ("Steps", "steps"),
)
HELD_OUT = (160, 120, 230)  # the held-out line, apart from the accent


class CsvTail:
    """A CSV file that's still being written: each read adds only the new
    complete lines. A file that shrank (rewritten after Ctrl+C) is read
    again from the start.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.offset = 0
        self.columns: list[str] | None = None
        self.rows: list[dict] = []

    def read(self) -> bool:
        """True if rows were added (or the file was read again)."""
        try:
            size = self.path.stat().st_size
        except FileNotFoundError:
            return False
        reset = size < self.offset
        if reset:
            self.offset, self.columns, self.rows = 0, None, []
        if size == self.offset:
            return reset
        with open(self.path, "rb") as file:
            file.seek(self.offset)
            chunk = file.read()
        end = chunk.rfind(b"\n")
        if end < 0:
            return reset  # half a line so far
        self.offset += end + 1
        lines = chunk[: end + 1].decode().splitlines()
        for values in csv.reader(lines):
            if not values:
                continue
            if self.columns is None:
                self.columns = values
                continue
            self.rows.append(
                {k: _number(v) for k, v in zip(self.columns, values)}
            )
        return True

    def column(self, name: str, x: str) -> list[tuple[float, float]]:
        return [
            (row[x], row[name])
            for row in self.rows
            if isinstance(row.get(name), float) and isinstance(row[x], float)
        ]


def _number(text: str):
    try:
        return float(text)
    except ValueError:
        return text


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, ValueError):
        return False
    except PermissionError:
        return True
    return True


def _lock_pid(folder: Path) -> int | None:
    try:
        return int((folder / "training.lock").read_text())
    except (FileNotFoundError, ValueError):
        return None


def job_runs(jobs: list[Job]) -> dict[str, Job]:
    """Which run folder each job writes, from its "Run: " line (the
    newest job wins, for a run resumed again).
    """
    return {job.run: job for job in jobs if job.run}


@dataclass
class RunRow:
    name: str  # the folder
    kind: str
    who: str  # the agent, or the driver of an episode run
    status: str
    progress: float | None  # 0 to 1, if it knows its total
    job: Job | None  # ours, if we started it
    resumable: bool
    has_replays: bool
    clock: str = ""  # a starting row's start time: "10-01 13:50:43"

    @property
    def when(self) -> str:
        """09-27 00:33:02, from the folder's name (or the name itself, for
        a folder not named by a run).
        """
        if self.clock:
            return self.clock
        parts = self.name.split("_")
        if len(parts) < 2 or len(parts[0]) != 10:
            return self.name[:14]
        date, clock = parts[:2]
        if len(clock) != 6:
            return date[5:]
        return f"{date[5:]} {clock[:2]}:{clock[2:4]}:{clock[4:]}"

    @property
    def state(self) -> str:
        """The list's short status."""
        if self.status in (RUNNING, ELSEWHERE) and self.progress is not None:
            return f"{self.progress:.0%}"
        return {ELSEWHERE: "live", ENDED: "ended?"}.get(
            self.status, self.status
        )

    @property
    def line(self) -> str:
        kind = KIND_LABELS[self.kind]
        return f"{self.when:<14} {kind:<8} {self.who[:9]:<9} {self.state:>7}"


def run_kind(config: dict) -> str:
    return config.get("kind") or EPISODES


def run_who(config: dict) -> str:
    if "agent" in config:
        return config["agent"]["id"]
    driver = config.get("driver") or {}
    who = driver.get("id") or driver.get("player") or config.get("name")
    return str(who or "?")


def run_stages(config: dict) -> list[str]:
    """The maps a run played: a mix's (7d5a), or its stage."""
    mix = config.get("mix")
    if mix:
        return [stage["name"] for stage in mix["stages"]]
    name = (config.get("stage") or {}).get("name")
    return [name] if name else []


def run_place(config: dict) -> str:
    """Where it played, as shown: "mix basics (4 maps)", or the stage."""
    mix = config.get("mix")
    if mix:
        return f"mix {mix['name']} ({len(mix['stages'])} maps)"
    return _name(config, "stage")


def status_of(
    folder: Path,
    kind: str,
    job: Job | None,
    now: float | None = None,
) -> str:
    if job and job.running:
        return PAUSED if job.paused else RUNNING
    if kind == TRAINING:
        pid = _lock_pid(folder)
        if pid and _alive(pid):
            return ELSEWHERE  # its lock says it's training
    summary = read_json(folder / "summary.json")
    if summary:
        return STOPPED if summary.get("interrupted") else DONE
    if kind != TRAINING:  # no lock: recent writes mean it's running
        now = time.time() if now is None else now
        newest = max(
            (p.stat().st_mtime for p in folder.glob("*.csv")),
            default=(folder / "config.json").stat().st_mtime,
        )
        if now - newest < LIVE_SECONDS:
            return ELSEWHERE
    return ENDED


def starting_name(job: Job) -> str:
    """A starting row's name (it has no folder yet)."""
    return f"starting #{job.number}"


def starting_rows(jobs: list[Job] = (), chains: list = ()) -> list[RunRow]:
    """A row for each of our jobs that will write a run but hasn't yet:
    a training, imitation, or episode run still getting ready (an
    imitation builds its dataset first), or a chain's step before its
    run (creating the agent). Newest first.
    """
    rows, in_chain = [], set()
    for chain in chains:
        in_chain.update(id(job) for job in chain.jobs)
        job = chain.job
        if not (chain.active and job and job.running and not job.run):
            continue
        ahead = chain.steps[len(chain.jobs) - 1 :]
        kind = next(
            (
                STEP_KINDS[step.action]
                for step in ahead
                if getattr(step, "action", None) in STEP_KINDS
            ),
            None,
        )
        if kind:
            rows.append(_starting(job, kind, chain.agent or "?"))
    for job in jobs:
        if id(job) in in_chain or not job.running or job.run:
            continue
        found = _run_flag(job.argv)
        if found:
            rows.append(_starting(job, *found))
    return sorted(rows, key=lambda row: row.clock, reverse=True)


def _run_flag(argv: list[str]) -> tuple[str, str] | None:
    """(kind, who) for a job that writes a run, from its command."""
    for flag, kind in RUN_FLAGS.items():
        if flag in argv[:-1]:
            who = argv[argv.index(flag) + 1]
            if kind == EPISODES and "--driver" in argv[:-1]:
                who = argv[argv.index("--driver") + 1]
            return kind, who
    return None


def _starting(job: Job, kind: str, who: str) -> RunRow:
    began = time.time() - (time.monotonic() - job.started)
    return RunRow(
        name=starting_name(job),
        kind=kind,
        who=who,
        status=STARTING,
        progress=None,
        job=job,
        resumable=False,
        has_replays=False,
        clock=datetime.fromtimestamp(began).strftime("%m-%d %H:%M:%S"),
    )


def scan(
    runs_dir: Path | None = None,
    jobs: list[Job] = (),
    now: float | None = None,
    configs: dict | None = None,
    chains: list = (),
) -> list[RunRow]:
    """Every run folder, newest first, after the runs still starting.
    `configs` keeps the configs read before (they never change), so
    rescanning every second stays cheap.
    """
    runs_dir = runs_dir or RUNS_DIR
    configs = {} if configs is None else configs
    linked = job_runs(list(jobs))
    by_pid = {job.process.pid: job for job in jobs if job.running}
    rows = starting_rows(list(jobs), chains)
    for folder in sorted(runs_dir.glob("*/"), reverse=True):
        config = configs.get(folder.name)
        if config is None:
            config = read_json(folder / "config.json")
            if not config:
                continue  # not a run, or its config isn't written yet
            configs[folder.name] = config
        kind = run_kind(config)
        job = linked.get(folder.name)
        if job is None and kind == TRAINING:
            job = by_pid.get(_lock_pid(folder))
        status = status_of(folder, kind, job, now)
        rows.append(
            RunRow(
                name=folder.name,
                kind=kind,
                who=run_who(config),
                status=status,
                progress=_progress(folder, kind, config, status),
                job=job,
                resumable=(
                    kind == TRAINING
                    and status in (STOPPED, ENDED)
                    and (folder / "resume.pt").exists()
                ),
                has_replays=any((folder / "replays").glob("*.jsonl*")),
            )
        )
    return rows


def _progress(folder, kind, config, status) -> float | None:
    if status == DONE:
        return 1.0
    done, total = _count(folder, kind, config)
    return None if not total else min(done / total, 1.0)


def _count(folder: Path, kind: str, config: dict) -> tuple[float, float]:
    """(done, total) in the run's own unit, from its files' last line."""
    if kind == TRAINING:
        last = _last_row(folder / "learning.csv")
        return last.get("decisions", 0), config["trainer"]["total_decisions"]
    if kind == IMITATION:
        last = _last_row(folder / "learning.csv")
        return last.get("epoch", 0), config["trainer"]["epochs"]
    rows = _line_count(folder / "metrics.csv") - 1
    return max(rows, 0), config.get("episodes") or 0


def _last_row(path: Path) -> dict:
    try:
        with open(path, "rb") as file:
            header = file.readline().decode()
            file.seek(0, os.SEEK_END)
            size = file.tell()
            file.seek(max(size - 4096, 0))
            tail = file.read().decode(errors="replace").splitlines()
    except FileNotFoundError:
        return {}
    columns = next(csv.reader([header]), [])
    for line in reversed(tail):
        values = next(csv.reader([line]), [])
        if len(values) == len(columns) and values != columns:
            return {k: _number(v) for k, v in zip(columns, values)}
    return {}


def _line_count(path: Path) -> int:
    try:
        with open(path, "rb") as file:
            return sum(1 for _ in file)
    except FileNotFoundError:
        return 0


class RunData:
    """One run's details and curves, kept up to date by `refresh`."""

    def __init__(self, folder: Path, agents_dir: Path | None = None):
        self.folder = folder
        self.agents_dir = agents_dir or AGENTS_DIR
        self.config = read_json(folder / "config.json")
        self.kind = run_kind(self.config)
        self.who = run_who(self.config)
        self.summary: dict = {}
        self.learning = CsvTail(folder / "learning.csv")
        self.metrics = CsvTail(folder / "metrics.csv")
        self._history_seen = -1.0
        # (checkpoint, decisions, game score on the suite) per scored one.
        self.suite_points: list[tuple[str, float, float]] = []
        self.shares: dict[str, float] = {}  # its average share, by name
        # Each scored checkpoint's driving style: (decisions, its shares).
        self.style_points: list[tuple[float, dict]] = []
        self.best: tuple[str, float, float] | None = None
        self.baseline: float | None = None  # the heuristic's share: 1.0
        # Each skill's share over the checkpoints (7d4): name -> points.
        self.skill_points: dict[str, list[tuple[float, float]]] = {}
        self.stage = (self.config.get("stage") or {}).get("name", "")
        self.mix = (self.config.get("mix") or {}).get("name")
        self.stages = run_stages(self.config)  # every map it trains on
        suite = self.config.get("suite")
        self.suite = f"{suite['name']}-v{suite['version']}" if suite else None
        self.skills = skills.load(suite["name"]) if suite else []
        self.heuristic: dict = {}
        if self.suite:
            scores = read_json(
                self.agents_dir / "baselines" / f"{self.suite}.json"
            ).get("scores", {})
            self.heuristic = scores.get("heuristic") or {}
            if self.heuristic:
                self.baseline = 1.0
        self.refresh()

    @property
    def start_decisions(self) -> float:
        return (self.config.get("agent") or {}).get("start_decisions", 0)

    def refresh(self) -> bool:
        """Reads what the run wrote since. True if anything changed."""
        changed = False
        summary = read_json(self.folder / "summary.json")
        if summary != self.summary:
            self.summary, changed = summary, True
        if self.kind in (TRAINING, IMITATION):
            changed |= self.learning.read()
        if self.kind in (TRAINING, EPISODES):
            changed |= self.metrics.read()
        if self.kind == TRAINING:
            changed |= self._read_history()
        return changed

    def _read_history(self) -> bool:
        """The suite score of each checkpoint this run saved, from the
        agent's history (scored as training goes, 5a5).
        """
        agent = self.agents_dir / self.who
        path = agent / "history.jsonl"
        try:
            seen = path.stat().st_mtime
        except FileNotFoundError:
            return False
        if seen == self._history_seen:
            return False
        self._history_seen = seen
        saved, scores, shares, styles, skill_values = {}, {}, {}, {}, {}
        for line in path.read_text().splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("event") == "checkpoint_saved":
                if event.get("run") == self.folder.name:
                    saved[event["checkpoint"]] = event["decisions"]
            elif event.get("event") == "scored":
                if event.get("suite") == self.suite and "share" in event:
                    scores[event["checkpoint"]] = event["score_mean"]
                    shares[event["checkpoint"]] = event["share"]
                    skill_values[event["checkpoint"]] = {
                        skills.COLUMN + name: value
                        for name, value in (event.get("skills") or {}).items()
                    }
                    styles[event["checkpoint"]] = {
                        k: v
                        for k, v in event.items()
                        if k.startswith("style_")
                    }
        self.suite_points = sorted(
            (
                (name, float(decisions), float(scores[name]))
                for name, decisions in saved.items()
                if name in scores
            ),
            key=lambda p: p[1],
        )
        self.shares = {
            name: float(shares[name]) for name, _, _ in self.suite_points
        }
        self.skill_points = {}
        for name, decisions in sorted(saved.items(), key=lambda kv: kv[1]):
            found = skills.shares(
                skill_values.get(name, {}), self.heuristic, self.skills
            )
            for skill, share in found.items():
                self.skill_points.setdefault(skill, []).append(
                    (float(decisions), share)
                )
        self.style_points = sorted(
            (float(decisions), styles[name])
            for name, decisions in saved.items()
            if styles.get(name)
        )
        best = read_json(agent / "evaluations" / "best.json")
        self.best = next(
            (p for p in self.suite_points if p[0] == best.get("checkpoint")),
            None,
        )
        return True

    # What the header shows

    def description(self) -> str:
        c = self.config
        trainer = _name(c, "trainer")
        if self.kind == IMITATION:
            rounds = len(c.get("recordings") or [])
            return (
                f"{self.who} · trainer {trainer} · dataset "
                f"{_name(c, 'dataset')} · {rounds} rounds"
            )
        game = (
            f"{run_place(c)} · {_name(c, 'rules')} · reward "
            f"{_name(c, 'reward')} · seed {c.get('first_seed', 0)}"
        )
        if self.kind == TRAINING:
            agent = c["agent"]
            start = agent.get("start_checkpoint", "initial")
            branched = agent.get("branched_from")
            if branched:
                start = f"{branched.get('agent')}@{branched.get('checkpoint')}"
            return f"{self.who} from {start} · trainer {trainer} · {game}"
        return f"driver {self.who} · {game}"

    def counts(self) -> tuple[float, float, str]:
        """(done, total, unit)."""
        done, total = _count(self.folder, self.kind, self.config)
        unit = {TRAINING: "decisions", IMITATION: "epochs"}.get(
            self.kind, "episodes"
        )
        return done, total, unit

    def seconds_left(self) -> float | None:
        """From the pace of the last rows. None if it can't tell."""
        done, total, _ = self.counts()
        if not total or done >= total:
            return None
        if self.kind == EPISODES:  # its seconds are game time: use the clock
            created = datetime.fromisoformat(self.config["created_at"])
            spent = time.time() - created.timestamp()
            return spent / done * (total - done) if done and spent else None
        rows = self.learning.rows[-RATE_ROWS:]
        x = "decisions" if self.kind == TRAINING else "epoch"
        if len(rows) < 2:
            return None
        units = rows[-1][x] - rows[0][x]
        seconds = rows[-1]["seconds"] - rows[0]["seconds"]
        if units <= 0 or seconds <= 0:
            return None
        return seconds / units * (total - done)

    def notes(self) -> str:
        """The key result, for the header's right side."""
        s = self.summary
        if self.kind == TRAINING and self.best:
            name = self.best[0]
            return f"best {name}: share {self.shares[name]:.2f}"
        if self.kind == IMITATION and s.get("evaluation"):
            return f"clone on the suite {s['evaluation']['score_mean']:,.0f}"
        if s.get("best_score") is not None:
            return f"best episode {s['best_score']:,.0f}"
        return ""

    # The charts

    def options(self) -> list[str]:
        table = {
            TRAINING: TRAINING_CHARTS,
            IMITATION: IMITATION_CHARTS,
            EPISODES: EPISODE_CHARTS,
        }[self.kind]
        return [name for name, _ in table]

    def main_chart(self) -> Chart:
        if self.kind == TRAINING:
            start = self.start_decisions
            training = [
                (x + start, y)
                for x, y in self.learning.column("score_mean", "decisions")
            ]
            series = [
                Series(
                    "training (mixed)" if self.mix else "training",
                    training,
                    theme.ACCENT,
                    LINE,
                ),
                Series(
                    f"suite {self.suite}",
                    [(d, s) for _, d, s in self.suite_points],
                    theme.GOOD,
                    DOTS,
                ),
            ]
            if self.best:
                name, d, s = self.best
                series.append(
                    Series(
                        f"best {name}", [(d, s)], theme.WARN, RING, priority=2
                    )
                )
            score = self.heuristic.get("score_mean")
            if score is not None:
                series.append(
                    Series(
                        "heuristic",
                        [(0, score)],
                        theme.TEXT_DIM,
                        LEVEL,
                        priority=1,
                    )
                )
            return Chart("SCORE (game points)", series, "{} decisions")
        if self.kind == IMITATION:
            return Chart(
                "ACCURACY (picks your action)",
                [
                    Series(
                        "train",
                        self.learning.column("train_accuracy", "epoch"),
                        theme.ACCENT,
                    ),
                    Series(
                        "held-out rounds",
                        self.learning.column("held_out_accuracy", "epoch"),
                        HELD_OUT,
                    ),
                ],
                "epoch {}",
                y_format=charts.percent,
                value_format=charts.percent,
            )
        scores = self.metrics.column("score", "episode")
        return Chart(
            "SCORE per episode (game points)",
            [
                Series("episode", scores, theme.ACCENT, DOTS),
                Series("mean of 20", _rolling(scores), theme.GOOD),
            ],
            "episode {}",
        )

    def _skills_chart(self) -> Chart:
        """SKILLS (7d4), the second chart's first option: each skill's
        share of the heuristic's over the run's scored checkpoints (dashed:
        a skill on the map it trains on), the average share's dots, the
        best ringed, and the heuristic at 1.0.
        """
        series = []
        for i, skill in enumerate(self.skills):
            here = skill.stage in self.stages
            series.append(
                Series(
                    skill.label + (" (trained here)" if here else ""),
                    self.skill_points.get(skill.name, []),
                    SKILL_COLORS[i % len(SKILL_COLORS)],
                    DASHED if here else LINE,
                    priority=3,
                )
            )
        series.append(
            Series(
                "average share",
                [(d, self.shares[n]) for n, d, _ in self.suite_points],
                theme.TEXT,
                DOTS,
            )
        )
        if self.best:
            name, d, _ = self.best
            series.append(
                Series(
                    f"best {name}",
                    [(d, self.shares[name])],
                    theme.WARN,
                    RING,
                    priority=2,
                )
            )
        if self.baseline is not None:
            series.append(
                Series(
                    "heuristic",
                    [(0, self.baseline)],
                    theme.TEXT_DIM,
                    LEVEL,
                    priority=1,
                )
            )
        place = f"mix {self.mix}" if self.mix else self.stage
        trained = f" · trained on {place}" if place else ""
        chart = Chart(f"SKILLS{trained}", series, "{} decisions")
        chart.y_format = chart.value_format = "{:.2f}".format
        chart.legend_rows = 3  # seven skills and the rest
        return chart

    def second_chart(self, option: str) -> Chart:
        if self.kind == TRAINING and option == SKILLS_CHART:
            return self._skills_chart()
        if self.kind == TRAINING and option == STYLE_CHART:
            chart = Chart(
                option.upper(),
                [
                    Series(
                        label,
                        [(d, s[column]) for d, s in self.style_points
                         if column in s],
                        color,
                    )
                    for label, column, color in STYLE_LINES
                ],
                "{} decisions",
            )
            chart.y_format = chart.value_format = charts.percent
            return chart
        if self.kind == TRAINING:
            column = dict(TRAINING_CHARTS)[option]
            start = self.start_decisions
            points = [
                (x + start, y)
                for x, y in self.learning.column(column, "decisions")
            ]
            return Chart(
                option.upper(),
                [Series(option.lower(), points, theme.ACCENT)],
                "{} decisions",
            )
        if self.kind == IMITATION:
            columns = dict(IMITATION_CHARTS)[option]
            colors = (theme.ACCENT, HELD_OUT)
            labels = {"train_loss": "train", "held_out_loss": "held-out"}
            return Chart(
                option.upper(),
                [
                    Series(
                        labels.get(c, option.lower()),
                        self.learning.column(c, "epoch"),
                        color,
                    )
                    for c, color in zip(columns, colors)
                ],
                "epoch {}",
            )
        column = dict(EPISODE_CHARTS)[option]
        return Chart(
            option.upper(),
            [
                Series(
                    option.lower(),
                    self.metrics.column(column, "episode"),
                    theme.ACCENT,
                    DOTS,
                )
            ],
            "episode {}",
        )


def _name(config: dict, key: str) -> str:
    return (config.get(key) or {}).get("name", "?")


def _rolling(points, count: int = 20) -> list[tuple[float, float]]:
    """The mean of the last `count` points, at each point."""
    out, total = [], 0.0
    for i, (x, y) in enumerate(points):
        total += y
        if i >= count:
            total -= points[i - count][1]
        out.append((x, total / min(i + 1, count)))
    return out
