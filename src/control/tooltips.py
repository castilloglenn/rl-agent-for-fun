"""Tooltips for the control center (decision 030): hold the mouse on a
marked item for half a second and a small box explains it.

While drawing, each tab registers "this rectangle has this help" (and
can draw the small circled "i" marker after a label). After everything
else, the window draws the one tooltip under the mouse. The texts are in
help.py.
"""

import pygame
from pygame import Rect

from src.control.text import wrap
from src.render import theme
from src.utils.ui import draw_text, get_font

DELAY = 0.5  # seconds on the same item before it opens
WIDTH = 320  # the text's wrap width
PAD = 10
MARKER = 5  # the "i" marker's radius
BG = (14, 15, 18)


class Tooltips:
    def __init__(self) -> None:
        self.targets: list[tuple[Rect, str]] = []
        self._hovered: tuple | None = None  # (rect as a tuple, text)
        self._since = 0.0

    def begin(self) -> None:
        """A new frame: the tabs register their targets again."""
        self.targets = []

    def add(self, rect: Rect, text: str) -> None:
        if text and rect.w > 0 and rect.h > 0:
            self.targets.append((Rect(rect), text))

    def marker(self, surface, left: int, center_y: int) -> Rect:
        """The dim circled "i" at (left, center_y); returns its area."""
        center = (left + MARKER, center_y)
        pygame.draw.circle(surface, theme.TEXT_DIM, center, MARKER, 1)
        pygame.draw.line(
            surface,
            theme.TEXT_DIM,
            (center[0], center_y - 1),
            (center[0], center_y + 2),
        )
        surface.set_at((center[0], center_y - 3), theme.TEXT_DIM)
        return Rect(left, center_y - MARKER, 2 * MARKER + 1, 2 * MARKER + 1)

    def label(
        self,
        surface,
        text: str,
        position: tuple[int, int],
        help_text: str,
        size: int = theme.TEXT_SIZE,
        color=theme.TEXT,
        bold: bool = False,
    ) -> Rect:
        """A label with its marker and tooltip (if it has help)."""
        rect = draw_text(surface, text, position, size, color, bold)
        if help_text:
            mark = self.marker(surface, rect.right + 6, rect.centery)
            self.add(rect.union(mark), help_text)
            return rect.union(mark)
        return rect

    def hovered(self, mouse) -> str | None:
        found = None
        for rect, text in self.targets:  # the last drawn is on top
            if rect.collidepoint(mouse):
                found = (tuple(rect), text)
        if found != self._hovered:
            self._hovered = found
            self._since = 0.0
        return found[1] if found else None

    def draw(
        self, surface, mouse, elapsed: float, blocked: bool = False
    ) -> str | None:
        """The tooltip under the mouse, once it has rested there DELAY
        seconds. `blocked` (a dropdown or a box is open) hides it.
        Returns the text shown, if any.
        """
        text = None if blocked else self.hovered(mouse)
        if blocked:
            self._hovered, self._since = None, 0.0
            return None
        if not text:
            return None
        self._since += elapsed
        if self._since < DELAY:
            return None
        lines = wrap(text, WIDTH)
        font = get_font(theme.TEXT_SIZE)
        width = max(font.size(line)[0] for line in lines) + 2 * PAD
        box = Rect(0, 0, width, 20 * len(lines) + 2 * PAD - 2)
        box.topleft = (mouse[0] + 14, mouse[1] + 18)
        screen = surface.get_rect()
        if box.right > screen.right - 8:
            box.right = mouse[0] - 8
        if box.bottom > screen.bottom - 8:
            box.bottom = mouse[1] - 8
        box.clamp_ip(screen.inflate(-16, -16))
        pygame.draw.rect(surface, BG, box)
        pygame.draw.rect(surface, theme.ACCENT, box, 1)
        y = box.y + PAD
        for line in lines:
            draw_text(
                surface, line, (box.x + PAD, y), theme.TEXT_SIZE, theme.TEXT
            )
            y += 20
        return text
