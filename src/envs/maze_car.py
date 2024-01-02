# pylint: disable=E1101
import sys
from dataclasses import dataclass
from typing import Optional

import pygame
from absl import flags
from pygame import Rect, Surface

from src.envs.base import Environment
from src.utils.common import (
    get_angular_movement_deltas,
    get_triangle_coordinates_from_rect,
)
from src.utils.types import Colors, ColorValue, GameOver, Reward, Score
from src.utils.ui import draw_texts, get_window_constants, rotate_surface

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

    @property
    def is_moving(self):
        return self.move_forward or self.move_backward

    def to_tuple(self) -> tuple:
        return tuple(self.__dict__.values())


class Car:
    def __init__(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        color: ColorValue,
        forward_speed: int = 150,
        turn_speed: int = 240,
    ) -> None:
        self.x: int = x
        self.y: int = y

        self.width: int = width
        self.height: int = height
        self.color: ColorValue = color
        self.rect: Rect = None

        single_frame: float = 1 / FLAGS.maze_car.display.fps
        self.base_speed = forward_speed
        self.forward_speed: float = self.base_speed * single_frame
        self.backward_speed: float = self.forward_speed / 2
        self.turn_speed: float = turn_speed * single_frame
        self.acceleration_unit: float = (
            FLAGS.maze_car.car.acceleration_unit * single_frame
        )

        self.acceleration_rate: float = 0.0
        self.speed: int = 0
        self.angle: int = 0

    @property
    def surface(self) -> Surface:
        surface = Surface((self.width, self.height), pygame.SRCALPHA, 32)
        surface.fill(self.color)
        pygame.draw.polygon(
            surface,
            Colors.WHITE,
            get_triangle_coordinates_from_rect(surface.get_rect()),
        )
        rotated_surface = rotate_surface(surface, self.angle)
        self.rect = rotated_surface.get_rect()

        if FLAGS.maze_car.show_bounds:
            pygame.draw.rect(
                rotated_surface,
                Colors.WHITE,
                rotated_surface.get_rect(),
                width=1,
            )

        return rotated_surface

    @property
    def position(self) -> tuple:
        return (self.x - self.rect.width // 2, self.y - self.rect.height // 2)

    def turn_left(self) -> None:
        self.angle = (self.angle + self.turn_speed) % 360

    def turn_right(self) -> None:
        self.angle = (self.angle - self.turn_speed) % 360

    def move_forward(self):
        acceleration_rate = pygame.math.clamp(
            self.acceleration_rate + self.acceleration_unit,
            0.0,
            FLAGS.maze_car.car.acceleration_max,
        )
        speed = self.forward_speed * self.acceleration_rate
        self.set_speed(speed=speed, acceleration_rate=acceleration_rate)
        delta_x, delta_y = get_angular_movement_deltas(
            angle=self.angle, speed=self.speed
        )
        self.x += delta_x
        self.y += delta_y

    def move_backward(self):
        self.set_speed(speed=self.backward_speed, acceleration_rate=0.0)
        delta_x, delta_y = get_angular_movement_deltas(
            angle=self.angle, speed=self.speed
        )
        self.x -= delta_x
        self.y -= delta_y

    def set_speed(self, speed: float, acceleration_rate: float):
        self.acceleration_rate = pygame.math.clamp(
            acceleration_rate,
            0.0,
            FLAGS.maze_car.car.acceleration_max,
        )
        self.speed = speed


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
        if FLAGS.maze_car.show_gui:
            self.handle_events()
        else:
            self.action_state = ActionState.from_tuple(action)

        self.apply_actions()

        if FLAGS.maze_car.show_gui:
            self.draw_assets()
            self.update_display()

        reward: int | float = self._calculate_reward()
        game_over: bool = False

        return (reward, game_over, self.score)

    def apply_actions(self):
        if self.action_state.turn_left:
            if self.action_state.move_backward:
                self.car.turn_right()
            else:
                self.car.turn_left()
        elif self.action_state.turn_right:
            if self.action_state.move_backward:
                self.car.turn_left()
            else:
                self.car.turn_right()

        if self.action_state.move_forward:
            self.car.move_forward()
        elif self.action_state.move_backward:
            self.car.move_backward()

        if not self.action_state.is_moving:
            self.car.set_speed(speed=0, acceleration_rate=0.0)

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

    def render_texts(self):
        spd = f"Speed: {self.car.base_speed * self.car.speed:,.0f} px/s"
        agl = f"Angle: {self.car.angle:.0f}°"

        draw_texts(
            surface=self.display,
            texts=[
                f"{spd} | {agl}",
            ],
            size=20,
            x=20,
            y=20,
        )
