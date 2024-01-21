import pygame
from ml_collections import ConfigDict

from src.utils.types import Colors, ColorValue, WindowConstants


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


def draw_texts(
    surface: pygame.Surface,
    texts: list[str],
    size: int,
    x: int,
    y: int,
    color: ColorValue = Colors.WHITE,
):
    font = pygame.font.SysFont("monospace", size)
    for i, text in enumerate(texts):
        text_surface = font.render(text, True, color)
        text_rect = text_surface.get_rect()
        text_rect.topleft = (x, y + (i * size))
        surface.blit(text_surface, text_rect)
