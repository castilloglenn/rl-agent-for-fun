# Environment
from dataclasses import dataclass

Reward = int | float
GameOver = bool
Score = int | float


@dataclass
class WindowConstants:
    title: str
    width: int
    half_width: int
    quarter_width: int
    height: int
    half_height: int
    quarter_height: int
