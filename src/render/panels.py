"""HUD panels around the field: top bar, side panel, bottom bar.

Sections for features that don't exist yet (round, score, checkpoints,
rewards, agent) show a dash. Their roadmap steps fill them in.
"""

import math
from dataclasses import dataclass

import pygame
from pygame import Rect, Surface

from src.ecs import World
from src.render import theme
from src.sim.components import (
    ActionInput,
    Hitbox,
    Motion,
    Ray,
    Renderable,
    Sensors,
    Transform,
)
from src.sim.resources import Field, SimClock, SimConfig
from src.utils.ui import draw_text

DASH = "—"
PADDING = 14


@dataclass
class CarInfo:
    label: str
    speed: float  # px/s
    throttle: float  # 0..1
    heading: float  # degrees
    center: tuple[int, int]
    hitbox_size: tuple[int, int]
    action: ActionInput
    rays: list[Ray]


def car_infos(world: World) -> list[CarInfo]:
    config = world.resource(SimConfig)
    return [
        CarInfo(
            label=renderable.label,
            speed=motion.speed * config.fps,
            throttle=motion.acceleration_rate / config.acceleration_max,
            heading=transform.angle,
            center=hitbox.rect.center,
            hitbox_size=hitbox.rect.size,
            action=action,
            rays=sensors.rays,
        )
        for _, (renderable, motion, transform, hitbox, action, sensors) in (
            world.query(
                Renderable, Motion, Transform, Hitbox, ActionInput, Sensors
            )
        )
    ]


def _box(surface: Surface, rect: Rect) -> None:
    pygame.draw.rect(surface, theme.PANEL, rect, border_radius=6)
    pygame.draw.rect(surface, theme.PANEL_BORDER, rect, 1, border_radius=6)


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
        moving = car.speed > 0
        status, color = ("DRIVING", theme.GOOD) if moving else (
            "STOPPED",
            theme.TEXT_DIM,
        )
        pygame.draw.circle(surface, color, (x + 5, y + 11), 5)
        draw_text(
            surface, status, (x + 16, y + 2), theme.TEXT_SIZE, color, True
        )

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

    def row(self, label: str, value: str) -> None:
        draw_text(
            self.surface,
            label,
            (self.left, self.y),
            theme.TEXT_SIZE,
            theme.TEXT_DIM,
        )
        draw_text(
            self.surface,
            value,
            (self.right, self.y),
            theme.TEXT_SIZE,
            theme.TEXT,
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
    surface: Surface, rect: Rect, world: World, cars: list[CarInfo]
) -> None:
    _box(surface, rect)
    column = _Column(surface, rect)
    car = cars[0] if cars else None

    column.header("CAR")
    if car:
        column.row("Speed", f"{car.speed:,.1f} px/s")
        column.row("Throttle", f"{car.throttle * 100:.0f} %")
        column.row("Heading", f"{car.heading:.0f}°")
        column.row("Position", f"{car.center[0]}, {car.center[1]}")
        column.row("Hitbox", f"{car.hitbox_size[0]} × {car.hitbox_size[1]}")
        _draw_inputs(column, car.action)
    else:
        column.note("No car")
    column.gap()

    column.header("SENSORS")
    if car:
        _draw_sensors(column, car.rays, world.resource(Field))
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


def _draw_inputs(column: _Column, action: ActionInput) -> None:
    draw_text(
        column.surface,
        "Inputs",
        (column.left, column.y + 4),
        theme.TEXT_SIZE,
        theme.TEXT_DIM,
    )
    keys = (
        ("W", action.move_forward),
        ("A", action.turn_left),
        ("S", action.move_backward),
        ("D", action.turn_right),
    )
    size = 24
    x = column.right - len(keys) * (size + 4) + 4
    for letter, pressed in keys:
        key = Rect(x, column.y, size, size)
        if pressed:
            pygame.draw.rect(column.surface, theme.ACCENT, key, border_radius=4)
        pygame.draw.rect(
            column.surface,
            theme.ACCENT if pressed else theme.PANEL_BORDER,
            key,
            1,
            border_radius=4,
        )
        draw_text(
            column.surface,
            letter,
            key.center,
            theme.TEXT_SIZE,
            theme.TEXT if pressed else theme.TEXT_DIM,
            bold=True,
            anchor="center",
        )
        x += size + 4
    column.y += size + 6


def _draw_sensors(column: _Column, rays: list[Ray], field: Field) -> None:
    """Radar with the car pointing up, plus each ray's distance."""
    radius = 46
    center = (column.left + radius, column.y + radius + 2)
    # Scaled to the field's shorter side, so typical distances stay
    # readable. Longer rays are capped at the radar edge.
    max_range = min(field.width, field.height)

    pygame.draw.circle(column.surface, theme.PANEL_BORDER, center, radius, 1)
    for ray in rays:
        # Relative angle, counterclockwise from the heading (screen up).
        angle = math.radians(ray.angle)
        length = radius * min(ray.distance / max_range, 1.0)
        end = (
            center[0] - math.sin(angle) * length,
            center[1] - math.cos(angle) * length,
        )
        pygame.draw.line(column.surface, theme.RAY, center, end)
        pygame.draw.circle(column.surface, theme.ACCENT, end, 3)
    pygame.draw.rect(
        column.surface,
        theme.ACCENT,
        Rect(center[0] - 4, center[1] - 6, 8, 12),
        border_radius=2,
    )

    values = _Column(column.surface, column.rect)
    values.left = center[0] + radius + 18
    values.y = column.y
    for ray in rays:
        values.row(ray.name.title(), f"{ray.distance:,.1f} px")
    column.y += max(2 * radius + 6, values.y - column.y)


# Bottom bar


def draw_bottom_bar(
    surface: Surface, rect: Rect, world: World, fps: float, target_fps: int
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
    status = f"Step {step:,}    FPS {fps:.0f}/{target_fps}    H: hide panels"
    draw_text(
        surface,
        status,
        (rect.right - PADDING, y),
        theme.TEXT_SIZE,
        theme.TEXT_DIM,
        anchor="midright",
    )
