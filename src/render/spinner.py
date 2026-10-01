"""A busy spinner: a ring of dots, the brightest going round, so a
window that's working never looks stuck (the showcase getting ready, a
run starting in the control center).
"""

import math

import pygame
from pygame import Surface

from src.render import theme

DOTS = 10
STEP_MS = 90  # one dot further around per step


def draw_spinner(
    surface, center: tuple[int, int], radius: int = 24, shade: bool = True
) -> None:
    """Draws it at `center`, on a dark disc if `shade`."""
    if shade:
        size = 2 * radius + 24
        disc = Surface((size, size), pygame.SRCALPHA)
        half = size // 2
        pygame.draw.circle(disc, (*theme.BACKGROUND, 225), (half, half), half)
        surface.blit(disc, (center[0] - half, center[1] - half))
    lead = pygame.time.get_ticks() // STEP_MS % DOTS
    dot = max(round(radius / 5), 2)
    for i in range(DOTS):
        angle = 2 * math.pi * i / DOTS - math.pi / 2
        age = (lead - i) % DOTS  # 0: the leading dot
        fade = 1.0 - age / DOTS
        color = tuple(
            round(dim + (bright - dim) * fade)
            for dim, bright in zip(theme.PANEL_BORDER, theme.ACCENT)
        )
        spot = (
            center[0] + radius * math.cos(angle),
            center[1] + radius * math.sin(angle),
        )
        pygame.draw.circle(surface, color, spot, dot if age else dot + 2)
