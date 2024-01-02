# pylint: disable=E1101
import sys
from dataclasses import dataclass
from typing import Optional

import pygame
from absl import flags
from pygame.surface import Surface

from src.envs.base import Environment
from src.utils.types import Colors, ColorValue, GameOver, Reward, Score
from src.utils.ui import get_window_constants, rotate_surface

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


class Car:
    def __init__(
        self, x: int, y: int, width: int, height: int, color: ColorValue
    ) -> None:
        self.x = x
        self.y = y

        self.width = width
        self.height = height
        self.color = color

        self.rect = None
        self.angle = 0

    @property
    def surface(self) -> Surface:
        surface = Surface((self.width, self.height), pygame.SRCALPHA, 32)
        surface.fill(self.color)
        rotated_surface = rotate_surface(surface, self.angle)
        self.rect = rotated_surface.get_rect()
        return rotated_surface

    @property
    def position(self) -> tuple:
        return (self.x - self.rect.width // 2, self.y - self.rect.height // 2)

    def tweak_angle(self, angle: int) -> None:
        self.angle = (self.angle + angle) % 360


class MazeCarEnv(Environment):
    def __init__(self) -> None:
        window = get_window_constants(config=FLAGS.maze_car)

        pygame.init()
        pygame.display.set_caption(window.title)

        self.clock = pygame.time.Clock()
        self.display = pygame.display.set_mode((window.width, window.height))

        self.reset()

    def reset(self) -> None:
        window = get_window_constants(config=FLAGS.maze_car)
        self.action_state: ActionState = ActionState()
        self.car = Car(
            x=window.half_width - FLAGS.maze_car.car.width // 2,
            y=window.half_height - FLAGS.maze_car.car.height // 2,
            width=FLAGS.maze_car.car.width,
            height=FLAGS.maze_car.car.height,
            color=Colors.RED,
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
        self.apply_actions()

        reward: int | float = self._calculate_reward()
        game_over: bool = False

        self.update_display()

        return (reward, game_over, self.score)

    def apply_actions(self):
        if self.action_state.turn_left:
            self.car.tweak_angle(angle=5)
        elif self.action_state.turn_right:
            self.car.tweak_angle(angle=-5)

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
