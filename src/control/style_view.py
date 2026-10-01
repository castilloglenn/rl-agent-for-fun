"""Driving style as graphs (roadmap 7c11): the pedals as a stacked bar,
turning as a left / straight / right split, and moving backward as a gauge
with its warning line. The colors match the Runs tab's style chart.
"""

import pygame
from pygame import Rect

from src.control.runs import STYLE_LINES
from src.render import theme
from src.utils import driving_style
from src.utils.ui import draw_text, get_font

PEDAL_COLORS = {column: color for _, column, color in STYLE_LINES}
TURN_COLORS = {
    "style_left": (90, 150, 230),
    "straight": (60, 64, 74),
    "style_right": (150, 110, 220),
}
BACKWARD_LINE = next(
    above for column, above, _ in driving_style.WARNINGS
    if column == "style_backward"
)


def draw_segments(surface, rect: Rect, parts: list[tuple[float, tuple]]):
    """A bar split into (share, color) parts, left to right. Returns each
    part's rect (for tooltips).
    """
    pygame.draw.rect(surface, theme.BAR_EMPTY, rect)
    x, drawn = rect.x, []
    total = sum(share for share, _ in parts) or 1.0
    for i, (share, color) in enumerate(parts):
        width = round(rect.w * share / total)
        if i == len(parts) - 1:
            width = rect.right - x  # no gap from rounding
        part = Rect(x, rect.y, max(width, 0), rect.h)
        if part.w > 0:
            pygame.draw.rect(surface, color, part)
        drawn.append(part)
        x += width
    return drawn


def pedal_parts(scores: dict) -> list[tuple[float, tuple]]:
    return [
        (scores.get(f"style_{p}") or 0.0, PEDAL_COLORS[f"style_{p}"])
        for p in driving_style.PEDALS
    ]


def draw_pedals(surface, rect: Rect, scores: dict) -> list[Rect]:
    return draw_segments(surface, rect, pedal_parts(scores))


def draw_legend(surface, x: int, y: int, scores: dict, width: int) -> int:
    """Each pedal's swatch, name, and share, on one line (two if needed).
    Returns the y under it.
    """
    font = get_font(theme.TEXT_SIZE)
    left = x
    for pedal in driving_style.PEDALS:
        column = f"style_{pedal}"
        text = f"{pedal} {scores.get(column) or 0:.0%}"
        need = 12 + 6 + font.size(text)[0] + 14
        if x + need > left + width:
            x, y = left, y + 20
        pygame.draw.rect(surface, PEDAL_COLORS[column], Rect(x, y + 4, 10, 10))
        draw_text(surface, text, (x + 16, y), theme.TEXT_SIZE, theme.TEXT)
        x += need
    return y + 22


def draw_turning(surface, rect: Rect, scores: dict) -> None:
    left = scores.get("style_left") or 0.0
    right = scores.get("style_right") or 0.0
    straight = max(1.0 - left - right, 0.0)
    parts = draw_segments(
        surface,
        rect,
        [
            (left, TURN_COLORS["style_left"]),
            (straight, TURN_COLORS["straight"]),
            (right, TURN_COLORS["style_right"]),
        ],
    )
    for part, text in zip(
        parts,
        (f"left {left:.0%}", f"straight {straight:.0%}", f"right {right:.0%}"),
    ):
        label_w = get_font(theme.HEADER_SIZE).size(text)[0]
        if part.w > label_w + 8:
            draw_text(
                surface,
                text,
                part.center,
                theme.HEADER_SIZE,
                theme.TEXT,
                anchor="center",
            )


def draw_backward(surface, rect: Rect, share: float) -> None:
    """A gauge: amber past the warning line (drawn as a tick)."""
    pygame.draw.rect(surface, theme.BAR_EMPTY, rect)
    color = theme.WARN if share > BACKWARD_LINE else theme.TEXT_DIM
    fill = Rect(rect.x, rect.y, round(rect.w * min(share, 1.0)), rect.h)
    if fill.w:
        pygame.draw.rect(surface, color, fill)
    tick = rect.x + round(rect.w * BACKWARD_LINE)
    pygame.draw.line(
        surface, theme.TEXT, (tick, rect.y - 3), (tick, rect.bottom + 2)
    )
    draw_text(
        surface,
        f"{share:.0%}",
        (rect.right + 8, rect.centery),
        theme.TEXT_SIZE,
        color,
        bold=True,
        anchor="midleft",
    )
