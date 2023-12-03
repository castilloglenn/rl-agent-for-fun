import pygame
from absl import flags

from src.envs.base import Environment, GameOver, Reward, Score

FLAGS = flags.FLAGS

WIDTH = FLAGS.maze_car.window.width
HEIGHT = FLAGS.maze_car.window.height
FPS = FLAGS.maze_car.display.fps


class MazeCarEnv(Environment):
    def __init__(self, user_inputs: bool = False) -> None:
        self.user_inputs = user_inputs

        # pylint: disable=E1101
        pygame.init()
        pygame.display.set_caption(FLAGS.maze_car.window.title)

        self.clock = pygame.time.Clock()
        self.display = pygame.display.set_mode((WIDTH, HEIGHT))

        self.reset()

    def reset(self) -> None:
        pass

    def get_state(self) -> tuple:
        pass

    def game_step(self, action) -> tuple[Reward, GameOver, Score]:
        pass
