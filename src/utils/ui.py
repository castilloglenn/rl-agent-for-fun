import pygame
from ml_collections import ConfigDict

from src.utils.types import WindowConstants


def get_window_constants(config: ConfigDict) -> WindowConstants:
    return WindowConstants(
        title=config.window.title,
        width=config.window.width,
        half_width=config.window.width // 2,
        quarter_width=config.window.width // 4,
        height=config.window.height,
        half_height=config.window.height // 2,
        quarter_height=config.window.height // 4,
    )


def draw_line(surface, start_pos, end_pos, color, width=1):
    pygame.draw.line(surface, color, start_pos, end_pos, width)


def rotate_surface(surface, angle):
    rotated_surface = pygame.transform.rotate(surface, angle)
    return rotated_surface
