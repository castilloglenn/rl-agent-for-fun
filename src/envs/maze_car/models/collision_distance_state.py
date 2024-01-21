from dataclasses import dataclass, field

from pygame import Vector2


@dataclass
class CollisionDistanceState:
    angle: int = 0
    offset: int = 0
    distance: int = 0
    start: Vector2 = field(default_factory=Vector2)
    end: Vector2 = field(default_factory=Vector2)

    def __post_init__(self):
        self.end = self.start
