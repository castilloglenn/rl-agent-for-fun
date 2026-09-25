"""Data-only components for Maze Car entities."""

from dataclasses import dataclass, field

from pygame import Rect, Vector2

from src.utils.types import ColorValue


@dataclass
class ActionInput:
    """Written by a controller (keyboard, agent, replayer) before a step."""

    turn_left: bool = False
    turn_right: bool = False
    gas: bool = False
    reverse: bool = False
    brake: bool = False


@dataclass
class Transform:
    angle: float = 0
    # Sub-pixel carry: the position itself is the integer Hitbox.rect.
    x_float: float = 0.0
    y_float: float = 0.0


class Pedal:
    IDLE = "Idle"
    GAS = "Gas"
    COASTING = "Coasting"
    BRAKING = "Braking"
    REVERSE = "Reverse"


@dataclass
class Motion:
    speed: float = 0.0  # px per step along the heading; negative = reversing
    pedal: str = Pedal.IDLE  # what the car did this step, for HUD and logs


@dataclass(frozen=True)
class CarSpec:
    """Driving limits, converted to per-step units (px/step, px/step²,
    degrees/step) from the px/s config values.
    """

    max_speed: float
    max_reverse_speed: float
    acceleration: float
    reverse_acceleration: float
    brake_deceleration: float
    drag: float
    max_turn_rate: float
    full_turn_speed: float


@dataclass
class Hitbox:
    """Unrotated size, plus the axis-aligned bounds of the rotated car.

    `rect` is also the car's position.
    """

    width: int
    height: int
    rect: Rect


@dataclass
class PreviousPose:
    """Pose at the start of the current step, so the renderer can draw
    the car between steps (interpolation). Never used by the physics.
    """

    center_x: float
    center_y: float
    angle: float


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
