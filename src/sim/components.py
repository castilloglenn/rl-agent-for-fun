"""Data-only components for Maze Car entities."""

from dataclasses import dataclass, field

from pygame import Vector2

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
    """The car's center position (world coordinates) and heading."""

    x: float = 0.0
    y: float = 0.0
    angle: float = 0.0


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
    steering: float = 0.0  # wheel position: -1 full right .. +1 full left


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
    steer_rate: float  # wheel travel per step, moving outward
    steer_return_rate: float  # wheel travel per step, toward center


@dataclass
class Hitbox:
    """The car's size. Its 4 real corners come from `car_corners`
    (src/sim/geometry.py) with the Transform.
    """

    width: int
    height: int


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
class Eliminated:
    """Marks a car that is out of the round (crash, later hazards or
    weapons). Car systems skip it. Added by `eliminate`.
    """

    reason: str  # e.g. "wall"
    step: int


@dataclass
class Renderable:
    color: ColorValue
    label: str = "Car"  # shown in the HUD, e.g. "You (keyboard)"
