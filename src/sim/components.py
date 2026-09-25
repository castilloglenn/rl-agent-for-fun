"""Data-only components for Maze Car entities."""

from dataclasses import dataclass, field

from pygame import Rect, Vector2

from src.utils.types import ColorValue


@dataclass
class ActionInput:
    """Written by a controller (keyboard, agent, replayer) before a step."""

    turn_left: bool = False
    turn_right: bool = False
    move_forward: bool = False
    move_backward: bool = False

    @property
    def is_moving(self) -> bool:
        return self.move_forward or self.move_backward


@dataclass
class Transform:
    angle: float = 0
    # Sub-pixel carry: the position itself is the integer Hitbox.rect.
    x_float: float = 0.0
    y_float: float = 0.0


@dataclass
class Motion:
    speed: float = 0.0
    acceleration_rate: float = 0.0


@dataclass(frozen=True)
class CarSpec:
    """Per-frame values derived from base_speed and the FPS."""

    base_speed: float
    forward_speed: float
    backward_speed: float
    turn_speed: float
    acceleration_unit: float


@dataclass
class Hitbox:
    """Unrotated size, plus the axis-aligned bounds of the rotated car.

    `rect` is also the car's position.
    """

    width: int
    height: int
    rect: Rect


@dataclass
class Ray:
    name: str
    angle: float  # relative to the car's heading
    offset: float  # distance from the car's center to the ray start
    start: Vector2 = field(default_factory=Vector2)
    end: Vector2 = field(default_factory=Vector2)
    distance: float = 0.0


@dataclass
class Sensors:
    rays: list[Ray]


@dataclass
class Renderable:
    color: ColorValue
    label: str = "Car"  # shown in the HUD, e.g. "You (keyboard)"
