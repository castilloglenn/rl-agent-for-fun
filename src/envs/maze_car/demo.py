from dataclasses import astuple

import pygame
from ml_collections import ConfigDict

from src.envs.maze_car.env import MazeCarEnv
from src.sim.components import ActionInput


class MazeCarDemo:
    """Human-driven Maze Car: the keyboard is the controller."""

    def __init__(self, config: ConfigDict) -> None:
        config = config.copy_and_resolve_references()
        config.show_gui = True  # the demo is always drawn
        self.env = MazeCarEnv(config, driver="You (keyboard)")
        self.run()

    def run(self) -> None:
        while self.env.running:
            self.env.game_step(astuple(read_keyboard()))


def read_keyboard() -> ActionInput:
    # Pump first so the key state is current for this frame. Pumping
    # leaves the events queued for the renderer to handle.
    pygame.event.pump()
    keys = pygame.key.get_pressed()
    return ActionInput(
        turn_left=keys[pygame.K_a] or keys[pygame.K_LEFT],
        turn_right=keys[pygame.K_d] or keys[pygame.K_RIGHT],
        move_forward=keys[pygame.K_w] or keys[pygame.K_UP],
        move_backward=keys[pygame.K_s] or keys[pygame.K_DOWN],
    )
