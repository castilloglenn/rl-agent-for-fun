from absl import flags
from pygame import Rect, Vector2

from envs.maze_car.models.collision_distance_state import CollisionDistanceState
from envs.maze_car.state import StateSingleton
from src.utils.common import get_extended_point
from src.utils.types import Coordinate
from src.utils.ui import get_window_constants

FLAGS = flags.FLAGS


class CollisionDistance:
    def __init__(
        self,
        key: str,
        angle: int,
        offset: int,
        start: Coordinate,
    ) -> None:
        self.key = key
        self._globals = StateSingleton.get_instance()
        self._globals.collision_distances[key] = CollisionDistanceState(
            angle=angle,
            offset=offset,
            start=Vector2(start),
        )

    @property
    def state(self) -> CollisionDistanceState:
        return self._globals.collision_distances[self.key]

    def update(self, rect: Rect, angle: int) -> None:
        window = get_window_constants(config=FLAGS.maze_car)
        angle = (angle + self.state.angle) % 360

        self.state.start = get_extended_point(
            start_point=Vector2(rect.center),
            angle=angle,
            distance=self.state.offset,
        )
        max_front = get_extended_point(
            start_point=self.state.start,
            angle=angle,
            distance=window.longest_side * 2,
        )
        collide_points = self._globals.field.rect.clipline(
            self.state.start,
            max_front,
        )
        self.state.end = Vector2(
            collide_points[1] if collide_points else self.state.start,
        )
        self.state.distance = self.state.start.distance_to(self.state.end)
