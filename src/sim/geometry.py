from functools import lru_cache

import pygame
from pygame import Rect, Surface

from src.utils.types import Coordinate


@lru_cache
def _blank_surface(width: int, height: int) -> Surface:
    return Surface((width, height), pygame.SRCALPHA, 32)


def rotated_bounds(
    width: int, height: int, angle: float, center: Coordinate
) -> Rect:
    """Axis-aligned bounds of a width x height box rotated by angle.

    Uses pygame's own rotation so the size matches the pre-ECS hitbox
    exactly. No window is needed. See decision 005 (refactor risk).
    """
    rotated = pygame.transform.rotate(_blank_surface(width, height), angle)
    return rotated.get_rect(center=center)
