"""Per-world shared data. Replaces the pre-ECS singletons and FLAGS reads."""

from dataclasses import dataclass, field

from ml_collections import ConfigDict
from pygame import Rect


@dataclass(frozen=True)
class SimConfig:
    fps: int
    acceleration_unit: float  # raw config value, not per frame
    acceleration_max: float
    car_width: int
    car_height: int
    ray_length: int

    @staticmethod
    def from_config(config: ConfigDict) -> "SimConfig":
        return SimConfig(
            fps=config.display.fps,
            acceleration_unit=config.car.acceleration_unit,
            acceleration_max=config.car.acceleration_max,
            car_width=config.car.width,
            car_height=config.car.height,
            ray_length=config.sensors.ray_length,
        )


@dataclass
class Field:
    """The drivable area. Its border stops cars and rays."""

    x: float
    y: float
    width: float
    height: float

    rect: Rect = field(init=False)

    def __post_init__(self):
        self.rect = Rect(self.x, self.y, self.width, self.height)

    @property
    def quarter_width(self) -> float:
        return self.x + self.width // 4

    @property
    def half_height(self) -> float:
        return self.y + self.height // 2

    @staticmethod
    def from_config(config: ConfigDict) -> "Field":
        return Field(
            x=config.field.x,
            y=config.field.y,
            width=config.field.width,
            height=config.field.height,
        )


@dataclass
class SimClock:
    """Steps simulated so far. Time is counted in steps, never real time."""

    step: int = 0
