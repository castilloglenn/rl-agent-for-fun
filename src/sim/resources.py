"""Per-world shared data. Replaces the pre-ECS singletons and FLAGS reads."""

from dataclasses import dataclass, field

from ml_collections import ConfigDict
from pygame import Rect


@dataclass(frozen=True)
class SimConfig:
    steps_per_second: int
    car_width: int
    car_height: int
    ray_length: int
    # Car driving limits, in px/s, px/s², and degrees/s.
    max_speed: float
    max_reverse_speed: float
    acceleration: float
    reverse_acceleration: float
    brake_deceleration: float
    drag: float
    max_turn_rate: float
    full_turn_speed: float

    @staticmethod
    def from_config(config: ConfigDict) -> "SimConfig":
        car = config.car
        return SimConfig(
            steps_per_second=config.sim.steps_per_second,
            car_width=car.width,
            car_height=car.height,
            ray_length=config.sensors.ray_length,
            max_speed=car.max_speed,
            max_reverse_speed=car.max_reverse_speed,
            acceleration=car.acceleration,
            reverse_acceleration=car.reverse_acceleration,
            brake_deceleration=car.brake_deceleration,
            drag=car.drag,
            max_turn_rate=car.max_turn_rate,
            full_turn_speed=car.full_turn_speed,
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
