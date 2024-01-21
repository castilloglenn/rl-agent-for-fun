from dataclasses import dataclass, field

from pygame import Rect, Surface
from absl import flags
import pygame
from utils.common import get_triangle_coordinates_from_rect

from utils.types import ColorValue, Colors

FLAGS = flags.FLAGS


@dataclass
class CarState:
    forward_speed: float = 0.0
    turn_speed: int = 0
    color: ColorValue = Colors.WHITE
    rect_spec: Rect = field(default_factory=lambda: Rect(0, 0, 0, 0))

    acceleration_rate: float = 0.0
    speed_multiplier: float = 0
    angle: int = 0
    x_float: float = 0.0
    y_float: float = 0.0

    base_speed: float = field(init=False)
    acceleration_unit: float = field(init=False)
    backward_speed: float = field(init=False)

    surface: Surface = field(init=False)
    rect: Rect = field(init=False)
    rotated_surface: Surface = field(init=False)

    def __post_init__(self):
        single_frame: float = 1 / FLAGS.maze_car.display.fps
        self.base_speed = self.forward_speed
        self.forward_speed = self.base_speed * single_frame
        self.backward_speed = self.forward_speed / 4
        self.turn_speed = self.turn_speed * single_frame
        self.acceleration_unit: float = (
            FLAGS.maze_car.car.acceleration_unit * single_frame
        )

        self.surface = Surface(
            (self.rect_spec.width, self.rect_spec.height),
            pygame.SRCALPHA,
            32,
        )
        self.surface.fill(self.color)

        self.rect = self.surface.get_rect()
        self.rect.center = (self.rect_spec.x, self.rect_spec.y)
        self._create_car_design()
        self.rotated_surface = self.surface.copy()

    def _create_car_design(self):
        pygame.draw.polygon(
            surface=self.surface,
            color=Colors.WHITE,
            points=get_triangle_coordinates_from_rect(self.rect),
        )
