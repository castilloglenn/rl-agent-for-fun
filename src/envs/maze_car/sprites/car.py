import pygame
from absl import flags
from pygame import Rect, Surface, Vector2
from envs.maze_car.models.car_state import CarState

from envs.maze_car.sprites.collision_distance import CollisionDistance
from envs.maze_car.state import StateSingleton
from src.utils.common import (
    get_angular_movement_deltas,
    get_clamped_rect,
)
from src.utils.types import Colors, ColorValue

FLAGS = flags.FLAGS


class Car:
    def __init__(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        color: ColorValue,
        base_speed: float = 300.0,
    ) -> None:
        self._globals = StateSingleton.get_instance()
        self._globals.car = CarState(
            base_speed=base_speed,
            color=color,
            rect_spec=Rect(x, y, width, height),
        )

        self.front_collision = CollisionDistance(
            key="car-front",
            angle=0,
            offset=self.state.rect.width // 2,
            start=self.state.rect.midright,
        )
        self.left_collision = CollisionDistance(
            key="car-left",
            angle=30,
            offset=Vector2(self.state.rect.topright).distance_to(
                Vector2(self.state.rect.center),
            ),
            start=self.state.rect.topright,
        )
        self.right_collision = CollisionDistance(
            key="car-right",
            angle=-30,
            offset=Vector2(self.state.rect.bottomright).distance_to(
                Vector2(self.state.rect.center),
            ),
            start=self.state.rect.bottomright,
        )
        self.back_collision = CollisionDistance(
            key="car-back",
            angle=180,
            offset=self.state.rect.width // 2,
            start=self.state.rect.midleft,
        )
        self._update_vision()

    @property
    def state(self) -> CarState:
        return self._globals.car

    def draw(self, surface: Surface):
        surface.blit(self.state.rotated_surface, self.state.rect)

        if FLAGS.maze_car.show_bounds:
            pygame.draw.rect(surface, Colors.WHITE, self.state.rect, width=1)
        if FLAGS.maze_car.show_collision_distance:
            pygame.draw.line(
                surface=surface,
                color=Colors.WHITE,
                start_pos=self.front_collision.state.start,
                end_pos=self.front_collision.state.end,
            )
            pygame.draw.line(
                surface=surface,
                color=Colors.WHITE,
                start_pos=self.left_collision.state.start,
                end_pos=self.left_collision.state.end,
            )
            pygame.draw.line(
                surface=surface,
                color=Colors.WHITE,
                start_pos=self.right_collision.state.start,
                end_pos=self.right_collision.state.end,
            )
            pygame.draw.line(
                surface=surface,
                color=Colors.WHITE,
                start_pos=self.back_collision.state.start,
                end_pos=self.back_collision.state.end,
            )

    def _update_vision(self):
        self.front_collision.update(rect=self.state.rect, angle=self.state.angle)
        self.left_collision.update(rect=self.state.rect, angle=self.state.angle)
        self.right_collision.update(rect=self.state.rect, angle=self.state.angle)
        self.back_collision.update(rect=self.state.rect, angle=self.state.angle)

    def _turn(self, angle: int):
        adjusted_angle = angle * max(
            self.state.acceleration_rate, FLAGS.maze_car.car.acceleration_unit
        )
        self.state.angle = (self.state.angle + adjusted_angle) % 360
        self.state.rotated_surface = pygame.transform.rotate(
            self.state.surface,
            self.state.angle,
        )
        self.state.rect = self.state.rotated_surface.get_rect(
            center=self.state.rect.center
        )
        self.state.rect.clamp_ip(self._globals.field.rect)
        self._update_vision()

    def turn_left(self) -> None:
        self._turn(angle=self.state.turn_speed)

    def turn_right(self) -> None:
        self._turn(angle=-self.state.turn_speed)

    def _move(self, x: float, y: float):
        self.state.x_float += x - int(x)
        self.state.y_float += y - int(y)

        x_adjusted = int(x) + int(self.state.x_float)
        y_adjusted = int(y) + int(self.state.y_float)

        is_clamped, self.state.rect = get_clamped_rect(
            rect=self.state.rect,
            constraint=self._globals.field.rect,
            new_x=x_adjusted,
            new_y=y_adjusted,
        )

        self.state.x_float -= int(self.state.x_float)
        self.state.y_float -= int(self.state.y_float)

        if is_clamped:
            self.set_speed(speed=0, acceleration_rate=0.0)
        self._update_vision()

    def move_forward(self):
        if self.state.acceleration_rate / FLAGS.maze_car.car.acceleration_max < 0.5:
            rate = self.state.acceleration_rate + (self.state.acceleration_unit * 4)
        else:
            rate = self.state.acceleration_rate + self.state.acceleration_unit
        speed = self.state.forward_speed * rate
        self.set_speed(speed=speed, acceleration_rate=rate)
        delta_x, delta_y = get_angular_movement_deltas(
            angle=self.state.angle, speed=self.state.speed_multiplier
        )
        self._move(x=delta_x, y=delta_y)

    def move_backward(self):
        self.set_speed(speed=self.state.backward_speed, acceleration_rate=0.0)
        delta_x, delta_y = get_angular_movement_deltas(
            angle=self.state.angle, speed=self.state.speed_multiplier
        )
        self._move(x=-delta_x, y=-delta_y)

    def set_speed(self, speed: float, acceleration_rate: float):
        self.state.acceleration_rate = pygame.math.clamp(
            acceleration_rate,
            0.0,
            FLAGS.maze_car.car.acceleration_max,
        )
        self.state.speed_multiplier = speed
