# pylint: disable=E1101
import pygame
from absl import flags
from pygame import Rect, Surface, Vector2

from src.utils.common import (
    get_angular_movement_deltas,
    get_clamped_rect,
    get_extended_point,
    get_triangle_coordinates_from_rect,
)
from src.utils.types import Colors, ColorValue, Coordinate
from src.utils.ui import get_window_constants

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


class CollisionVision:
    def __init__(
        self,
        angle: int,
        offset: int,
        start: Coordinate,
        field: Field,
    ) -> None:
        self.angle = angle
        self.offset = offset
        self.start = Vector2(start)
        self.end = Vector2(start)
        self.field = field

        self.distance: int = 0

    def update(self, rect: Rect, angle: int) -> None:
        angle_with_offset = (angle + self.angle) % 360
        self.start = get_extended_point(
            start_point=Vector2(rect.center),
            angle=angle_with_offset,
            distance=self.offset,
        )
        window = get_window_constants(config=FLAGS.maze_car)
        max_front = get_extended_point(
            start_point=self.start,
            angle=angle_with_offset,
            distance=max(window.width, window.height),
        )
        collide_points = self.field.rect.clipline(self.start, max_front)
        self.end = Vector2(
            collide_points[1] if collide_points else self.start,
        )
        self.distance = self.start.distance_to(self.end)


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
        self.acceleration_rate: float = 0.0
        self.speed_multiplier: float = 0
        self.angle: int = 0

        single_frame: float = 1 / FLAGS.maze_car.display.fps
        self.base_speed: float = forward_speed
        self.forward_speed: float = self.base_speed * single_frame
        self.backward_speed: float = self.forward_speed / 4
        self.turn_speed: float = turn_speed * single_frame
        self.acceleration_unit: float = (
            FLAGS.maze_car.car.acceleration_unit * single_frame
        )

        self.x: int = x
        self.y: int = y
        self.width: int = width
        self.height: int = height

        self.field = field

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

        self.front_collision = CollisionVision(
            angle=0,
            offset=self.width // 2,
            start=self.rect.midright,
            field=self.field,
        )
        self.left_collision = CollisionVision(
            angle=30,
            offset=Vector2(self.rect.topright).distance_to(
                Vector2(self.rect.center),
            ),
            start=self.rect.topright,
            field=self.field,
        )
        self.right_collision = CollisionVision(
            angle=-30,
            offset=Vector2(self.rect.bottomright).distance_to(
                Vector2(self.rect.center),
            ),
            start=self.rect.bottomright,
            field=self.field,
        )
        self.back_collision = CollisionVision(
            angle=180,
            offset=self.width // 2,
            start=self.rect.midleft,
            field=self.field,
        )

    def draw(self, surface: Surface):
        surface.blit(self.rotated_surface, self.rect)

        if FLAGS.maze_car.show_bounds:
            pygame.draw.rect(surface, Colors.WHITE, self.rect, width=1)
        if FLAGS.maze_car.show_collision_distance:
            pygame.draw.line(
                surface=surface,
                color=Colors.WHITE,
                start_pos=self.front_collision.start,
                end_pos=self.front_collision.end,
            )
            pygame.draw.line(
                surface=surface,
                color=Colors.WHITE,
                start_pos=self.left_collision.start,
                end_pos=self.left_collision.end,
            )
            pygame.draw.line(
                surface=surface,
                color=Colors.WHITE,
                start_pos=self.right_collision.start,
                end_pos=self.right_collision.end,
            )
            pygame.draw.line(
                surface=surface,
                color=Colors.WHITE,
                start_pos=self.back_collision.start,
                end_pos=self.back_collision.end,
            )

    def _update_vision(self):
        self.front_collision.update(rect=self.rect, angle=self.angle)
        self.left_collision.update(rect=self.rect, angle=self.angle)
        self.right_collision.update(rect=self.rect, angle=self.angle)
        self.back_collision.update(rect=self.rect, angle=self.angle)

    def _turn(self, angle: int):
        self.angle = (self.angle + angle) % 360
        self.rotated_surface = pygame.transform.rotate(
            self.surface,
            self.angle,
        )
        self.rect = self.rotated_surface.get_rect(center=self.rect.center)
        self._update_vision()

    def turn_left(self) -> None:
        self._turn(angle=self.turn_speed)

    def turn_right(self) -> None:
        self._turn(angle=-self.turn_speed)

    def _move(self, x: int, y: int):
        is_clamped, self.rect = get_clamped_rect(
            rect=self.rect,
            constraint=self.field.rect,
            new_x=x,
            new_y=y,
        )
        if is_clamped:
            self.set_speed(speed=0, acceleration_rate=0.0)
        self._update_vision()

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
