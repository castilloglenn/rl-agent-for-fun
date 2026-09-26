"""Showcase mode: an agent's training progression, checkpoint by
checkpoint, in the simulation window (roadmap step 5c).

    make showcase AGENT=id       highlights (about 8 checkpoints)
    make showcase_all AGENT=id   every scored checkpoint

Every checkpoint plays the same round (the suite's first round seed), so
you watch the same situation handled better and better. Play is
deterministic, so each round is exactly what the evaluation saw. A title
card with the checkpoint's suite scores comes first, and the next
checkpoint starts when a round ends.

SPACE pause, 1-4 speed, N one step while paused, R restart this
checkpoint, Left/Right previous/next checkpoint, H lines, Esc quit.
"""

import csv
from dataclasses import dataclass
from pathlib import Path

import pygame
from ml_collections import ConfigDict

from src.agents.driver import AgentDriver
from src.agents.history import read_profile
from src.agents.store import load_agent
from src.envs.maze_car.env import MazeCarEnv
from src.experiments.evaluation import (
    DEFAULT_SUITE,
    best_row,
    evaluate_agent,
    load_suite,
    read_results,
)
from src.experiments.runner import RUNS_DIR
from src.render import theme
from src.render.panels import ModeInfo
from src.render.renderer import Command
from src.replay.viewer import PlaybackControl
from src.sim.rules import load_rules
from src.sim.stage import load_stage
from src.utils.timing import FixedStepClock

CARD_SECONDS = 2.0  # the title card, and the pause after a round
DEFAULT_SPEED = 2  # index in the viewer's speeds: 2x
HIGHLIGHTS = 8
HINTS = "SPACE pause  1-4 speed  <- -> checkpoint  R restart  H lines"


@dataclass(frozen=True)
class Stop:
    """One checkpoint to show, with what's known about it."""

    checkpoint: str
    decisions: int
    scores: dict  # its suite row
    minutes: float | None  # training time up to it
    badges: tuple[str, ...]


def plan(
    agent: str | Path,
    everything: bool = False,
    root: Path | None = None,
    runs_dir: Path | None = None,
    base_config: ConfigDict | None = None,
    on_scored=None,
) -> tuple[Path, list[Stop]]:
    """The checkpoints to show, oldest first. Unscored checkpoints are
    scored first (a few seconds each).
    """
    suite = load_suite(DEFAULT_SUITE)
    folder = load_agent(agent, "initial", root=root).folder
    rows = evaluate_agent(
        folder, suite, base_config=base_config, on_checkpoint=on_scored
    )
    rows = sorted(rows, key=lambda r: (r["decisions"], r["checkpoint"]))
    chosen = rows if everything else highlights(rows, folder)
    profile = read_profile(folder)
    milestone = (profile["milestone"] or {}).get("checkpoint")
    best = best_row(rows)["checkpoint"]
    stops, record = [], float("-inf")
    for row in rows:
        new_best = row["score_mean"] > record
        record = max(record, row["score_mean"])
        if row not in chosen:
            continue
        badges = []
        if row["checkpoint"] == best:
            badges.append("BEST")
        elif new_best and row is not rows[0]:
            badges.append("NEW BEST")
        if row["checkpoint"] == milestone:
            badges.append("MILESTONE")
        stops.append(
            Stop(
                checkpoint=row["checkpoint"],
                decisions=int(row["decisions"]),
                scores=row,
                minutes=_training_minutes(
                    folder, row["checkpoint"], runs_dir or RUNS_DIR
                ),
                badges=tuple(badges),
            )
        )
    return folder, stops


def highlights(rows: list[dict], folder: Path, count: int = HIGHLIGHTS):
    """initial, the first checkpoint that scores, the milestone, the best,
    and the last, filled up with evenly spaced ones.
    """
    if len(rows) <= count:
        return list(rows)
    names = [r["checkpoint"] for r in rows]
    best = best_row(rows)
    must = {0, len(rows) - 1, names.index(best["checkpoint"])}
    threshold = 0.1 * best["score_mean"]
    scoring = next(
        (i for i, r in enumerate(rows) if r["score_mean"] >= threshold),
        None,
    )
    if scoring is not None:
        must.add(scoring)
    milestone = (read_profile(folder)["milestone"] or {}).get("checkpoint")
    if milestone in names:
        must.add(names.index(milestone))
    spare = count - len(must)
    others = [i for i in range(len(rows)) if i not in must]
    if spare > 0 and others:
        step = len(others) / spare
        must |= {others[int(k * step)] for k in range(spare)}
    return [rows[i] for i in sorted(must)]


def _training_minutes(folder: Path, checkpoint: str, runs_dir: Path):
    """Training time up to a checkpoint: earlier phases, plus its own run's
    learning.csv up to its decisions. None if the run is gone.
    """
    import torch

    data = torch.load(
        folder / "checkpoints" / f"{checkpoint}.pt", weights_only=True
    )
    run, decisions = data.get("run"), data.get("decisions", 0)
    if run is None:
        return 0.0  # initial, or a branch start
    phases = read_profile(folder)["phases"]
    before = 0.0
    for phase in phases:
        if phase["run"] == run:
            break
        before += phase["seconds"]
    else:
        return None
    if phase.get("kind") == "imitation":
        return (before + phase["seconds"]) / 60
    learning = Path(runs_dir) / run / "learning.csv"
    if not learning.exists():
        return None
    start = phase["start_decisions"]
    with open(learning, newline="") as file:
        for row in csv.DictReader(file):
            if start + int(row["decisions"]) >= decisions:
                return (before + float(row["seconds"])) / 60
    return None


class Showcase:
    def __init__(
        self, folder: Path, stops: list[Stop], config: ConfigDict
    ) -> None:
        if not stops:
            raise ValueError("no checkpoints to show")
        self.folder, self.stops = folder, stops
        scenario = next(
            s
            for s in load_suite(DEFAULT_SUITE).scenarios
            if s.kind == "round"
        )
        self.seed = scenario.first_seed
        config = config.copy_and_resolve_references()
        config.show_gui = True
        rules = load_rules(scenario.rules)
        if scenario.round_seconds:
            rules = rules.with_round_seconds(scenario.round_seconds)
        self.env = MazeCarEnv(
            config, stage=load_stage(scenario.stage), rules=rules
        )
        self.renderer = self.env.renderer
        sps = self.env.config.sim.steps_per_second
        self.clock = FixedStepClock(sps, max_steps_per_frame=32)
        self.control = PlaybackControl(speed_index=DEFAULT_SPEED)
        self.index = 0
        self.finished = False  # past the last checkpoint: the summary
        self._start(0)

    # Moving between checkpoints

    def _start(self, index: int) -> None:
        self.index = index
        stop = self.stops[index]
        self.driver = AgentDriver(load_agent(self.folder, stop.checkpoint))
        self.env.driver = f"{self.folder.name}@{stop.checkpoint}"
        self.observation, _ = self.env.reset(seed=self.seed)
        self.driver.reset(self.seed)
        self.card = CARD_SECONDS  # title card time left
        self.after = CARD_SECONDS  # pause after the round ends
        self.finished = False

    def next(self) -> None:
        if self.index + 1 < len(self.stops):
            self._start(self.index + 1)
        else:
            self.finished = True
            self.observation, _ = self.env.reset(seed=self.seed)  # a calm
            # field under the summary, not the last round's end

    def previous(self) -> None:
        if self.finished:
            self._start(self.index)
        elif self.index > 0:
            self._start(self.index - 1)

    def handle_key(self, key: int) -> None:
        if key == pygame.K_RIGHT:
            self.next()
        elif key == pygame.K_LEFT:
            self.previous()
        else:
            self.control.handle_key(key)

    # Playing

    def tick(self, elapsed: float) -> None:
        """Advances by `elapsed` real seconds."""
        control = self.control
        if self.finished:
            return
        if control.restart_requested:
            control.restart_requested = False
            self._start(self.index)
            return
        if control.paused:
            for _ in range(control.step_requests):
                self._step()
            control.step_requests = 0
            self.clock.advance(0)
            return
        if self.card > 0:
            self.card -= elapsed
            self.clock.advance(0)
            return
        if self.env.is_game_over:
            self.after -= elapsed
            if self.after <= 0:
                self.next()
            return
        for _ in range(self.clock.advance(elapsed * control.speed)):
            self._step()
            if self.env.is_game_over:
                break

    def _step(self) -> None:
        if not self.env.is_game_over:
            self.env.step_world(self.driver.act(self.observation))
            self.observation = self.env.last_observation

    # What the window shows

    def mode(self) -> ModeInfo:
        speed = "PAUSED" if self.control.paused else f"{self.control.speed:g}×"
        # Short, to fit next to the gauge: DRIVER shows the checkpoint.
        label = f"{self.index + 1}/{len(self.stops)} {speed}"
        if self.finished:
            return ModeInfo("SHOWCASE", theme.ACCENT, HINTS, self._summary())
        if self.card > 0:
            messages = self._title()
        elif self.env.is_game_over:
            messages = self._round_end()
        else:
            messages = ()
        return ModeInfo(label, theme.ACCENT, HINTS, messages)

    def _title(self) -> tuple:
        stop = self.stops[self.index]
        s = stop.scores
        minutes = ""
        if stop.minutes is not None:
            minutes = f" · {stop.minutes:,.1f} min of training"
        lines = [
            (
                f"{self.folder.name} · {stop.checkpoint} · "
                f"{self.index + 1} of {len(self.stops)}",
                theme.ACCENT,
            ),
            (f"{stop.decisions:,} decisions{minutes}", theme.TEXT),
            (
                f"suite: score {s['score_mean']:,.0f} · survival "
                f"{s['survival']:.0%} · wrecks {s['wreck_rate']:.0%} · "
                f"braking {s['braking']:.0%}",
                theme.TEXT,
            ),
        ]
        if stop.badges:
            lines.append((" · ".join(stop.badges), theme.GOOD))
        return tuple(lines)

    def _round_end(self) -> tuple:
        stop = self.stops[self.index]
        last = self.index + 1 == len(self.stops)
        return (
            (
                f"{stop.checkpoint}: this round {self.env.score:,.0f} "
                f"(suite mean {stop.scores['score_mean']:,.0f})",
                theme.TEXT,
            ),
            (
                "the summary is next"
                if last
                else "the next checkpoint follows",
                theme.TEXT_DIM,
            ),
        )

    def _summary(self) -> tuple:
        first, last = self.stops[0], self.stops[-1]
        best = max(self.stops, key=lambda s: s.scores["score_mean"])
        lines = [
            (
                f"{self.folder.name}: {len(self.stops)} checkpoints shown",
                theme.ACCENT,
            ),
            (
                f"{first.checkpoint} {first.scores['score_mean']:,.0f}  ->  "
                f"{last.checkpoint} {last.scores['score_mean']:,.0f}",
                theme.TEXT,
            ),
            (
                f"best: {best.checkpoint} {best.scores['score_mean']:,.0f}",
                theme.GOOD,
            ),
        ]
        milestone = next(
            (s for s in self.stops if "MILESTONE" in s.badges), None
        )
        if milestone:
            lines.append(
                (f"milestone at {milestone.checkpoint}", theme.GOOD)
            )
        lines.append(("<- back  Esc quit", theme.TEXT_DIM))
        return tuple(lines)

    def run(self) -> None:
        elapsed = 0.0
        while True:
            if Command.QUIT in self.renderer.poll_events():
                break
            for key in self.renderer.keys_pressed:
                self.handle_key(key)
            self.tick(elapsed)
            playing = not (self.control.paused or self.card > 0)
            alpha = self.clock.alpha if playing else 1.0
            self.renderer.draw(
                self.env.world, alpha, self.env.reward_status(), self.mode()
            )
            elapsed = self.renderer.present()


