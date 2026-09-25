"""HUD panels around the field: top bar, side panel, bottom bar.

Retro style: only lines and text, with colors and bold for distinction.
Graphics belong inside the field.

Sections for features that don't exist yet (round, score, checkpoints,
rewards, agent) show a dash. Their roadmap steps fill them in.
"""

from dataclasses import dataclass

from ml_collections import ConfigDict

import pygame
from pygame import Rect, Surface

from src.ecs import World
from src.render import theme, warnings
from src.sim.components import (
    ActionInput,
    Motion,
    Ray,
    Renderable,
    Sensors,
    Transform,
)
from src.sim.resources import SimClock, SimConfig
from src.utils.ui import draw_text

DASH = "—"
PADDING = 14


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
        )
        for _, (renderable, motion, transform, action, sensors) in (
            world.query(Renderable, Motion, Transform, ActionInput, Sensors)
        )
    ]


def _box(surface: Surface, rect: Rect) -> None:
    pygame.draw.rect(surface, theme.PANEL_BORDER, rect, 1)


# Top bar


def draw_top_bar(surface: Surface, rect: Rect, car: CarInfo | None) -> None:
    _box(surface, rect)
    x = rect.x + PADDING
    y = rect.y + 8
    for label, value in (("ROUND", DASH), ("TIME", DASH), ("SCORE", DASH)):
        label_rect = draw_text(
            surface, label, (x, y + 3), theme.HEADER_SIZE, theme.TEXT_DIM
        )
        value_rect = draw_text(
            surface,
            value,
            (label_rect.right + 8, y),
            theme.BIG_SIZE,
            theme.TEXT,
            bold=True,
        )
        x = value_rect.right + 28

    if car is not None:
        if car.speed > 0:
            status, color = "DRIVING", theme.GOOD
        elif car.speed < 0:
            status, color = "REVERSING", theme.GOOD
        else:
            status, color = "STOPPED", theme.WARN
        draw_text(surface, status, (x, y + 2), theme.TEXT_SIZE, color, True)

    driver = car.label if car else DASH
    y += 26
    label_rect = draw_text(
        surface,
        "DRIVER",
        (rect.x + PADDING, y + 1),
        theme.HEADER_SIZE,
        theme.TEXT_DIM,
    )
    draw_text(
        surface, driver, (label_rect.right + 8, y), theme.TEXT_SIZE, theme.TEXT
    )


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
        self.y += 10


def draw_side_panel(
    surface: Surface,
    rect: Rect,
    world: World,
    cars: list[CarInfo],
    hud: ConfigDict,
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
        _draw_sensors(column, car, stop_distance, hud)
    column.gap()

    column.header("OBJECTIVE")
    column.row("Checkpoint", DASH)
    column.row("Collected", DASH)
    column.gap()

    column.header("REWARD")
    column.row("Distance", DASH)
    column.row("Checkpoints", DASH)
    column.gap()

    column.header("AGENT VIEW")
    column.note("Not driven by an agent")
    column.gap()

    column.header("LEADERBOARD")
    for rank, info in enumerate(cars, start=1):
        column.row(f"{rank}  {info.label}", DASH)


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
    column: _Column, car: CarInfo, stop_distance: float, hud: ConfigDict
) -> None:
    rays = {ray.name: ray for ray in car.rays}
    middle = (column.left + column.right) // 2
    for left_name, right_name in SENSOR_ROWS:
        for name, x, right_edge in (
            (left_name, column.left, middle - 12),
            (right_name, middle + 12, column.right),
        ):
            if name not in rays:
                continue
            ray = rays[name]
            level = warnings.ray_level(
                ray.angle, ray.distance, car.speed, stop_distance, hud
            )
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
    draw_text(
        surface,
        "No events yet",
        (rect.x + PADDING, y),
        theme.TEXT_SIZE,
        theme.TEXT_DIM,
        anchor="midleft",
    )
    step = world.resource(SimClock).step
    sim_rate = world.resource(SimConfig).steps_per_second
    sync = " vsync" if vsync else ""
    fps_level = warnings.fps_level(fps, frame_rate, hud)
    # Drawn right to left, so only the FPS part can change color.
    parts = (
        ("H: toggle lines", theme.TEXT_DIM),
        (f"FPS {fps:.0f}/{frame_rate}{sync}", warnings.label_color(fps_level)),
        (f"SIM {sim_rate}/s", theme.TEXT_DIM),
        (f"Step {step:,}", theme.TEXT_DIM),
    )
    x = rect.right - PADDING
    for text, color in parts:
        drawn = draw_text(
            surface, text, (x, y), theme.TEXT_SIZE, color, anchor="midright"
        )
        x = drawn.left - 24
