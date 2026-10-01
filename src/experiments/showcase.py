"""Showcase mode: an agent's training progression, checkpoint by
checkpoint, in the simulation window (roadmap step 5c).

    make showcase AGENT=id       highlights (about 8 checkpoints)
    make showcase_all AGENT=id   every scored checkpoint

The window opens at once, and gets ready behind a card that says each
step (scoring what isn't scored yet, 7c8). Every checkpoint plays the same
round, a skill's first seed (Open field by default; M picks another of
the suite's skills, with a preview of its map), so you watch the same
situation handled better and better. Play is deterministic, so each
round is exactly what the evaluation saw. A title card with the
checkpoint's scores comes first, and the round's result stays until
Enter, then the next checkpoint's card.

Enter start the round, SPACE/P pause, 1-4 speed, N one step while
paused, R restart this checkpoint, Left/Right previous/next checkpoint,
M pick a skill, H lines, Esc quit.
"""

import csv
import json
import random
import threading
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
    baseline_scores,
    baselines_fresh,
    best_row,
    evaluate_agent,
    load_suite,
    place_at_wall,
    shares,
    unscored,
)
from src.experiments.runner import RUNS_DIR
from src.render import theme
from src.render.map_picker import MapChoice
from src.render.panels import ModeInfo, PlaybackInfo
from src.render.renderer import Command
from src.replay.viewer import SPEEDS, TRAIL_EVERY, PlaybackControl
from src.sim.components import Transform
from src.sim.resources import RoundState, SimClock
from src.sim.rules import load_rules
from src.sim.stage import load_stage
from src.utils import named_files
from src.utils.timing import FixedStepClock

DEFAULT_SPEED = 2  # index in the viewer's speeds: 2x
DEFAULT_SKILL = "open_field"  # the box: one familiar map (M picks another)
HIGHLIGHTS = 8
SHORTCUTS = (
    ("Enter", "start the round, or go on after it ends"),
    ("SPACE / P", "pause / resume"),
    ("1-4", "speed: 0.5x, 1x, 2x, 4x"),
    ("N", "one step while paused"),
    ("<- ->", "previous / next checkpoint"),
    ("M", "skills: pick one, its map and round"),
    ("R", "restart this checkpoint"),
    ("H", "lines"),
    ("F", "camera: follow or fit (big stages)"),
    ("T", "trail: where the car has been"),
    ("?", "these shortcuts"),
    ("Esc", "quit (asks first)"),
)


@dataclass(frozen=True)
class Stop:
    """One checkpoint to show, with what's known about it."""

    checkpoint: str
    decisions: int
    scores: dict  # its suite row
    minutes: float | None  # training time up to it
    badges: tuple[str, ...]


class Cancelled(Exception):
    """The showcase was closed while it was getting ready."""


def plan(
    agent: str | Path,
    everything: bool = False,
    root: Path | None = None,
    runs_dir: Path | None = None,
    base_config: ConfigDict | None = None,
    on_scored=None,
    on_progress=None,
    cancelled=lambda: False,
) -> tuple[Path, list[Stop]]:
    """The checkpoints to show, oldest first. Unscored checkpoints are
    scored first (a few seconds each), and the baselines too if their
    cache is out of date (about 9 s). `on_progress(text)` hears each step;
    `cancelled()` true stops it (Cancelled) between steps.
    """
    say = on_progress or (lambda text: None)
    suite = load_suite(DEFAULT_SUITE)
    folder = load_agent(agent, "initial", root=root).folder
    todo = unscored(folder, suite)
    if todo and not baselines_fresh(suite, folder.parent, base_config):
        say(
            "The heuristic's scores for this code, once (about 9 s): each "
            "skill's share is measured against them"
        )
        baseline_scores(suite, folder.parent, base_config)

    def starting(name: str, i: int, n: int) -> None:
        if cancelled():
            raise Cancelled()
        say(
            f"Scoring checkpoint {name}, {i} of {n}, on the skills suite "
            "(about 5 s each)"
        )

    rows = evaluate_agent(
        folder,
        suite,
        base_config=base_config,
        on_checkpoint=on_scored,
        on_start=starting,
    )
    if cancelled():
        raise Cancelled()
    rows = sorted(rows, key=lambda r: (r["decisions"], r["checkpoint"]))
    chosen = rows if everything else highlights(rows, folder)
    profile = read_profile(folder)
    milestone = (profile["milestone"] or {}).get("checkpoint")
    best = best_row(rows)["checkpoint"]
    stops, record = [], float("-inf")
    for row in rows:
        new_best = row["share"] > record
        record = max(record, row["share"])
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
    threshold = 0.1 * best["share"]
    scoring = next(
        (i for i, r in enumerate(rows) if r["share"] >= threshold),
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
    """The showcase window. `Showcase(folder, stops, config)` shows stops
    already planned; `Showcase.prepare(agent, config)` opens the window at
    once and plans in the background, showing each step (7c8).
    """

    def __init__(
        self,
        folder: Path,
        stops: list[Stop],
        config: ConfigDict,
        skill: str = DEFAULT_SKILL,
    ) -> None:
        if not stops:
            raise ValueError("no checkpoints to show")
        self._setup(config, skill)
        self._ready(folder, stops)

    @classmethod
    def prepare(
        cls,
        agent: str | Path,
        config: ConfigDict,
        everything: bool = False,
        root: Path | None = None,
        runs_dir: Path | None = None,
        skill: str = DEFAULT_SKILL,
    ) -> "Showcase":
        """The window, open at once on the skill's map, getting ready: the
        plan (scoring what isn't scored yet) runs in the background.
        """
        show = cls.__new__(cls)
        show._setup(config, skill)
        show.status = "Reading the agent's checkpoints"
        show.error: str | None = None
        show._planned = None
        show._closing = False

        def work() -> None:
            try:
                show._planned = plan(
                    agent,
                    everything,
                    root,
                    runs_dir,
                    base_config=config,
                    on_progress=show._say,
                    cancelled=lambda: show._closing,
                )
            except Cancelled:
                pass
            except Exception as error:  # shown in the window, then printed
                show.error = str(error) or type(error).__name__

        show._worker = threading.Thread(target=work, daemon=True)
        show._worker.start()
        return show

    def _say(self, text: str) -> None:
        self.status = text
        print(f"  {text}", flush=True)

    def _setup(self, config: ConfigDict, skill: str) -> None:
        self.config = config.copy_and_resolve_references()
        self.config.show_gui = True
        self.config.window.playback_bar = True  # the bar under the field
        suite = load_suite(DEFAULT_SUITE)
        self.suite = suite
        self.skills = list(suite.scenarios)
        names = [s.name for s in self.skills]
        self.skill_index = names.index(skill) if skill in names else 0
        self.control = PlaybackControl(speed_index=DEFAULT_SPEED)
        self.folder: Path | None = None
        self.stops: list[Stop] = []
        self.heuristic: dict = {}
        self.index = 0
        self.card = True
        self.finished = False  # past the last checkpoint: the summary
        self._build_env()

    def _ready(self, folder: Path, stops: list[Stop]) -> None:
        self.folder, self.stops = folder, stops
        self.heuristic = _cached_heuristic(folder, self.suite)
        if stops:
            self._start(0)

    @property
    def ready(self) -> bool:
        return bool(self.stops)

    @property
    def skill(self):
        """The skill (a suite scenario) whose map and round are played."""
        return self.skills[self.skill_index]

    @property
    def seed(self) -> int:
        return self.skill.first_seed

    def _build_env(self) -> None:
        """The game for the skill's map, rules, and round length."""
        scenario = self.skill
        rules = load_rules(scenario.rules)
        if scenario.round_seconds:
            rules = rules.with_round_seconds(scenario.round_seconds)
        self.env = MazeCarEnv(
            self.config, stage=load_stage(scenario.stage), rules=rules
        )
        self.renderer = self.env.renderer
        sps = self.env.config.sim.steps_per_second
        self.clock = FixedStepClock(sps, max_steps_per_frame=32)
        self.observation, _ = self.env.reset(seed=self.seed)
        self.trail: list[tuple[float, float]] = [self._car_position()]
        # M: the MAPS box lists the skills, each with its map.
        self.renderer.offer_maps(
            [
                MapChoice(
                    f"{s.label} · {s.stage}",
                    json.loads(
                        named_files.find("stages", s.stage).read_text()
                    ),
                )
                for s in self.skills
            ],
            self.skill_index,
        )

    def pick_skill(self, index: int) -> None:
        """The skill picked in the MAPS box (M): its map and round, the
        same checkpoint, from its card.
        """
        self.skill_index = index
        self._build_env()
        if self.ready and not self.finished:
            self._start(self.index)

    # Moving between checkpoints

    def _start(self, index: int) -> None:
        self.index = index
        stop = self.stops[index]
        self.driver = AgentDriver(load_agent(self.folder, stop.checkpoint))
        self.env.driver = f"{self.folder.name}@{stop.checkpoint}"
        self.observation = self._reset()
        self.driver.reset(self.seed)
        self.trail = [self._car_position()]
        self.card = True  # the title card stays until Enter
        self.finished = False

    def _reset(self):
        """The skill's round, as the evaluation played it (braking: at
        speed, aimed at a wall, from the seed).
        """
        observation, _ = self.env.reset(seed=self.seed)
        if self.skill.kind == "braking":
            place_at_wall(self.env, random.Random(self.seed), self.skill.start)
            observation = self.env.last_observation
        return observation

    def next(self) -> None:
        if self.index + 1 < len(self.stops):
            self._start(self.index + 1)
        else:
            self.finished = True
            self.observation = self._reset()  # a calm field under the
            # summary, not the last round's end

    def previous(self) -> None:
        if self.finished:
            self._start(self.index)
        elif self.index > 0:
            self._start(self.index - 1)

    def handle_key(self, key: int) -> None:
        if not self.ready:
            return
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if self.card:
                self.card = False  # start the round
                if self.renderer.map_intro:  # it waited behind the card
                    self.renderer.camera.start_intro()
            elif self.env.is_game_over and not self.finished:
                self.next()  # after reading how the round ended
        elif key == pygame.K_RIGHT:
            self.next()
        elif key == pygame.K_LEFT:
            self.previous()
        else:
            self.control.handle_key(key)

    # Playing

    def tick(self, elapsed: float) -> None:
        """Advances by `elapsed` real seconds."""
        control = self.control
        if self.finished or not self.ready:
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
        if self.card:
            self.clock.advance(0)
            return
        if self.env.is_game_over:
            return  # the round's end stays until Enter
        for _ in range(self.clock.advance(elapsed * control.speed)):
            self._step()
            if self.env.is_game_over:
                break

    def _step(self) -> None:
        if not self.env.is_game_over:
            self.env.step_world(self.driver.act(self.observation))
            self.observation = self.env.last_observation
            if self.env.world.resource(SimClock).step % TRAIL_EVERY == 0:
                self.trail.append(self._car_position())

    def _car_position(self) -> tuple[float, float]:
        transform = self.env.world.component(self.env.car, Transform)
        return transform.x, transform.y

    # What the window shows

    def mode(self) -> ModeInfo:
        if not self.ready:
            stuck = self.error or (
                self._planned is not None and not self._planned[1]
            )
            return ModeInfo(
                "SHOWCASE · getting ready",
                theme.ACCENT,
                SHORTCUTS,
                self._getting_ready(),
                busy=not stuck,  # a spinner while it works
            )
        label = f"SHOWCASE {self.index + 1}/{len(self.stops)}"
        if self.finished:
            return ModeInfo(
                "SHOWCASE", theme.ACCENT, SHORTCUTS, self._summary()
            )
        if self.card:
            messages = self._title()
        elif self.env.is_game_over:
            messages = self._round_end()
        else:
            messages = ()
        return ModeInfo(
            label,
            theme.ACCENT,
            SHORTCUTS,
            messages,
            self._playback(),
            self.trail,
        )

    def _getting_ready(self) -> tuple:
        if self.error:
            return (
                (f"Can't showcase: {self.error}", theme.BAD),
                ("Esc quits", theme.TEXT_DIM),
            )
        if self._planned is not None and not self._planned[1]:
            return (
                ("No scored checkpoints to show yet", theme.WARN),
                ("Esc quits", theme.TEXT_DIM),
            )
        return (
            ("Getting ready", theme.ACCENT),
            (self.status, theme.TEXT),
            (
                f"Then: {self._skill_name()} on {self.skill.stage} "
                "(M: pick another skill)",
                theme.TEXT_DIM,
            ),
            ("Esc, then Enter, cancels", theme.TEXT_DIM),
        )

    def _name(self) -> str:
        """The agent as shown: with its nickname, if it has one (7c10)."""
        nickname = read_profile(self.folder).get("nickname")
        return f"{nickname} · {self.folder.name}" if nickname else (
            self.folder.name
        )

    def _skill_name(self) -> str:
        return self.skill.label or self.skill.name

    def _skill_line(self, scores: dict) -> str:
        """This skill's result for a checkpoint, and its share."""
        value = scores.get(self.skill.column)
        if value is None:
            return f"{self._skill_name()}: not scored"
        if self.skill.kind == "braking":
            text = f"{self._skill_name()}: {value:.0%} clean stops"
        else:
            text = f"{self._skill_name()}: mean {value:,.0f}"
        if self.heuristic.get(self.skill.column) is not None:
            share = shares(scores, self.heuristic, self.suite)[
                self.skill.name
            ]
            text += f" · share {share:.2f} of the heuristic's"
        return text

    def _playback(self) -> PlaybackInfo:
        state = self.env.world.resource(RoundState)
        sps = self.env.config.sim.steps_per_second
        return PlaybackInfo(
            speed=self.control.speed,
            speeds=SPEEDS,
            paused=self.control.paused,
            position=(state.steps_total - state.steps_left) / sps,
            length=state.steps_total / sps,
        )

    def _title(self) -> tuple:
        stop = self.stops[self.index]
        s = stop.scores
        minutes = ""
        if stop.minutes is not None:
            minutes = f" · {stop.minutes:,.1f} min of training"
        lines = [
            (
                f"{self._name()} · {stop.checkpoint} · "
                f"{self.index + 1} of {len(self.stops)}",
                theme.ACCENT,
            ),
            (f"{stop.decisions:,} decisions{minutes}", theme.TEXT),
            (
                f"suite: share {s['share']:.2f} · survival "
                f"{s['survival']:.0%} · wrecks {s['wreck_rate']:.0%} · "
                f"braking {s['braking']:.0%}",
                theme.TEXT,
            ),
            (self._skill_line(s), theme.TEXT),
        ]
        if stop.badges:
            lines.append((" · ".join(stop.badges), theme.GOOD))
        lines.append(("Enter starts · M: another skill", theme.TEXT_DIM))
        return tuple(lines)

    def _round_end(self) -> tuple:
        stop = self.stops[self.index]
        last = self.index + 1 == len(self.stops)
        return (
            (
                f"{stop.checkpoint}: this round {self.env.score:,.0f} "
                f"({self._skill_line(stop.scores)})",
                theme.TEXT,
            ),
            (
                "Enter: the summary" if last else "Enter: the next checkpoint",
                theme.TEXT_DIM,
            ),
        )

    def _summary(self) -> tuple:
        first, last = self.stops[0], self.stops[-1]
        best = max(self.stops, key=lambda s: s.scores["share"])
        lines = [
            (
                f"{self._name()}: {len(self.stops)} checkpoints shown",
                theme.ACCENT,
            ),
            (
                f"{first.checkpoint} {first.scores['share']:.2f}  ->  "
                f"{last.checkpoint} {last.scores['share']:.2f} (share of "
                "the heuristic's)",
                theme.TEXT,
            ),
            (
                f"best: {best.checkpoint} {best.scores['share']:.2f}",
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
        try:
            self._run()
        except KeyboardInterrupt:  # Stop, or Ctrl+C
            print("(stopped)", flush=True)
        finally:
            self._closing = True  # a plan still running stops
        if getattr(self, "error", None):
            print(f"Can't showcase: {self.error}", flush=True)

    def _poll_plan(self) -> None:
        """Takes the plan once the background work is done."""
        planned = getattr(self, "_planned", None)
        if not self.ready and planned is not None and planned[1]:
            self._ready(*planned)

    def _run(self) -> None:
        elapsed = 0.0
        while True:
            self._poll_plan()
            commands = self.renderer.poll_events(game_over=self.finished)
            if Command.QUIT in commands:
                break
            for key in self.renderer.keys_pressed:
                self.handle_key(key)
            picked = self.renderer.take_map_pick()
            if picked is not None:
                self.pick_skill(picked)
            self.tick(0.0 if self.renderer.modal_open else elapsed)
            playing = self.ready and not (self.control.paused or self.card)
            alpha = self.clock.alpha if playing else 1.0
            self.renderer.draw(
                self.env.world, alpha, self.env.reward_status(), self.mode()
            )
            elapsed = self.renderer.present()


def _cached_heuristic(folder: Path, suite) -> dict:
    """The heuristic's scores from the baselines' cache (never scored
    here: just for the title card's shares). {} if there's none.
    """
    path = folder.parent / "baselines" / f"{suite.label}.json"
    try:
        return json.loads(path.read_text())["scores"]["heuristic"]
    except (OSError, ValueError, KeyError):
        return {}
