"""HUD panels around the field: top bar, side panel, bottom bar.

Retro style: only lines and text, with colors and bold for distinction.
Graphics belong inside the field.

Sections for features that don't exist yet (round, score, checkpoints,
rewards, agent) show a dash. Their roadmap steps fill them in.
"""

import math
from dataclasses import dataclass

from ml_collections import ConfigDict

import pygame
from pygame import Rect, Surface

from src.ecs import World
from src.render import theme, warnings
from src.sim.components import (
    ActionInput,
    Checkpoint,
    Eliminated,
    Motion,
    Ray,
    Renderable,
    Score,
    Sensors,
    Transform,
)
from src.sim.resources import (
    EventLog,
    Rng,
    RoundState,
    SimClock,
    SimConfig,
)
from src.sim.stage import Stage
from src.utils.ui import draw_text

DASH = "—"
PADDING = 14


@dataclass(frozen=True)
class RewardStatus:
    """The agent reward, from the env (it isn't part of the simulation)."""

    profile: str  # reward profile name
    last: float  # reward of the latest step
    total: float  # summed over this game


@dataclass
class CarInfo:
    label: str
    speed: float  # px/s, negative while reversing
    pedal: str
    steering: float  # -1 full right .. +1 full left
    heading: float  # degrees
    center: tuple[float, float]
    action: ActionInput
    rays: list[Ray]
    eliminated: bool
    score: Score


def car_infos(world: World) -> list[CarInfo]:
    config = world.resource(SimConfig)
    return [
        CarInfo(
            label=renderable.label,
            speed=motion.speed * config.steps_per_second,
            pedal=motion.pedal,
            steering=motion.steering,
            heading=transform.angle,
            center=(transform.x, transform.y),
            action=action,
            rays=sensors.rays,
            eliminated=world.try_component(car, Eliminated) is not None,
            score=score,
        )
        for car, (renderable, motion, transform, action, sensors, score) in (
            world.query(
                Renderable, Motion, Transform, ActionInput, Sensors, Score
            )
        )
    ]


DIRECTIONS = (
    "ahead",
    "ahead-left",
    "left",
    "behind-left",
    "behind",
    "behind-right",
    "right",
    "ahead-right",
)


def nearest_checkpoint(
    world: World, car: CarInfo
) -> tuple[float, str] | None:
    """Distance (center to center) and direction, relative to the car's
    heading, of the nearest checkpoint.
    """
    spots = [spot for _, (spot, _) in world.query(Transform, Checkpoint)]
    if not spots:
        return None
    x, y = car.center
    spot = min(spots, key=lambda s: math.dist((s.x, s.y), (x, y)))
    bearing = math.degrees(math.atan2(-(spot.y - y), spot.x - x))
    relative = (bearing - car.heading) % 360
    direction = DIRECTIONS[int((relative + 22.5) // 45) % 8]
    return math.dist((spot.x, spot.y), (x, y)), direction


def format_time(seconds: float) -> str:
    minutes, seconds = divmod(max(seconds, 0.0), 60)
    return f"{int(minutes):02d}:{seconds:04.1f}"


def seconds_left(world: World) -> float:
    state = world.resource(RoundState)
    return state.steps_left / world.resource(SimConfig).steps_per_second


def _box(surface: Surface, rect: Rect) -> None:
    pygame.draw.rect(surface, theme.PANEL_BORDER, rect, 1)


# Top bar


def draw_top_bar(
    surface: Surface,
    rect: Rect,
    world: World,
    car: CarInfo | None,
    hud: ConfigDict,
    reward: RewardStatus | None = None,
) -> None:
    _box(surface, rect)
    x = rect.x + PADDING
    y = rect.y + 8
    state = world.resource(RoundState)
    time_left = seconds_left(world)
    items = (
        ("ROUND", f"{state.number}/{state.total}", warnings.NORMAL),
        ("TIME", format_time(time_left), warnings.time_level(time_left, hud)),
        ("SCORE", f"{car.score.total:,.0f}" if car else DASH, warnings.NORMAL),
    )
    for label, value, level in items:
        label_rect = draw_text(
            surface, label, (x, y + 3), theme.HEADER_SIZE, theme.TEXT_DIM
        )
        value_rect = draw_text(
            surface,
            value,
            (label_rect.right + 8, y),
            theme.BIG_SIZE,
            warnings.value_color(level),
            bold=True,
        )
        x = value_rect.right + 28

    if car is not None:
        if car.eliminated:
            status, color = "CRASHED", theme.BAD
        elif car.speed > 0:
            status, color = "DRIVING", theme.GOOD
        elif car.speed < 0:
            status, color = "REVERSING", theme.GOOD
        else:
            status, color = "STOPPED", theme.WARN
        draw_text(surface, status, (x, y + 2), theme.TEXT_SIZE, color, True)

    y += 26
    x = rect.x + PADDING
    details = [
        ("DRIVER", car.label if car else DASH),
        *round_details(world, reward),
    ]
    for label, value in details:
        label_rect = draw_text(
            surface, label, (x, y + 1), theme.HEADER_SIZE, theme.TEXT_DIM
        )
        value_rect = draw_text(
            surface,
            value,
            (label_rect.right + 8, y),
            theme.TEXT_SIZE,
            theme.TEXT,
        )
        x = value_rect.right + 24


def round_details(
    world: World, reward: RewardStatus | None = None
) -> list[tuple[str, str]]:
    """Which stage, seed, and reward profile this round runs on."""
    stage = world.resource(Stage)
    details = [
        ("STAGE", f"{stage.name} {stage.width:g}×{stage.height:g}"),
        ("CHECKPOINTS", stage.checkpoints.mode),
        ("SEED", str(world.resource(Rng).seed)),
    ]
    if reward:
        details.append(("REWARD", reward.profile))
    return details


# Side panel


class _Column:
    """Draws panel sections top to bottom."""

    def __init__(self, surface: Surface, rect: Rect) -> None:
        self.surface = surface
        self.rect = rect
        self.left = rect.x + PADDING
        self.right = rect.right - PADDING
        self.y = rect.y + PADDING

    def header(self, title: str) -> None:
        draw_text(
            self.surface,
            title,
            (self.left, self.y),
            theme.HEADER_SIZE,
            theme.ACCENT,
            bold=True,
        )
        self.y += theme.LINE_HEIGHT

    def row(
        self, label: str, value: str, level: int = warnings.NORMAL
    ) -> None:
        draw_text(
            self.surface,
            label,
            (self.left, self.y),
            theme.TEXT_SIZE,
            warnings.label_color(level),
        )
        draw_text(
            self.surface,
            value,
            (self.right, self.y),
            theme.TEXT_SIZE,
            warnings.value_color(level),
            anchor="topright",
        )
        self.y += theme.LINE_HEIGHT

    def note(self, text: str) -> None:
        draw_text(
            self.surface,
            text,
            (self.left, self.y),
            theme.TEXT_SIZE,
            theme.TEXT_DIM,
        )
        self.y += theme.LINE_HEIGHT

    def gap(self) -> None:
        self.y += 6


def draw_side_panel(
    surface: Surface,
    rect: Rect,
    world: World,
    cars: list[CarInfo],
    hud: ConfigDict,
    reward: RewardStatus | None = None,
) -> None:
    _box(surface, rect)
    column = _Column(surface, rect)
    car = cars[0] if cars else None
    stop_distance = 0.0
    if car:
        stop_distance = warnings.stopping_distance(
            car.speed,
            hud.reaction_time,
            world.resource(SimConfig).brake_deceleration,
        )

    column.header("CAR")
    if car:
        column.row(
            "Speed",
            f"{car.speed:,.1f} px/s",
            warnings.speed_level(
                _ahead_distance(car), car.speed, stop_distance
            ),
        )
        column.row("Stop dist", f"{stop_distance:,.0f} px")
        column.row("Pedal", car.pedal)
        column.row("Steering", _steering_text(car.steering))
        column.row("Heading", f"{car.heading:.0f}°")
        column.row("Position", f"{car.center[0]:.1f}, {car.center[1]:.1f}")
        _draw_inputs(column, car.action)
    else:
        column.note("No car")
    column.gap()

    column.header("SENSORS (px to border)")
    if car:
        _draw_sensors(
            column, car, world.resource(SimConfig).brake_deceleration, hud
        )
    column.gap()

    column.header("OBJECTIVE")
    checkpoint = nearest_checkpoint(world, car) if car else None
    if checkpoint:
        distance, direction = checkpoint
        column.row(
            "Checkpoint",
            f"{distance:,.0f} px {direction}",
            warnings.checkpoint_level(distance, hud),
        )
    else:
        column.row("Checkpoint", DASH)
    column.row("Collected", str(car.score.checkpoints) if car else DASH)
    column.gap()

    column.header("SCORE (game points)")
    if car:
        column.row("Distance", f"+{car.score.distance_points:,.0f}")
        column.row("Checkpoints", f"+{car.score.checkpoint_points:,.0f}")
        column.row("Last step", f"+{car.score.last_step:g}")
    column.gap()

    column.header(
        f"AGENT REWARD ({reward.profile})" if reward else "AGENT REWARD"
    )
    if reward:
        column.row("Last step", f"{reward.last:+,.2f}")
        column.row("This game", f"{reward.total:+,.2f}")
    else:
        column.note("No reward profile")
    column.gap()

    column.header("LEADERBOARD")
    ranked = sorted(cars, key=lambda info: -info.score.total)
    for rank, info in enumerate(ranked, start=1):
        column.row(f"{rank}  {info.label}", f"{info.score.total:,.0f}")


# Mirrored columns: the car's left side on the left, right side on the right.
SENSOR_ROWS = (
    ("front", "back"),
    ("front_left", "front_right"),
    ("left", "right"),
    ("back_left", "back_right"),
)
SENSOR_LABELS = {
    "front": "Front",
    "front_left": "F-left",
    "left": "Left",
    "back_left": "B-left",
    "back": "Back",
    "back_right": "B-right",
    "right": "Right",
    "front_right": "F-right",
}


def _ahead_distance(car: CarInfo) -> float | None:
    """Distance straight along the direction of travel."""
    name = "front" if car.speed > 0 else "back" if car.speed < 0 else None
    return next((ray.distance for ray in car.rays if ray.name == name), None)


def _draw_sensors(
    column: _Column, car: CarInfo, brake_deceleration: float, hud: ConfigDict
) -> None:
    rays = {ray.name: ray for ray in car.rays}
    levels = warnings.ray_levels(car.rays, car.speed, brake_deceleration, hud)
    middle = (column.left + column.right) // 2
    for left_name, right_name in SENSOR_ROWS:
        for name, x, right_edge in (
            (left_name, column.left, middle - 12),
            (right_name, middle + 12, column.right),
        ):
            if name not in rays:
                continue
            ray = rays[name]
            level = levels[name]
            draw_text(
                column.surface,
                SENSOR_LABELS.get(name, name),
                (x, column.y),
                theme.TEXT_SIZE,
                warnings.label_color(level),
            )
            draw_text(
                column.surface,
                f"{ray.distance:.1f}",
                (right_edge, column.y),
                theme.TEXT_SIZE,
                warnings.value_color(level),
                anchor="topright",
            )
        column.y += theme.LINE_HEIGHT


def _steering_text(steering: float) -> str:
    if steering == 0:
        return "Center"
    side = "Left" if steering > 0 else "Right"
    return f"{side} {abs(steering) * 100:.0f} %"


def _draw_inputs(column: _Column, action: ActionInput) -> None:
    """Keys as text: pressed keys are bright and bold, others dim."""
    draw_text(
        column.surface,
        "Inputs",
        (column.left, column.y),
        theme.TEXT_SIZE,
        theme.TEXT_DIM,
    )
    keys = (
        ("W", action.gas),
        ("A", action.turn_left),
        ("S", action.reverse),
        ("D", action.turn_right),
        ("SPACE", action.brake),
    )
    x = column.right
    for letter, pressed in reversed(keys):
        rect = draw_text(
            column.surface,
            letter,
            (x, column.y),
            theme.TEXT_SIZE,
            theme.ACCENT if pressed else theme.TEXT_DIM,
            bold=pressed,
            anchor="topright",
        )
        x = rect.left - 10
    column.y += theme.LINE_HEIGHT


# Bottom bar


def draw_bottom_bar(
    surface: Surface,
    rect: Rect,
    world: World,
    fps: float,
    frame_rate: int,
    vsync: bool,
    hud: ConfigDict,
) -> None:
    _box(surface, rect)
    y = rect.centery
    _draw_events(surface, rect, world)
    step = world.resource(SimClock).step
    sim_rate = world.resource(SimConfig).steps_per_second
    sync = " vsync" if vsync else ""
    fps_level = warnings.fps_level(fps, frame_rate, hud)
    # Drawn right to left, so only the FPS part can change color.
    parts = (
        ("R: restart  H: lines", theme.TEXT_DIM),
        (f"FPS {fps:.0f}/{frame_rate}{sync}", warnings.label_color(fps_level)),
        (f"SIM {sim_rate}/s", theme.TEXT_DIM),
        (f"Step {step:,}", theme.TEXT_DIM),
    )
    x = rect.right - PADDING
    for text, color in parts:
        drawn = draw_text(
            surface, text, (x, y), theme.TEXT_SIZE, color, anchor="midright"
        )
        x = drawn.left - 20


def _draw_events(surface: Surface, rect: Rect, world: World) -> None:
    """The latest event, with its time into the round."""
    events = world.resource(EventLog).events
    if not events:
        text, color = "No events yet", theme.TEXT_DIM
    else:
        event = events[-1]
        sps = world.resource(SimConfig).steps_per_second
        text = f"{format_time(event.step / sps)}  {event.text}"
        if event.danger:
            color = theme.BAD
        elif event.kind == "checkpoint":
            color = theme.GOOD
        else:
            color = theme.TEXT
    draw_text(
        surface,
        text,
        (rect.x + PADDING, rect.centery),
        theme.TEXT_SIZE,
        color,
        anchor="midleft",
    )
