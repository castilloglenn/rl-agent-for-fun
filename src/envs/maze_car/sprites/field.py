import pygame
from absl import flags

from envs.maze_car.models.field_state import GameFieldState
from envs.maze_car.models.state import StateSingleton
from utils.types import Colors, ColorValue
from utils.ui import get_window_constants

FLAGS = flags.FLAGS


class GameField:
    def __init__(self) -> None:
        self._state = StateSingleton()

        window = get_window_constants(config=FLAGS.maze_car)
        x = window.width * 0.025
        y = window.half_height * 0.325
        width = window.width * 0.95
        height = window.height * 0.8
        color: ColorValue = Colors.WHITE

        field_state = GameFieldState(x, y, width, height, color)
        self._state.game_field = field_state

    @property
    def state(self) -> GameFieldState:
        return self._state.game_field

    def draw(self, surface: pygame.Surface):
        pygame.draw.rect(surface, self.state.color, self.state.rect, 1)
