import pygame
from absl import flags
from pygame import Rect, Surface

from utils.types import Colors, ColorValue
from utils.ui import get_window_constants

FLAGS = flags.FLAGS


class Field:
    def __init__(self):
        window = get_window_constants(config=FLAGS.maze_car)
        self.x = window.width * 0.025
        self.y = window.half_height * 0.325
        self.width = window.width * 0.95
        self.height = window.height * 0.8
        self.color: ColorValue = Colors.WHITE

        self.rect = Rect(self.x, self.y, self.width, self.height)

    def draw(self, surface: Surface):
        pygame.draw.rect(surface, self.color, self.rect, 1)
