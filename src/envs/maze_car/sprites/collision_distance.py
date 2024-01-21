from absl import flags
from pygame import Rect, Vector2

from envs.maze_car.sprites.field import Field
from src.utils.common import get_extended_point
from src.utils.types import Coordinate
from src.utils.ui import get_window_constants

FLAGS = flags.FLAGS


class CollisionDistance:
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
            distance=max(window.width, window.height) * 2,
        )
        collide_points = self.field.rect.clipline(self.start, max_front)
        self.end = Vector2(
            collide_points[1] if collide_points else self.start,
        )
        self.distance = self.start.distance_to(self.end)
