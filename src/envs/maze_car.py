import sys
from dataclasses import dataclass
from typing import Optional

import pygame
from absl import flags
from pygame.surface import Surface

from src.envs.base import Environment
from src.utils.types import GameOver, Reward, Score
from src.utils.ui import get_window_constants

FLAGS = flags.FLAGS


@dataclass
class ActionState:
    turn_left: bool = False
    turn_right: bool = False
    move_forward: bool = False
    move_backward: bool = False

    @staticmethod
    def from_tuple(data: tuple) -> "ActionState":
        return ActionState(*data)

    def to_tuple(self) -> tuple:
        return tuple(self.__dict__.values())


# pylint: disable=E1101
class MazeCarEnv(Environment):
    def __init__(self) -> None:
        window = get_window_constants(config=FLAGS.maze_car)

        pygame.init()
        pygame.display.set_caption(window.title)

        self.clock = pygame.time.Clock()
        self.display = pygame.display.set_mode((window.width, window.height))

        self.reset()

    def reset(self) -> None:
        self.action_state: ActionState = ActionState()
        self.car_surface = Surface(
            (FLAGS.maze_car.car.width, FLAGS.maze_car.car.height)
        )
        self.score: int | float = 0
        self.is_game_over: bool = False
        self.running: bool = True

    def get_state(self) -> tuple:
        pass

    def game_step(
        self, action: Optional[tuple] = None
    ) -> tuple[Reward, GameOver, Score]:
        self.handle_events()

        reward: int | float = self._calculate_reward()
        game_over: bool = False

        self.update_display()

        return (reward, game_over, self.score)

    def _calculate_reward(self) -> int | float:
        return 0

    def update_display(self):
        pygame.display.update()
        self.clock.tick(FLAGS.maze_car.display.fps)

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                pygame.quit()
                sys.exit()
