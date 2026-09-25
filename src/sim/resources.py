"""Per-world shared data. Replaces the pre-ECS singletons and FLAGS reads."""

import random
from dataclasses import dataclass, field

from ml_collections import ConfigDict
from pygame import Rect

from src.sim.spawning import SpawnSchedule
from src.sim.stage import Stage


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
    def from_stage(stage: "Stage") -> "Field":
        """Stage coordinates: the field spans (0, 0) to the stage size."""
        return Field(x=0.0, y=0.0, width=stage.width, height=stage.height)


@dataclass
class RoundState:
    """The current round: a countdown in steps, and whether it's over."""

    steps_left: int
    steps_total: int
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


@dataclass(frozen=True)
class Rng:
    """The world's seed. Every random thing uses its own named stream from
    it, so adding a new one never changes another's sequence.
    """

    seed: int

    def stream(self, name: str) -> random.Random:
        return random.Random(f"{self.seed}:{name}")


@dataclass
class SpawnSchedules:
    """Spawn schedules by spawner name (checkpoints now, fuel later)."""

    schedules: dict[str, SpawnSchedule] = field(default_factory=dict)

    def get(self, name: str) -> SpawnSchedule:
        return self.schedules[name]


@dataclass
class SimClock:
    """Steps simulated so far. Time is counted in steps, never real time."""

    step: int = 0
