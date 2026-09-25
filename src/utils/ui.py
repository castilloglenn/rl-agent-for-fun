from functools import lru_cache

import pygame
from pygame import Rect, Surface

from src.utils.types import Colors, ColorValue


@lru_cache
def get_font(size: int, bold: bool = False) -> pygame.font.Font:
    """Cached, since creating a SysFont is slow. Needs pygame.init()."""
    return pygame.font.SysFont("monospace", size, bold=bold)


def draw_text(
    surface: Surface,
    text: str,
    position: tuple[float, float],
    size: int = 14,
    color: ColorValue = Colors.WHITE,
    bold: bool = False,
    anchor: str = "topleft",
) -> Rect:
    """Draws one line of text. `anchor` is any pygame Rect position name."""
    rendered = get_font(size, bold).render(text, True, color)
    rect = rendered.get_rect(**{anchor: position})
    surface.blit(rendered, rect)
    return rect
