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
    moved: float = 0.0  # px actually moved along the heading this step


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
class Score:
    """A car's points in the current game (kept across rounds)."""

    total: float = 0.0
    distance_points: float = 0.0
    checkpoint_points: float = 0.0
    checkpoints: int = 0
    last_step: float = 0.0  # points earned in the latest step
    distance_carry: float = 0.0  # px driven toward the next distance point
    # Steps each checkpoint reached in the latest step had been on the
    # field (for time-based reward terms). Reset every step.
    checkpoint_ages: list[int] = field(default_factory=list)


@dataclass
class Trigger:
    """A circular zone that fires when a car's hitbox touches it.
    Its effects are the other components on the same entity.
    """

    radius: float


@dataclass
class ScoreReward:
    """Trigger effect: the car that touches it gains points."""

    points: float
    label: str  # e.g. "checkpoint", for the event log


@dataclass
class SpawnedAt:
    """How many steps were completed when a trigger (re)appeared, so its
    age can be measured: reached during the Nth step after appearing
    before step 0 means N steps on the field.
    """

    step: int = 0


@dataclass
class Respawn:
    """Trigger effect: after firing, move to the next spot of a spawn
    schedule (by spawner name).
    """

    spawner: str = "checkpoints"


@dataclass
class Checkpoint:
    """Tag for checkpoint entities (HUD, observation)."""


@dataclass
class Health:
    """A car's health. Wall hits cost health by impact speed (the rules'
    collisions); at 0 the car is wrecked.
    """

    current: float
    maximum: float
    last_hit_step: int | None = None  # last step a hit cost health
    last_hit_damage: float = 0.0
    contact_step: int | None = None  # last step it touched a wall
    contacts: int = 0  # separate wall contacts so far (bumps and hits)
    scraped: float = 0.0  # px slid along a wall in the current scrape
    scrape_damage: float = 0.0  # health lost in the current scrape

    @property
    def share(self) -> float:
        """0 (wrecked) .. 1 (full)."""
        return self.current / self.maximum


@dataclass
class Eliminated:
    """Marks a car that is out of the round (wrecked, later hazards or
    weapons). Car systems skip it. Added by `eliminate`.
    """

    reason: str  # e.g. "wrecked"
    step: int


@dataclass
class Renderable:
    color: ColorValue
    label: str = "Car"  # shown in the HUD, e.g. "You (keyboard)"
