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

    @property
    def longest_side(self):
        return max(self.width, self.height)


ColorValue = tuple[int, int, int]


class Colors:
    WHITE: ColorValue = (255, 255, 255)
    BLACK: ColorValue = (0, 0, 0)
    RED: ColorValue = (255, 0, 0)
    GREEN: ColorValue = (0, 255, 0)
    BLUE: ColorValue = (0, 0, 255)
    SKY_BLUE: ColorValue = (0, 134, 212)


Coordinate = tuple[int, int]
