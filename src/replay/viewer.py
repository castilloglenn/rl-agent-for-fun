"""Replay mode: plays a replay file in a simulation window.

    python app.py -replay <file>

SPACE pause, 1-4 speed (0.5x, 1x, 2x, 4x), N one step while paused,
R restart, H lines, Esc quit. The replay is verified up front (a quick
headless re-simulation), so an out-of-date replay is flagged from the
start. The SOURCE card says where it comes from, and a run's best replay
of a mix offers each map's best (M).
"""

from dataclasses import dataclass
from pathlib import Path

import pygame
from ml_collections import ConfigDict

from src.render import theme
from src.render.map_picker import MapChoice
from src.render.panels import ModeInfo, PlaybackInfo, mind_of
from src.render.renderer import Command
from src.replay.format import Replay, read_replay
from src.replay.source import source_rows
from src.replay.replayer import Replayer, Verification
from src.sim.components import Transform
from src.utils.timing import FixedStepClock

SPEEDS = (0.5, 1.0, 2.0, 4.0)
SPEED_KEYS = {pygame.K_1: 0, pygame.K_2: 1, pygame.K_3: 2, pygame.K_4: 3}
TRAIL_EVERY = 2  # steps between the trail's points (60 per second)
SHORTCUTS = (
    ("SPACE / P", "pause / resume"),
    ("1-4", "speed: 0.5x, 1x, 2x, 4x"),
    ("N", "one step while paused"),
    ("R", "restart"),
    ("H", "lines"),
    ("F", "camera: follow or fit (big stages)"),
    ("T", "trail: where the car has been"),
    ("?", "these shortcuts"),
    ("Esc", "quit (asks first)"),
)


@dataclass
class PlaybackControl:
    """Pause, speed, and frame stepping, driven by key presses."""

    speed_index: int = 1  # 1x
    paused: bool = False
    step_requests: int = 0
    restart_requested: bool = False

    @property
    def speed(self) -> float:
        return SPEEDS[self.speed_index]

    def handle_key(self, key: int) -> None:
        if key in (pygame.K_SPACE, pygame.K_p):
            self.paused = not self.paused
        elif key in SPEED_KEYS:
            self.speed_index = SPEED_KEYS[key]
        elif key == pygame.K_n and self.paused:
            self.step_requests += 1
        elif key == pygame.K_r:
            self.restart_requested = True


class ReplayViewer:
    def __init__(
        self,
        replay: Replay,
        config: ConfigDict,
        path: str | Path | None = None,
    ) -> None:
        """config: presentation settings (HUD, display) to use. The game
        itself always comes from the replay. path: its file, for the
        SOURCE card (an episode's number is in its name).
        """
        self.base_config = config
        self.control = PlaybackControl()
        self.running = True
        self.bests: list[Path] = []  # a mixed run's best replay per map
        self._load(replay, path)

    @staticmethod
    def open(path: str | Path, config: ConfigDict) -> "ReplayViewer":
        return ReplayViewer(read_replay(path), config, path)

    def _load(self, replay: Replay, path: str | Path | None) -> None:
        self.path = Path(path) if path else None
        self.source = source_rows(replay.header, self.path)
        base = self.base_config
        self.verification = Replayer(replay, base_config=base).run()
        config = self.base_config.copy_and_resolve_references()
        config.window.playback_bar = True  # the bar under the field
        self.replayer = Replayer(replay, show_gui=True, base_config=config)
        self.renderer = self.replayer.env.renderer
        steps_per_second = self.replayer.env.config.sim.steps_per_second
        # 4x speed needs up to 8 steps per frame at 60 Hz.
        self.clock = FixedStepClock(steps_per_second, max_steps_per_frame=32)
        self.trail: list[tuple[float, float]] = []  # where the car has been
        self._start_trail()
        self._offer_bests()
        self.mind = _mind_driver(replay.header)  # an exact checkpoint only

    def offer_bests(self, paths: list[Path]) -> None:
        """A run's best replay on each of its maps: M picks one (with two
        maps or more: a mix).
        """
        self.bests = [Path(p) for p in paths]
        self._offer_bests()

    def _offer_bests(self) -> None:
        if len(self.bests) < 2:
            return
        choices = []
        for path in self.bests:
            stage = read_replay(path).header["stage"]
            score = path.name.rsplit("_score", 1)[-1].split(".")[0]
            choices.append(
                MapChoice(f"{stage['name']} · best {score}", stage)
            )
        playing = self.path in self.bests
        current = self.bests.index(self.path) if playing else -1
        self.renderer.offer_maps(choices, current)

    def play_best(self, index: int) -> None:
        """Another map's best replay, in this window's playback state."""
        path = self.bests[index]
        self._load(read_replay(path), path)

    def tick(self, elapsed: float) -> None:
        """Advances playback by `elapsed` real seconds."""
        control = self.control
        if control.restart_requested:
            self.replayer.restart()
            self._start_trail()
            control.restart_requested = False
        if control.paused:
            for _ in range(control.step_requests):
                self._step()
            control.step_requests = 0
            self.clock.advance(0)
            return
        for _ in range(self.clock.advance(elapsed * control.speed)):
            if not self._step():
                break

    def _step(self) -> bool:
        """One replay step, adding to the trail. False once it's over."""
        more = self.replayer.step()
        if self.replayer.step_index % TRAIL_EVERY == 0:
            self._add_trail_point()
        return more

    def _start_trail(self) -> None:
        self.trail = []
        self._add_trail_point()

    def _add_trail_point(self) -> None:
        env = self.replayer.env
        transform = env.world.component(env.car, Transform)
        self.trail.append((transform.x, transform.y))

    def mode(self) -> ModeInfo:
        if self.verification.ok:
            label, color = "REPLAY · verified", theme.GOOD
        else:
            label, color = "REPLAY · OUT OF DATE", theme.BAD
        messages = ()
        if self.replayer.done:
            messages = _end_messages(self.verification)
        sps = self.replayer.env.config.sim.steps_per_second
        playback = PlaybackInfo(
            speed=self.control.speed,
            speeds=SPEEDS,
            paused=self.control.paused,
            position=self.replayer.step_index / sps,
            length=self.replayer.total_steps / sps,
        )
        return ModeInfo(
            label,
            color,
            SHORTCUTS,
            messages,
            playback,
            self.trail,
            source=self.source,
            mind=self._mind(),
        )

    def _mind(self):
        """What the replay's agent thinks of this moment (7f7): its
        network, run on the replayed observation.
        """
        if self.mind is None:
            return None
        self.mind.reset(0)  # decide now, on this observation
        self.mind.act(self.replayer.env.last_observation)
        return mind_of(self.mind)

    def run(self) -> None:
        try:
            self._run()
        except KeyboardInterrupt:  # Stop, or Ctrl+C
            print("(stopped)", flush=True)

    def _run(self) -> None:
        elapsed = 0.0
        while self.running:
            commands = self.renderer.poll_events(game_over=self.replayer.done)
            if Command.QUIT in commands:
                break
            for key in self.renderer.keys_pressed:
                self.control.handle_key(key)
            picked = self.renderer.take_map_pick()
            if picked is not None:  # M: another map's best
                self.play_best(picked)
            self.tick(0.0 if self.renderer.modal_open else elapsed)
            env = self.replayer.env
            alpha = 1.0 if self.control.paused else self.clock.alpha
            self.renderer.draw(
                env.world, alpha, env.reward_status(), self.mode()
            )
            elapsed = self.renderer.present()


def _mind_driver(header: dict):
    """The replay's agent at its exact checkpoint, if the replay names
    one and it still exists (training replays come from weights that kept
    changing: none).
    """
    slot = (header.get("slots") or {}).get("1") or {}
    if slot.get("type") != "agent" or not slot.get("checkpoint"):
        return None
    try:
        from src.agents.driver import AgentDriver
        from src.agents.store import load_agent

        return AgentDriver(load_agent(slot["id"], slot["checkpoint"]))
    except Exception:  # gone, or from another observation: no MIND
        return None


def _end_messages(verification: Verification) -> tuple:
    if verification.ok:
        lines = [("REPLAY ENDED: verified, matches the recording", theme.GOOD)]
    else:
        lines = [("REPLAY ENDED: OUT OF DATE", theme.BAD)]
        lines += [(problem, theme.BAD) for problem in verification.problems]
    lines += [(note, theme.TEXT_DIM) for note in verification.notes]
    return tuple(lines)
