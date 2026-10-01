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


def wrap_name(text: str, width: float, size: int, lines: int) -> list[str]:
    """A bold name on up to `lines` lines, broken at spaces (a word longer
    than a line is broken where it must). Only what still doesn't fit gets
    "…": names stay whole whenever they can (7c11).
    """
    font = get_font(size, True)
    words, found, line = text.split(), [], ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if line and font.size(candidate)[0] > width:
            found.append(line)
            line = word
        else:
            line = candidate
        while font.size(line)[0] > width and len(line) > 1:  # a long word
            cut = len(line)
            while cut > 1 and font.size(line[:cut])[0] > width:
                cut -= 1
            found.append(line[:cut])
            line = line[cut:]
    if line:
        found.append(line)
    if len(found) > lines:
        rest = " ".join(found[lines - 1 :])
        found = found[: lines - 1] + [fit(rest, width, True, size)]
    return found
