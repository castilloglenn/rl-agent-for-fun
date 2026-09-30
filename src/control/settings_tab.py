"""The Settings tab (roadmap 7c6, decision 040): your display settings,
the same ones as a game window's O box, in `user/settings.json`. A change
saves at once, and every game window opened after it uses it. A change
made in a game window shows up here too (the file is read again every few
seconds).

    ┌ SETTINGS ───────────────────────────────────────────────┐
    │ Display only: nothing here changes the simulation, ...   │
    │ CAR                                                      │
    │   Bars                         [above            v]      │
    │   Bars shown                   [always           v]      │
    │ LINES ...                                                │
    └──────────────────────────────────────────────────────────┘
"""

import time
from pathlib import Path

import pygame
import pygame_gui
from pygame import Rect
from pygame_gui.elements import UIDropDownMenu

from src.control.text import PAD, header, wrap
from src.control.tooltips import Tooltips
from src.render import theme
from src.utils.settings import OPTIONS, SETTINGS_PATH, Settings
from src.utils.ui import draw_text

ROW = 30
GAP = 8
GROUP_GAP = 18  # extra room above a group's header
LABEL_WIDTH = 300
MENU_WIDTH = 260
REFRESH = 2.0  # seconds between reading the file again
NOTE = (
    "Display only: nothing here changes the simulation, so replays, runs, "
    "and scores never depend on it. In a game window, O opens the same "
    "settings; H, T, and F change them too."
)


class SettingsTab:
    def __init__(self, gui, area: Rect, path: Path | None = None) -> None:
        """`path`: your settings file (app.py passes user/settings.json).
        None keeps them in memory, so tests never touch yours.
        """
        self.gui = gui
        self.area = area
        self.path = Path(path) if path else None
        self.settings = Settings.load(self.path)
        self.tips = Tooltips()  # the window shares its own
        self.visible = True
        self.message: tuple[str, tuple] | None = None
        self._refreshed = time.monotonic()
        self.menus: dict[str, UIDropDownMenu] = {}
        self.rows: list[tuple[str, int]] = []  # ("group" or key, y)
        self._build()

    # Widgets

    def _build(self) -> None:
        for menu in self.menus.values():
            menu.kill()
        self.menus, self.rows = {}, []
        x = self.area.x + PAD
        y = self.area.y + 100
        group = None
        for option in OPTIONS:
            if option.group != group:
                group = option.group
                y += GROUP_GAP if self.rows else 0
                self.rows.append(("group:" + group, y))
                y += ROW
            self.rows.append((option.key, y))
            choices = [
                (text, str(i)) for i, (_, text) in enumerate(option.choices)
            ]
            values = [value for value, _ in option.choices]
            at = values.index(self.settings[option.key])
            self.menus[option.key] = UIDropDownMenu(
                choices,
                choices[at],
                Rect(x + LABEL_WIDTH, y, MENU_WIDTH, ROW),
                self.gui,
            )
            y += ROW + GAP
        if not self.visible:
            self.hide()

    def widgets(self) -> list:
        return list(self.menus.values())

    def show(self) -> None:
        self.visible = True
        for widget in self.widgets():
            widget.show()
        self.refresh(force=True)

    def hide(self) -> None:
        self.visible = False
        for widget in self.widgets():
            widget.hide()

    def dropdown_open(self) -> bool:
        return any(
            menu.current_state is menu.menu_states["expanded"]
            for menu in self.menus.values()
        )

    # Reading and saving

    def refresh(self, force: bool = False) -> None:
        """Reads the file again (a game window may have changed it)."""
        now = time.monotonic()
        if not force and now - self._refreshed < REFRESH:
            return
        self._refreshed = now
        if self.path is None:
            return
        on_disk = Settings.load(self.path)
        if on_disk.values != self.settings.values and not self.dropdown_open():
            self.settings = on_disk
            self._build()

    def handle(self, event) -> None:
        if event.type != pygame_gui.UI_DROP_DOWN_MENU_CHANGED:
            return
        for key, menu in self.menus.items():
            if event.ui_element is menu:
                self.pick(key, int(menu.selected_option[1]))

    def pick(self, key: str, index: int) -> None:
        """Sets `key` to its choice number `index`, and saves it."""
        option = next(o for o in OPTIONS if o.key == key)
        value, shown = option.choices[index]
        self.settings.set(key, value)
        self.message = (
            f"Saved: {option.label} is {shown}. Game windows opened from "
            "now on use it.",
            theme.GOOD,
        )

    # Drawing

    def _where(self) -> str:
        if self.path is None:
            return "in memory"
        try:
            return str(self.path.relative_to(SETTINGS_PATH.parents[1]))
        except ValueError:
            return self.path.name

    def draw(self, surface) -> None:
        area = self.area
        pygame.draw.rect(surface, theme.PANEL_BORDER, area, 1)
        header(surface, area, "SETTINGS")
        x = area.x + PAD
        note = f"{self._where()} · {NOTE}"
        for i, line in enumerate(wrap(note, area.w - 2 * PAD)):
            draw_text(
                surface,
                line,
                (x, area.y + 40 + i * 20),
                theme.TEXT_SIZE,
                theme.TEXT_DIM,
            )
        labels = {o.key: o.label for o in OPTIONS}
        for key, y in self.rows:
            if key.startswith("group:"):
                draw_text(
                    surface,
                    key[len("group:"):].upper(),
                    (x, y + 8),
                    theme.HEADER_SIZE,
                    theme.ACCENT,
                    bold=True,
                )
            else:
                draw_text(
                    surface,
                    labels[key],
                    (x + 16, y + 6),
                    theme.TEXT_SIZE,
                    theme.TEXT,
                )
        if self.message:
            text, color = self.message
            draw_text(
                surface,
                text,
                (x, area.bottom - PAD - 20),
                theme.TEXT_SIZE,
                color,
            )
