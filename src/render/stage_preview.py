"""A stage drawn small (roadmap step 7c3): the Maps tab's cards and
detail, and the game window's MAPS box (moved here from src/control/ so
the game window can use it). The stage in its own shape, centered in the rect: the border,
walls, the spawn as the car (with its heading), and fuel, in
order (numbered, if there's room) or random (their border margin,
dashed).
"""

import pygame
from pygame import Rect

from src.render import theme
from src.sim.geometry import car_corners, direction
from src.utils.ui import draw_text

CAR = (24, 16)
MARGIN_COLOR = (44, 46, 54)
DASH = 4


def draw_stage_preview(surface, rect: Rect, data: dict) -> Rect:
    """Draws the stage fitted into `rect`; returns where it went."""
    width, height = data.get("size", (1, 1))
    scale = min(rect.w / width, rect.h / height)
    box = Rect(0, 0, round(width * scale), round(height * scale))
    box.center = rect.center

    def at(x: float, y: float) -> tuple[float, float]:
        return box.x + x * scale, box.y + y * scale

    pygame.draw.rect(surface, theme.BACKGROUND, box)
    fuel = data.get("fuel", {})
    scripted = fuel.get("mode") == "scripted"
    if not scripted:
        margin = fuel.get("border_margin", 40) * scale
        _dashed(surface, box.inflate(-2 * margin, -2 * margin))
    for x, y, w, h in data.get("walls", []):
        left, top = at(x, y)
        wall = Rect(
            round(left),
            round(top),
            max(round(w * scale), 1),
            max(round(h * scale), 1),
        )
        pygame.draw.rect(surface, theme.TEXT_DIM, wall)
    points = fuel.get("points", []) if scripted else []
    spots = [at(x, y) for x, y in points]
    if len(spots) > 1:
        pygame.draw.lines(surface, theme.GUIDE, True, spots)
    radius = max(fuel.get("radius", 15) * scale, 3)
    for i, spot in enumerate(spots):
        pygame.draw.circle(surface, theme.FUEL, spot, radius, 1)
        if radius >= 7:
            draw_text(
                surface,
                str(i + 1),
                spot,
                11,
                theme.TEXT,
                bold=True,
                anchor="center",
            )
    for spawn in data.get("spawns", [])[:1]:
        center = at(spawn["x"], spawn["y"])
        car = [max(CAR[0] * scale, 6), max(CAR[1] * scale, 4)]
        corners = car_corners(*center, spawn.get("angle", 0), *car)
        pygame.draw.polygon(surface, theme.TRAIL_RECENT, corners)
        dx, dy = direction(spawn.get("angle", 0))
        tip = (center[0] + dx * car[0], center[1] + dy * car[0])
        pygame.draw.line(surface, theme.TRAIL_RECENT, center, tip, 1)
    pygame.draw.rect(surface, theme.FIELD_BORDER, box, 1)
    return box


def _dashed(surface, rect: Rect) -> None:
    """A dashed outline: random fuels stay inside it."""
    if rect.w <= 0 or rect.h <= 0:
        return
    edges = (
        (rect.topleft, rect.topright),
        (rect.bottomleft, rect.bottomright),
        (rect.topleft, rect.bottomleft),
        (rect.topright, rect.bottomright),
    )
    for (x0, y0), (x1, y1) in edges:
        length = max(abs(x1 - x0), abs(y1 - y0))
        for start in range(0, length, 2 * DASH):
            end = min(start + DASH, length)
            t0, t1 = start / length, end / length
            pygame.draw.line(
                surface,
                MARGIN_COLOR,
                (x0 + (x1 - x0) * t0, y0 + (y1 - y0) * t0),
                (x0 + (x1 - x0) * t1, y0 + (y1 - y0) * t1),
            )
