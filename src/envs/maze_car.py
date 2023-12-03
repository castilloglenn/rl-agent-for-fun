import sys
from typing import Optional

import pygame
from absl import flags

from src.envs.base import Environment
from src.utils.types import GameOver, Reward, Score

FLAGS = flags.FLAGS


# pylint: disable=E1101
class MazeCarEnv(Environment):
    def __init__(self) -> None:
        self.demo_mode: bool = FLAGS.demo == FLAGS.maze_car.code

        pygame.init()
        pygame.display.set_caption(FLAGS.maze_car.window.title)

        self.clock = pygame.time.Clock()
        self.display = pygame.display.set_mode(
            (FLAGS.maze_car.window.width, FLAGS.maze_car.window.height)
        )
        self.running: bool = True
        self.reset()

        if self.demo_mode:
            self.run_demo()

    def run_demo(self):
        while self.running:
            self.game_step()

    def reset(self) -> None:
        self.score: int | float = 0

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

    def update_display(self, rectangle: tuple = None):
        pygame.display.update(rectangle)
        self.clock.tick(FLAGS.maze_car.display.fps)

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                pygame.quit()
                sys.exit()

            if not self.demo_mode:
                continue
