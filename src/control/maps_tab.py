"""The control center's Maps tab (roadmap step 7c3): every stage as a card
with a drawn preview, and the selected one's details, what uses it, and
what to do with it.

    ┌ MAPS · 4  [sort ▾] ┐ ┌ MAP ────────────────────────────────┐
    │ ┌ card ┐ ┌ card ┐  │ │ a big preview    size, walls, ...   │
    │ └──────┘ └──────┘  │ │ USED BY: runs, suites               │
    │                    │ │ [Edit] [Drive] [driver ▾] [Watch]   │
    │                    │ │ [new name] [New map] [Duplicate] .. │
    └────────────────────┘ └─────────────────────────────────────┘

Its buttons start the Commands tab's actions (the editor and game
windows); duplicating and deleting are file operations, like the Files
tab's.
"""

import time
from pathlib import Path
from typing import Callable

import pygame
import pygame_gui
from pygame import Rect
from pygame_gui.elements import UIButton, UIDropDownMenu, UITextEntryLine

from src.control import actions, help, maps_data
from src.control.confirm import Confirm
from src.control.maps_data import MapError, MapInfo
from src.control.stage_preview import draw_stage_preview
from src.control.text import PAD, fit, header, wrap
from src.control.tooltips import Tooltips
from src.control.trash import Trash, TrashError
from src.render import theme
from src.utils.ui import draw_text

LIST_WIDTH = 600
MARGIN = 16
ROW = 30
GAP = 8
REFRESH = 2.0  # seconds between reads of stages/ and the runs
CARD = (278, 176)
CARD_GAP = (16, 12)
PREVIEW = (254, 120)  # a card's preview
SCROLL_STEP = 40
SORTS = ("name", "newest", "walls")
LIT = (20, 60, 95)
CARD_BG = (18, 19, 23)
BADGE_COLORS = {
    "BUILT-IN": theme.TEXT_DIM,
    "YOURS": theme.GOOD,
    "DEFAULT": theme.ACCENT,
    "SUITE": theme.WARN,
    "BIG": (160, 120, 230),
}


class MapsTab:
    def __init__(
        self,
        gui,
        area: Rect,
        ask: Callable[[Confirm], None],
        run_action: Callable[[str, dict], object],
        root: Path | None = None,
        runs_dir: Path | None = None,
    ) -> None:
        """`root`: the repo, with stages/ and suites/ (tests use a copy).
        `run_action(name, values)` runs a Commands tab action.
        """
        self.gui = gui
        self.ask = ask
        self.run_action = run_action
        self.root = root or maps_data.REPO
        self.runs_dir = runs_dir
        self.tips = Tooltips()  # the window shares its own
        self.list_box = Rect(area.x, area.y, LIST_WIDTH, area.h)
        self.detail = Rect(
            self.list_box.right + MARGIN,
            area.y,
            area.right - self.list_box.right - MARGIN,
            area.h,
        )
        box = self.list_box
        self.content = Rect(
            box.x + PAD, box.y + 48, box.w - 2 * PAD, box.h - 48 - PAD
        )
        self.sort_menu = UIDropDownMenu(
            [f"sort: {s}" for s in SORTS],
            "sort: name",
            Rect(box.right - PAD - 150, box.y + 8, 150, 26),
            gui,
        )
        d = self.detail
        self.preview_rect = Rect(d.x + PAD, d.y + 72, 380, 250)
        rows_b = d.bottom - PAD - ROW
        rows_a = rows_b - GAP - ROW
        self.buttons: dict[str, UIButton] = {}
        x = d.x + PAD
        for name, width in (("Edit", 90), ("Drive", 90)):
            self.buttons[name] = UIButton(
                Rect(x, rows_a, width, ROW), name, gui
            )
            x += width + GAP
        x += 2 * GAP
        self.driver_x = x
        self.driver_menu = None
        self._build_driver_menu()
        self.buttons["Watch"] = UIButton(
            Rect(x + 220 + GAP, rows_a, 90, ROW), "Watch", gui
        )
        x = d.x + PAD
        self.new_name = UITextEntryLine(Rect(x, rows_b, 200, ROW), gui)
        x += 200 + GAP
        for name, width in (("New map", 110), ("Duplicate", 110)):
            self.buttons[name] = UIButton(
                Rect(x, rows_b, width, ROW), name, gui
            )
            x += width + GAP
        self.buttons["Delete"] = UIButton(
            Rect(d.right - PAD - 100, rows_b, 100, ROW), "Delete", gui
        )
        self.rows_a, self.rows_b = rows_a, rows_b
        self.maps: list[MapInfo] = []
        self.sort = SORTS[0]
        self.selected: str | None = None
        self.scroll = 0
        self.content_height = 0
        self.hit: list[tuple[Rect, str]] = []
        self.message: tuple[str, tuple] | None = None
        self._refreshed = 0.0
        self.visible = True
        self.refresh(force=True)

    def _build_driver_menu(self) -> None:
        if self.driver_menu:
            self.driver_menu.kill()
        options = actions._drivers(False)()
        top = self.detail.bottom - PAD - 2 * ROW - GAP
        self.driver_menu = UIDropDownMenu(
            options,
            options[0],
            Rect(self.driver_x, top, 220, ROW),
            self.gui,
        )
        if not getattr(self, "visible", True):
            self.driver_menu.hide()

    # Showing and hiding with the tab

    def widgets(self) -> list:
        return [
            self.sort_menu,
            self.driver_menu,
            self.new_name,
            *self.buttons.values(),
        ]

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
            for menu in (self.sort_menu, self.driver_menu)
        )

    # Reading

    def refresh(self, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self._refreshed < REFRESH:
            return
        self._refreshed = now
        self.maps = maps_data.load_maps(self.root, self.runs_dir)
        names = [m.name for m in self.maps]
        if self.selected not in names:
            ordered = self.ordered()
            self.selected = ordered[0].name if ordered else None
        self._update_buttons()

    def ordered(self) -> list[MapInfo]:
        return maps_data.sort_maps(self.maps, self.sort)

    @property
    def map(self) -> MapInfo | None:
        return next((m for m in self.maps if m.name == self.selected), None)

    def select(self, name: str) -> None:
        self.selected = name
        self.message = None
        self._update_buttons()

    def _update_buttons(self) -> None:
        chosen = self.map
        wanted = {
            "Edit": bool(chosen),
            "Drive": bool(chosen),
            "Watch": bool(chosen),
            "New map": True,
            "Duplicate": bool(chosen),
            "Delete": bool(chosen and not chosen.protected),
        }
        for name, on in wanted.items():
            button = self.buttons[name]
            if on and not button.is_enabled:
                button.enable()
            elif not on and button.is_enabled:
                button.disable()

    # Acting

    def press(self, name: str) -> None:
        chosen = self.map
        started = None
        if name == "Edit" and chosen:
            started = self.run_action("Edit a map", {"Map": chosen.name})
        elif name == "Drive" and chosen:
            started = self.run_action("Drive", {"Stage": chosen.name})
        elif name == "Watch" and chosen:
            option = self.driver_menu.selected_option
            driver = option[1] if isinstance(option, tuple) else option
            started = self.run_action(
                "Watch a driver", {"Driver": driver, "Stage": chosen.name}
            )
        elif name == "New map":
            self._new_map()
        elif name == "Duplicate" and chosen:
            self._duplicate(chosen)
        elif name == "Delete" and chosen and not chosen.protected:
            self._ask_delete(chosen)
        if started:
            self.message = (f"Started job #{started.number}", theme.GOOD)

    def _new_map(self) -> None:
        try:
            name = maps_data.check_new_name(
                self.root, self.new_name.get_text()
            )
        except MapError as error:
            self.message = (str(error), theme.BAD)
            return
        self.new_name.set_text("")
        started = self.run_action("Edit a map", {"Map": name})
        if started:
            self.message = (
                f"The editor opens {name}: save it to add it here.",
                theme.GOOD,
            )

    def _duplicate(self, chosen: MapInfo) -> None:
        try:
            path = maps_data.duplicate(
                self.root, chosen.name, self.new_name.get_text()
            )
        except MapError as error:
            self.message = (str(error), theme.BAD)
            return
        self.new_name.set_text("")
        self.refresh(force=True)
        self.select(path.stem)
        self.message = (f"Made stages/{path.name}", theme.GOOD)

    def _ask_delete(self, chosen: MapInfo) -> None:
        name = chosen.name

        def go() -> None:
            try:
                entry = Trash(self.root).delete_file("stages", name)
            except TrashError as error:
                self.message = (str(error), theme.BAD)
                return
            self.refresh(force=True)
            self.message = (
                f"Moved stages/{name}.json into the trash ({entry.name}).",
                theme.GOOD,
            )

        lines = [(f"stages/{name}.json moves into the trash.", theme.TEXT)]
        if chosen.runs:
            lines.append(
                (
                    f"{chosen.runs} run{'s' if chosen.runs > 1 else ''} "
                    "played on it: they keep their own copy of the map.",
                    theme.TEXT_DIM,
                )
            )
        lines.append(("You can restore it later.", theme.TEXT_DIM))
        self.ask(
            Confirm(
                "DELETE A MAP?",
                lines,
                go,
                confirm_label="Delete (Enter)",
                title_color=theme.BAD,
            )
        )

    # Events

    def handle(self, event) -> None:
        if event.type == pygame_gui.UI_DROP_DOWN_MENU_CHANGED:
            if event.ui_element is self.sort_menu:
                self.sort = event.text.replace("sort: ", "")
        elif event.type == pygame_gui.UI_BUTTON_PRESSED:
            for name, button in self.buttons.items():
                if event.ui_element is button:
                    self.press(name)
        elif event.type == pygame_gui.UI_TEXT_ENTRY_CHANGED:
            self.message = None
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.click(event.pos)
        elif event.type == pygame.MOUSEWHEEL:
            if self.content.collidepoint(pygame.mouse.get_pos()):
                most = max(self.content_height - self.content.h, 0)
                self.scroll = min(
                    max(self.scroll - event.y * SCROLL_STEP, 0), most
                )

    def click(self, pos) -> None:
        if self.dropdown_open() or not self.content.collidepoint(pos):
            return
        for rect, name in self.hit:
            if rect.collidepoint(pos):
                self.select(name)
                return

    # Drawing

    def draw(self, surface) -> None:
        for rect in (self.list_box, self.detail):
            pygame.draw.rect(surface, theme.PANEL_BORDER, rect, 1)
        header(surface, self.list_box, f"MAPS · {len(self.maps)}")
        surface.set_clip(self.content)
        self.hit = []
        width, height = CARD
        gap_x, gap_y = CARD_GAP
        ordered = self.ordered()
        for i, info in enumerate(ordered):
            rect = Rect(
                self.content.x + (i % 2) * (width + gap_x),
                self.content.y + (i // 2) * (height + gap_y) - self.scroll,
                width,
                height,
            )
            self._draw_card(surface, rect, info)
            self.hit.append((rect, info.name))
        self.content_height = (len(ordered) + 1) // 2 * (height + gap_y)
        surface.set_clip(None)
        self._draw_scrollbar(surface)
        if self.map:
            self._draw_detail(surface, self.map)
        self._draw_message(surface)

    def _draw_card(self, surface, rect: Rect, info: MapInfo) -> None:
        chosen = info.name == self.selected
        pygame.draw.rect(surface, LIT if chosen else CARD_BG, rect)
        pygame.draw.rect(
            surface, theme.ACCENT if chosen else theme.PANEL_BORDER, rect, 1
        )
        preview = Rect(rect.x + 12, rect.y + 10, *PREVIEW)
        draw_stage_preview(surface, preview, info.data)
        y = preview.bottom + 8
        draw_text(
            surface,
            fit(info.name, rect.w - 24, True),
            (rect.x + 12, y),
            theme.TEXT_SIZE,
            theme.TEXT,
            bold=True,
        )
        width, height = info.size
        draw_text(
            surface,
            f"{width:g} × {height:g} · {info.walls} walls",
            (rect.x + 12, y + 20),
            theme.HEADER_SIZE,
            theme.TEXT_DIM,
        )
        bx = rect.right - 12
        for badge in reversed(info.badges()):
            color = BADGE_COLORS[badge]
            label = draw_text(
                surface,
                badge,
                (bx - 6, y + 3),
                11,
                color,
                bold=True,
                anchor="topright",
            )
            pygame.draw.rect(surface, color, label.inflate(12, 6), 1)
            self.tips.add(label.inflate(12, 6), help.topic(f"map:{badge}"))
            bx = label.x - 14

    def _draw_scrollbar(self, surface) -> None:
        view = self.content
        most = self.content_height - view.h
        if most <= 0:
            return
        track = Rect(self.list_box.right - 7, view.y, 3, view.h)
        pygame.draw.rect(surface, theme.BAR_EMPTY, track)
        thumb = max(view.h * view.h // self.content_height, 24)
        y = view.y + (view.h - thumb) * self.scroll // most
        pygame.draw.rect(surface, theme.TEXT_DIM, Rect(track.x, y, 3, thumb))

    def _draw_detail(self, surface, info: MapInfo) -> None:
        d = self.detail
        x = d.x + PAD
        header(surface, d, "MAP")
        draw_text(
            surface,
            fit(info.name, d.w - 2 * PAD, True, theme.BIG_SIZE),
            (x, d.y + 34),
            theme.BIG_SIZE,
            theme.TEXT,
            bold=True,
        )
        draw_stage_preview(surface, self.preview_rect, info.data)
        width, height = info.size
        checkpoints = info.checkpoints
        if checkpoints.get("mode") == "scripted":
            count = len(checkpoints.get("points", []))
            cps = f"in order, {count}"
        else:
            cps = "random"
        spawn = (info.data.get("spawns") or [{}])[0]
        rows = [
            ("Size", f"{width:g} × {height:g}"),
            ("Walls", str(info.walls)),
            ("Checkpoints", cps),
            ("Spawn", f"{spawn.get('x', 0):g}, {spawn.get('y', 0):g}"),
            ("Heading", f"{spawn.get('angle', 0):g}°"),
            ("View", "followed, map card" if info.big else "1:1"),
        ]
        rx = self.preview_rect.right + 20
        y = self.preview_rect.y
        for label, value in rows:
            draw_text(surface, label, (rx, y), theme.TEXT_SIZE, theme.TEXT_DIM)
            draw_text(
                surface,
                value,
                (d.right - PAD, y),
                theme.TEXT_SIZE,
                theme.TEXT,
                anchor="topright",
            )
            y += 22
        y = self.preview_rect.bottom + 20
        used = self.tips.label(
            surface,
            "USED BY",
            (x, y),
            help.topic("map:used by"),
            theme.HEADER_SIZE,
            theme.ACCENT,
            bold=True,
        )
        y = used.bottom + 8
        for line in self._used_lines(info)[:6]:
            for part in wrap(line, d.w - 2 * PAD):
                draw_text(surface, part, (x, y), theme.TEXT_SIZE, theme.TEXT)
                y += 20
        if info.protected:
            delete = self.buttons["Delete"].rect
            self.tips.add(delete, f"Can't delete: {info.protected}.")
            draw_text(
                surface,
                fit(f"Protected: {info.protected}", d.w - 2 * PAD),
                (x, self.rows_a - 26),
                theme.TEXT_SIZE,
                theme.TEXT_DIM,
            )

    def _used_lines(self, info: MapInfo) -> list[str]:
        lines = []
        by_kind: dict[str, list[str]] = {}
        for (who, kind), count in sorted(info.played.items()):
            label = f"{who} ({count} run{'s' if count > 1 else ''})"
            by_kind.setdefault(kind, []).append(label)
        names = {
            "training": "Trained",
            "imitation": "Cloned",
            "episodes": "Episodes",
        }
        for kind, labels in by_kind.items():
            lines.append(f"{names.get(kind, kind)}: {', '.join(labels)}")
        if info.suites:
            lines.append(f"Suites: {', '.join(info.suites)}")
        return lines or ["Nothing yet: no runs played on it, no suite uses it."]

    def draw_after(self, surface) -> None:
        """After the GUI: the new name's hint, while it's blank."""
        entry = self.new_name
        if entry.get_text() or entry.is_focused or not entry.visible:
            return
        if self.dropdown_open():
            return
        draw_text(
            surface,
            "new map name",
            (entry.rect.x + 10, entry.rect.centery),
            theme.TEXT_SIZE,
            theme.TEXT_DIM,
            anchor="midleft",
        )

    def _draw_message(self, surface) -> None:
        if not self.message:
            return
        text, color = self.message
        d = self.detail
        draw_text(
            surface,
            fit(text, d.w - 2 * PAD),
            (d.x + PAD, self.rows_a - 26),
            theme.TEXT_SIZE,
            color,
        )
