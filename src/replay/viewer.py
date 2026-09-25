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
from src.render.panels import ModeInfo
from src.render.renderer import Command
from src.replay.format import Replay, read_replay
from src.replay.replayer import Replayer, Verification
from src.utils.timing import FixedStepClock

SPEEDS = (0.5, 1.0, 2.0, 4.0)
SPEED_KEYS = {pygame.K_1: 0, pygame.K_2: 1, pygame.K_3: 2, pygame.K_4: 3}
HINTS = "SPACE pause  1-4 speed  N step  R restart  H lines"


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
        if key == pygame.K_SPACE:
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
        self.replayer = Replayer(replay, show_gui=True, base_config=config)
        self.renderer = self.replayer.env.renderer
        steps_per_second = self.replayer.env.config.sim.steps_per_second
        # 4x speed needs up to 8 steps per frame at 60 Hz.
        self.clock = FixedStepClock(steps_per_second, max_steps_per_frame=32)
        self.control = PlaybackControl()
        self.running = True

    @staticmethod
    def open(path: str | Path, config: ConfigDict) -> "ReplayViewer":
        return ReplayViewer(read_replay(path), config)

    def tick(self, elapsed: float) -> None:
        """Advances playback by `elapsed` real seconds."""
        control = self.control
        if control.restart_requested:
            self.replayer.restart()
            control.restart_requested = False
        if control.paused:
            for _ in range(control.step_requests):
                self.replayer.step()
            control.step_requests = 0
            self.clock.advance(0)
            return
        for _ in range(self.clock.advance(elapsed * control.speed)):
            if not self.replayer.step():
                break

    def mode(self) -> ModeInfo:
        state = "PAUSED" if self.control.paused else f"{self.control.speed:g}×"
        if self.verification.ok:
            label, color = f"REPLAY {state} · verified", theme.GOOD
        else:
            label, color = f"REPLAY {state} · OUT OF DATE", theme.BAD
        messages = ()
        if self.replayer.done:
            messages = _end_messages(self.verification)
        return ModeInfo(label, color, HINTS, messages)

    def run(self) -> None:
        elapsed = 0.0
        while self.running:
            commands = self.renderer.poll_events()
            if Command.QUIT in commands:
                break
            for key in self.renderer.keys_pressed:
                self.control.handle_key(key)
            self.tick(elapsed)
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
