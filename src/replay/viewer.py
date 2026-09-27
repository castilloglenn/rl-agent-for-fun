"""Replay mode: plays a replay file in a simulation window.

    python app.py -replay <file>

SPACE pause, 1-4 speed (0.5x, 1x, 2x, 4x), N one step while paused,
R restart, H lines, Esc quit. The replay is verified up front (a quick
headless re-simulation), so an out-of-date replay is flagged from the
start.
"""

from dataclasses import dataclass
from pathlib import Path

import pygame
from ml_collections import ConfigDict

from src.render import theme
from src.render.panels import ModeInfo, PlaybackInfo
from src.render.renderer import Command
from src.replay.format import Replay, read_replay
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
    def __init__(self, replay: Replay, config: ConfigDict) -> None:
        """config: presentation settings (HUD, display) to use. The game
        itself always comes from the replay.
        """
        self.verification = Replayer(replay, base_config=config).run()
        config = config.copy_and_resolve_references()
        config.window.playback_bar = True  # the bar under the field
        self.replayer = Replayer(replay, show_gui=True, base_config=config)
        self.renderer = self.replayer.env.renderer
        steps_per_second = self.replayer.env.config.sim.steps_per_second
        # 4x speed needs up to 8 steps per frame at 60 Hz.
        self.clock = FixedStepClock(steps_per_second, max_steps_per_frame=32)
        self.control = PlaybackControl()
        self.running = True
        self.trail: list[tuple[float, float]] = []  # where the car has been
        self._start_trail()

    @staticmethod
    def open(path: str | Path, config: ConfigDict) -> "ReplayViewer":
        return ReplayViewer(read_replay(path), config)

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
            label, color, SHORTCUTS, messages, playback, self.trail
        )

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
            self.tick(0.0 if self.renderer.modal_open else elapsed)
            env = self.replayer.env
            alpha = 1.0 if self.control.paused else self.clock.alpha
            self.renderer.draw(
                env.world, alpha, env.reward_status(), self.mode()
            )
            elapsed = self.renderer.present()


def _end_messages(verification: Verification) -> tuple:
    if verification.ok:
        lines = [("REPLAY ENDED: verified, matches the recording", theme.GOOD)]
    else:
        lines = [("REPLAY ENDED: OUT OF DATE", theme.BAD)]
        lines += [(problem, theme.BAD) for problem in verification.problems]
    lines += [(note, theme.TEXT_DIM) for note in verification.notes]
    return tuple(lines)
