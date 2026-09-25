"""HUD panels around the field: top bar, side panel, bottom bar.

Retro style: only lines and text, with colors and bold for distinction.
Graphics belong inside the field.

Sections for features that don't exist yet (round, score, checkpoints,
rewards, agent) show a dash. Their roadmap steps fill them in.
"""

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
from src.sim.resources import SimClock, SimConfig
from src.utils.ui import draw_text

DASH = "—"
PADDING = 14


@dataclass
class CarInfo:
    label: str
    speed: float  # px/s, negative while reversing
    pedal: str
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
            speed=motion.speed * config.steps_per_second,
            pedal=motion.pedal,
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
            status, color = "STOPPED", theme.TEXT_DIM
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
        column.row("Pedal", car.pedal)
        column.row("Heading", f"{car.heading:.0f}°")
        column.row("Position", f"{car.center[0]}, {car.center[1]}")
        column.row("Hitbox", f"{car.hitbox_size[0]} × {car.hitbox_size[1]}")
        _draw_inputs(column, car.action)
    else:
        column.note("No car")
    column.gap()

    column.header("SENSORS")
    if car:
        for ray in car.rays:
            column.row(ray.name.title(), f"{ray.distance:,.1f} px")
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
    status = (
        f"Step {step:,}   SIM {sim_rate}/s   "
        f"FPS {fps:.0f}/{frame_rate}{sync}   H: toggle lines"
    )
    draw_text(
        surface,
        status,
        (rect.right - PADDING, y),
        theme.TEXT_SIZE,
        theme.TEXT_DIM,
        anchor="midright",
    )
