import pygame
from absl import flags

from envs.maze_car.models.field_state import FieldState
from envs.maze_car.state import StateSingleton
from utils.types import Colors, ColorValue
from utils.ui import get_window_constants

FLAGS = flags.FLAGS


class FieldSingleton:
    _instance = None

    def __init__(self) -> None:
        window = get_window_constants(config=FLAGS.maze_car)

        self._globals = StateSingleton.get_instance()
        self._globals.field = FieldState(
            x=window.width * 0.025,
            y=window.half_height * 0.325,
            width=window.width * 0.95,
            height=window.height * 0.8,
            color=Colors.WHITE,
        )

    @classmethod
    def get_instance(cls):
        if not cls._instance:
            cls._instance = cls()
        return cls._instance

    @property
    def state(self) -> FieldState:
        return self._globals.field

    @property
    def rect(self) -> pygame.Rect:
        return self.state.rect

    @property
    def color(self) -> ColorValue:
        return self.state.color

    def draw(self, surface: pygame.Surface):
        pygame.draw.rect(surface, self.color, self.rect, 1)
