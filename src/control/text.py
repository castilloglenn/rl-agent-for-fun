"""Text helpers the control center's tabs share: fitting, wrapping, and
box headers, in the game window's font.
"""

from pygame import Rect

from src.render import theme
from src.utils.ui import draw_text, get_font

PAD = 14  # a box's inner padding


def fit(
    text: str, width: float, bold: bool = False, size: int = theme.TEXT_SIZE
) -> str:
    """`text`, shortened with "…" to fit `width` pixels."""
    font = get_font(size, bold)
    if font.size(text)[0] <= width:
        return text
    while text and font.size(text + "…")[0] > width:
        text = text[:-1]
    return text + "…"


def wrap(text: str, width: float, size: int = theme.TEXT_SIZE) -> list[str]:
    """`text` split into lines of at most `width` pixels (at spaces)."""
    font = get_font(size)
    lines, line = [], ""
    for word in text.split():
        candidate = f"{line} {word}".strip()
        if line and font.size(candidate)[0] > width:
            lines.append(line)
            line = word
        else:
            line = candidate
    return lines + ([line] if line else [])


def header(surface, rect: Rect, text: str) -> None:
    """A box's title, top left, in the accent color."""
    draw_text(
        surface,
        text,
        (rect.x + PAD, rect.y + 12),
        theme.HEADER_SIZE,
        theme.ACCENT,
        bold=True,
    )
