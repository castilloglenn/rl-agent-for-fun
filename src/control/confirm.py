"""The control center's confirmation box, in the game window's style: it
dims the window and asks, with Cancel (Esc) and a confirm button (Enter).
Quitting uses it, and so do deleting a run and emptying the trash (6b3).

Its buttons act like any button: on release, if the mouse is still on
the one it pressed. While it's open, nothing behind it reacts.
"""

from dataclasses import dataclass
from typing import Callable

import pygame
from pygame import Rect

from src.render import theme
from src.utils.ui import draw_text, get_font

ROW = 30
GAP = 8
PAD_X = 28  # inside the box, left and right
LIT = (20, 60, 95)  # the confirm button, like the open tab
BUTTON = (24, 25, 30)


@dataclass
class Confirm:
    title: str  # "QUIT?"
    lines: list[tuple[str, tuple]]  # (text, color)
    on_confirm: Callable[[], None]
    confirm_label: str = "Confirm (Enter)"
    title_color: tuple = theme.WARN

    def __post_init__(self) -> None:
        self.buttons: dict[str, Rect] = {}  # where they were last drawn
        self.pressed: str | None = None

    def button_at(self, pos) -> str | None:
        found = self.buttons.items()
        return next((k for k, r in found if r.collidepoint(pos)), None)

    def handle(self, event) -> str | None:
        """"cancel" or "confirm" when it's decided, else None."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return "cancel"
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                return "confirm"
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.pressed = self.button_at(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            pressed, self.pressed = self.pressed, None
            if pressed and self.button_at(event.pos) == pressed:
                return pressed
        return None

    def draw(self, surface) -> None:
        size = surface.get_size()
        shade = pygame.Surface(size, pygame.SRCALPHA)
        shade.fill((*theme.BACKGROUND, 170))
        surface.blit(shade, (0, 0))
        font = get_font(theme.TEXT_SIZE)
        bold = get_font(theme.TEXT_SIZE, True)
        labels = {"cancel": "Cancel (Esc)", "confirm": self.confirm_label}
        widths = {k: bold.size(v)[0] + 2 * 18 for k, v in labels.items()}
        width = max(
            [font.size(text)[0] for text, _ in self.lines]
            + [sum(widths.values()) + GAP]
        ) + 2 * PAD_X
        box = Rect(0, 0, width, 64 + 22 * len(self.lines) + 20 + ROW + 24)
        box.center = (size[0] // 2, size[1] // 2)
        pygame.draw.rect(surface, theme.BACKGROUND, box)
        pygame.draw.rect(surface, theme.PANEL_BORDER, box, 1)
        y = box.y + 24
        draw_text(
            surface,
            self.title,
            (box.centerx, y),
            theme.BIG_SIZE,
            self.title_color,
            bold=True,
            anchor="midtop",
        )
        y += 40
        for text, color in self.lines:
            draw_text(
                surface,
                text,
                (box.centerx, y),
                theme.TEXT_SIZE,
                color,
                anchor="midtop",
            )
            y += 22
        # The buttons, right-aligned: Cancel, then the confirm one.
        x = box.right - PAD_X
        top = box.bottom - 24 - ROW
        for key in ("confirm", "cancel"):
            rect = Rect(0, top, widths[key], ROW)
            rect.right = x
            lit = key == "confirm"
            pygame.draw.rect(surface, LIT if lit else BUTTON, rect)
            pygame.draw.rect(
                surface, theme.ACCENT if lit else theme.PANEL_BORDER, rect, 1
            )
            draw_text(
                surface,
                labels[key],
                rect.center,
                theme.TEXT_SIZE,
                theme.TEXT,
                bold=True,
                anchor="center",
            )
            self.buttons[key] = rect
            x = rect.left - GAP
