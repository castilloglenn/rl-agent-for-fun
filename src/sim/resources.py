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
    steer_in_time: float  # seconds, center to full lock
    steer_return_time: float  # seconds, full lock to center

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
            steer_in_time=car.steer_in_time,
            steer_return_time=car.steer_return_time,
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

    @staticmethod
    def from_config(config: ConfigDict) -> "Field":
        return Field(
            x=config.field.x,
            y=config.field.y,
            width=config.field.width,
            height=config.field.height,
        )


@dataclass
class RoundState:
    """The current round: a countdown in steps, and whether it's over."""

    steps_left: int
    number: int = 1
    total: int = 1  # rounds per game
    over: bool = False
    reason: str | None = None  # "time" or "all_out" once over

    @property
    def game_over(self) -> bool:
        return self.over and self.number >= self.total


@dataclass
class Event:
    step: int
    text: str
    kind: str = "info"  # "elimination", "round", or "info"
    danger: bool = False


@dataclass
class EventLog:
    """Things that happened, for the HUD and replays."""

    events: list[Event] = field(default_factory=list)

    def add(
        self, step: int, text: str, kind: str = "info", danger: bool = False
    ) -> None:
        self.events.append(Event(step, text, kind, danger))

    def of_kind(self, kind: str) -> list[Event]:
        return [event for event in self.events if event.kind == kind]


@dataclass
class SimClock:
    """Steps simulated so far. Time is counted in steps, never real time."""

    step: int = 0
