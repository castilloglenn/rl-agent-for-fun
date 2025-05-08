from dataclasses import dataclass, field

from pygame import Rect

from src.utils.types import Colors


@dataclass
class FieldState:
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    color: Colors = Colors.WHITE

    rect: Rect = field(init=False)
    half_width: int = field(init=False)
    quarter_width: int = field(init=False)
    half_height: int = field(init=False)
    quarter_height: int = field(init=False)

    def __post_init__(self):
        self.rect = Rect(self.x, self.y, self.width, self.height)
        self.half_width = self.x + self.width // 2
        self.quarter_width = self.x + self.width // 4
        self.half_height = self.y + self.height // 2
        self.quarter_height = self.y + self.height // 4
