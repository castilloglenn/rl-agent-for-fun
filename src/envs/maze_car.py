# pylint: disable=E1101
from dataclasses import dataclass
from typing import Optional

import pygame
from absl import flags
from pygame import Rect, Surface, Vector2

from src.envs.base import Environment
from src.utils.common import (
    get_angular_movement_deltas,
    get_clamped_rect,
    get_extended_point,
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


class Car:
    def __init__(
        self,
        field: Field,
        x: int,
        y: int,
        width: int,
        height: int,
        color: ColorValue,
        forward_speed: int = 300,
        turn_speed: int = 240,
    ) -> None:
        self.x: int = x
        self.y: int = y
        self.width: int = width
        self.height: int = height

        self.surface = Surface((self.width, self.height), pygame.SRCALPHA, 32)
        self.surface.fill(color)

        self.rect = self.surface.get_rect()
        self.rect.center = (self.x, self.y)

        pygame.draw.polygon(
            surface=self.surface,
            color=Colors.WHITE,
            points=get_triangle_coordinates_from_rect(self.rect),
        )

        self.rotated_surface = self.surface.copy()

        self.front_point = Vector2(self.rect.midright)
        self.field = field

        single_frame: float = 1 / FLAGS.maze_car.display.fps
        self.base_speed: float = forward_speed
        self.forward_speed: float = self.base_speed * single_frame
        self.backward_speed: float = self.forward_speed / 4
        self.turn_speed: float = turn_speed * single_frame
        self.acceleration_unit: float = (
            FLAGS.maze_car.car.acceleration_unit * single_frame
        )

        self.acceleration_rate: float = 0.0
        self.speed_multiplier: float = 0
        self.angle: int = 0

    def _update_front_point(self):
        self.front_point = get_extended_point(
            start_point=Vector2(self.rect.center),
            angle=self.angle,
            distance=self.width // 2,
        )
        if FLAGS.maze_car.show_bounds:
            pygame.draw.rect(
                self.rotated_surface,
                Colors.WHITE,
                self.rect,
                width=1,
            )

    def _turn(self, angle: int):
        self.angle = (self.angle + angle) % 360
        self.rotated_surface = rotate_surface(self.surface, self.angle)
        self.rect = self.rotated_surface.get_rect(center=self.rect.center)
        self._update_front_point()

    def turn_left(self) -> None:
        self._turn(angle=self.turn_speed)

    def turn_right(self) -> None:
        self._turn(angle=-self.turn_speed)

    def _move(self, x: int, y: int):
        self.rect = get_clamped_rect(
            rect=self.rect,
            constraint=self.field.rect,
            new_x=x,
            new_y=y,
        )
        self._update_front_point()

    def move_forward(self):
        if self.acceleration_rate / FLAGS.maze_car.car.acceleration_max < 0.5:
            rate = self.acceleration_rate + (self.acceleration_unit * 4)
        else:
            rate = self.acceleration_rate + self.acceleration_unit
        speed = self.forward_speed * rate
        self.set_speed(speed=speed, acceleration_rate=rate)
        delta_x, delta_y = get_angular_movement_deltas(
            angle=self.angle, speed=self.speed_multiplier
        )
        self._move(x=delta_x, y=delta_y)

    def move_backward(self):
        self.set_speed(speed=self.backward_speed, acceleration_rate=0.0)
        delta_x, delta_y = get_angular_movement_deltas(
            angle=self.angle, speed=self.speed_multiplier
        )
        self._move(x=-delta_x, y=-delta_y)

    def set_speed(self, speed: float, acceleration_rate: float):
        self.acceleration_rate = pygame.math.clamp(
            acceleration_rate,
            0.0,
            FLAGS.maze_car.car.acceleration_max,
        )
        self.speed_multiplier = speed


class MazeCarEnv(Environment):
    def __init__(self) -> None:
        window = get_window_constants(config=FLAGS.maze_car)

        pygame.init()
        pygame.display.set_caption(window.title)

        self.clock = pygame.time.Clock()
        self.display = pygame.display.set_mode((window.width, window.height))

        self.field = Field()
        self.reset()

    def reset(self) -> None:
        window = get_window_constants(config=FLAGS.maze_car)
        self.action_state: ActionState = ActionState()
        self.car = Car(
            field=self.field,
            x=window.half_width - FLAGS.maze_car.car.width // 2,
            y=(window.height * 0.58) - FLAGS.maze_car.car.height // 2,
            width=FLAGS.maze_car.car.width,
            height=FLAGS.maze_car.car.height,
            color=Colors.SKY_BLUE,
        )
        self.score: int | float = 0
        self.is_game_over: bool = False
        self.running: bool = True

    def get_state(self) -> tuple:
        pass

    def game_step(
        self, action: Optional[tuple] = None
    ) -> tuple[Reward, GameOver, Score]:
        self.handle_events(action)
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

    def handle_events(self, action):
        self.action_state = ActionState.from_tuple(action)
        if FLAGS.maze_car.show_gui:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False

    def render_texts(self):
        a = self.car.acceleration_rate / FLAGS.maze_car.car.acceleration_max
        s = self.car.base_speed * self.car.speed_multiplier

        sep = " | "
        spd = f"Speed: {s:,.0f} px/s"
        acc = f"Acceleration: {a*100:,.0f}%"
        agl = f"Angle: {self.car.angle:.0f}°"
        rec = f"Rect: {(self.car.rect)}"
        cen = f"Center: {(self.car.rect.center)}"

        window = get_window_constants(config=FLAGS.maze_car)
        draw_texts(
            surface=self.display,
            texts=[
                rec + sep + cen + sep + agl,
                spd + sep + acc,
            ],
            size=20,
            x=window.width * 0.025,
            y=window.half_height * 0.075,
        )
