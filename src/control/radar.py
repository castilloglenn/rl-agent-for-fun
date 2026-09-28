"""A skill radar (roadmap step 6c): one axis per skill, 0 at the center
and 1 at the rim, the agent as a filled shape and a reference (the
heuristic) as an outline. Drawn by hand, like the charts.
"""

import math

import pygame

from src.render import theme
from src.utils.ui import draw_text

GRID = (32, 34, 40)
FILL_ALPHA = 70


def _point(center, radius: float, i: int, n: int, value: float):
    angle = -math.pi / 2 + 2 * math.pi * i / n
    return (
        center[0] + math.cos(angle) * radius * value,
        center[1] + math.sin(angle) * radius * value,
    )


def draw_radar(
    surface,
    center: tuple[int, int],
    radius: int,
    values: list[float],
    color: tuple = theme.ACCENT,
    reference: list[float] | None = None,
    labels: list[str] | None = None,
) -> list:
    """Draws it; returns (Rect, label) for each label drawn."""
    n = len(values)
    if n < 3:
        return []
    for ring in (0.5, 1.0):  # the grid: half and full
        points = [_point(center, radius, i, n, ring) for i in range(n)]
        pygame.draw.polygon(surface, GRID, points, 1)
    for i in range(n):
        pygame.draw.line(
            surface, GRID, center, _point(center, radius, i, n, 1.0)
        )
    if reference:
        points = [
            _point(center, radius, i, n, v) for i, v in enumerate(reference)
        ]
        pygame.draw.polygon(surface, theme.TEXT_DIM, points, 1)
    points = [
        _point(center, radius, i, n, max(v, 0.03))
        for i, v in enumerate(values)
    ]
    size = radius * 2 + 4
    layer = pygame.Surface((size, size), pygame.SRCALPHA)
    offset = (center[0] - size // 2, center[1] - size // 2)
    local = [(x - offset[0], y - offset[1]) for x, y in points]
    pygame.draw.polygon(layer, (*color, FILL_ALPHA), local)
    surface.blit(layer, offset)
    pygame.draw.polygon(surface, color, points, 2)
    drawn = []
    if labels:
        for i, label in enumerate(labels):
            x, y = _point(center, radius + 14, i, n, 1.0)
            if abs(x - center[0]) < 4:
                anchor = "midbottom" if y < center[1] else "midtop"
            else:
                anchor = "midleft" if x > center[0] else "midright"
            rect = draw_text(
                surface,
                label,
                (x, y),
                theme.HEADER_SIZE,
                theme.TEXT_DIM,
                anchor=anchor,
            )
            drawn.append((rect, label))
    return drawn
