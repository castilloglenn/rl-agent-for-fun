from dataclasses import astuple

import pygame
from ml_collections import ConfigDict

from src.envs.maze_car.env import MazeCarEnv
from src.sim.components import ActionInput
from src.utils.timing import FixedStepClock


class MazeCarDemo:
    """Human-driven Maze Car: the keyboard is the controller."""

    def __init__(self, config: ConfigDict) -> None:
        config = config.copy_and_resolve_references()
        config.show_gui = True  # the demo is always drawn
        self.env = MazeCarEnv(
            config, driver="You (keyboard)", random_seeds=True
        )
        self.run()

    def run(self) -> None:
        """Fixed-rate simulation steps, drawn at the display's rate."""
        clock = FixedStepClock(self.env.config.sim.steps_per_second)
        elapsed = self.env.render()
        while self.env.running:
            action = astuple(read_keyboard())
            for _ in range(clock.advance(elapsed)):
                self.env.step_world(action)
            elapsed = self.env.render(clock.alpha)


def read_keyboard() -> ActionInput:
    # Pump first so the key state is current for this frame. Pumping
    # leaves the events queued for the renderer to handle.
    pygame.event.pump()
    keys = pygame.key.get_pressed()
    return ActionInput(
        turn_left=keys[pygame.K_a] or keys[pygame.K_LEFT],
        turn_right=keys[pygame.K_d] or keys[pygame.K_RIGHT],
        gas=keys[pygame.K_w] or keys[pygame.K_UP],
        reverse=keys[pygame.K_s] or keys[pygame.K_DOWN],
        brake=keys[pygame.K_SPACE],
    )
