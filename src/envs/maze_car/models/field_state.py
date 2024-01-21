from dataclasses import dataclass, field

from pygame import Rect

from utils.types import Colors


@dataclass
class GameFieldState:
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    color: Colors = Colors.WHITE
    rect: Rect = field(init=False)

    def __post_init__(self):
        self.rect = Rect(self.x, self.y, self.width, self.height)
