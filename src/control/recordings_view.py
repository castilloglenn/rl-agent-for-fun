"""The recordings browser (roadmap step 6d2), inside the Files tab: a
player's recorded rounds as a table, with watch, keep, unkeep, and
delete into the trash.

    when            seed    score  ended    kept  game               datasets
    09-27 02:59:38  545170  2,433  all out        box / standard...  mine

The rows come from recordings_data.py. Keeping and unkeeping move the
file (recordings.py); deleting moves it into the trash (trash.py).
"""

from pathlib import Path
from typing import Callable

import pygame
import pygame_gui
from pygame import Rect
from pygame_gui.elements import UIButton, UIDropDownMenu

from src.control import help, recordings_data
from src.control.confirm import Confirm
from src.control.recordings_data import Recording
from src.control.text import PAD, fit, header
from src.control.tooltips import Tooltips
from src.control.trash import Trash, TrashError
from src.render import theme
from src.replay.recordings import RecordingError, keep_file, unkeep_file
from src.utils.ui import draw_text

ROW = 30
GAP = 8
LINE = 24  # a table row
SCROLL_STEP = 48
LIT = (20, 60, 95)
# (title, width, value, align)
COLUMNS = (
    ("when", 132, lambda r: r.when, "left"),
    ("seed", 80, lambda r: str(r.seed), "left"),
    ("score", 64, lambda r: f"{r.score:,.0f}", "right"),
    ("ended", 84, lambda r: r.ended, "left"),
    ("kept", 56, lambda r: "kept" if r.kept else "", "left"),
    ("game", 230, lambda r: r.game, "left"),
    ("datasets", 120, lambda r: ", ".join(r.datasets), "left"),
)
SORTS = ("newest", "score")


class RecordingsView:
    def __init__(
        self,
        gui,
        area: Rect,
        ask: Callable[[Confirm], None],
        run_action: Callable[[str, dict], object],
        root: Path,
    ) -> None:
        """`area`: the editor's box. `root`: the repo (recordings/,
        datasets/, trash/ under it).
        """
        self.gui = gui
        self.area = area
        self.ask = ask
        self.run_action = run_action
        self.root = root
        self.recordings_dir = root / "recordings"
        self.tips = Tooltips()  # the window shares its own
        a = area
        self.sort_menu = UIDropDownMenu(
            [f"sort: {s}" for s in SORTS],
            "sort: newest",
            Rect(a.right - PAD - 160, a.y + 6, 160, 26),
            gui,
        )
        self.buttons_y = a.bottom - PAD - ROW
        self.table = Rect(
            a.x + PAD, a.y + 48, a.w - 2 * PAD, self.buttons_y - 40 - a.y - 48
        )
        self.buttons: dict[str, UIButton] = {}
        x = a.x + PAD
        for name, width in (("Watch", 100), ("Keep", 90), ("Unkeep", 90)):
            self.buttons[name] = UIButton(
                Rect(x, self.buttons_y, width, ROW), name, gui
            )
            x += width + GAP
        self.buttons["Delete"] = UIButton(
            Rect(a.right - PAD - 100, self.buttons_y, 100, ROW), "Delete", gui
        )
        self.player: str | None = None
        self.sort = SORTS[0]
        self.rows: list[Recording] = []
        self.selected: Path | None = None
        self.scroll = 0
        self.message: tuple[str, tuple] | None = None
        self._headers: dict = {}
        self._hit: list[tuple[Rect, Path]] = []
        self.hide()

    # Showing and hiding

    def widgets(self) -> list:
        return [self.sort_menu, *self.buttons.values()]

    def show(self) -> None:
        self.visible = True
        for widget in self.widgets():
            widget.show()

    def hide(self) -> None:
        self.visible = False
        for widget in self.widgets():
            widget.hide()

    def dropdown_open(self) -> bool:
        menu = self.sort_menu
        return menu.current_state is menu.menu_states["expanded"]

    # Reading

    def open(self, player: str | None) -> None:
        if player != self.player:
            self.scroll = 0
            self.selected = None
            self.message = None
        self.player = player
        self.reload()

    def reload(self) -> None:
        self.rows = (
            recordings_data.recordings(
                self.player,
                self.recordings_dir,
                self.root,
                self.sort,
                self._headers,
            )
            if self.player
            else []
        )
        names = {r.path.name: r.path for r in self.rows}
        if self.selected and self.selected not in names.values():
            # It moved (kept or unkept): follow it by name.
            self.selected = names.get(self.selected.name)
        if not self.selected and self.rows:
            self.selected = self.rows[0].path
        self._update_buttons()

    @property
    def row(self) -> Recording | None:
        return next((r for r in self.rows if r.path == self.selected), None)

    def _update_buttons(self) -> None:
        row = self.row
        wanted = {
            "Watch": bool(row),
            "Keep": bool(row and not row.kept),
            "Unkeep": bool(row and row.kept),
            "Delete": bool(row),
        }
        for name, on in wanted.items():
            button = self.buttons[name]
            if on and not button.is_enabled:
                button.enable()
            elif not on and button.is_enabled:
                button.disable()

    # Acting

    def press(self, name: str) -> None:
        row = self.row
        if not row:
            return
        relative = row.path.relative_to(self.root)
        if name == "Watch":
            job = self.run_action("Watch a replay", {"File": str(relative)})
            if job:
                self.message = (f"Started job #{job.number}", theme.GOOD)
        elif name in ("Keep", "Unkeep"):
            try:
                moved = (keep_file if name == "Keep" else unkeep_file)(
                    row.path
                )
            except RecordingError as error:
                self.message = (str(error), theme.BAD)
                return
            self.selected = moved
            self.message = (
                (
                    "Kept: the latest-50 limit never removes it.",
                    theme.GOOD,
                )
                if name == "Keep"
                else (
                    "Back with the recent ones: the latest-50 limit applies "
                    "at your next saved round.",
                    theme.WARN,
                )
            )
            self.reload()
        elif name == "Delete":
            self._ask_delete(row, relative)

    def _ask_delete(self, row: Recording, relative: Path) -> None:
        def go() -> None:
            try:
                entry = Trash(self.root).delete_recording(row.path)
            except TrashError as error:
                self.message = (str(error), theme.BAD)
                return
            self.selected = None
            self.message = (
                f"Moved into the trash ({entry.name}).",
                theme.GOOD,
            )
            self.reload()

        self.ask(
            Confirm(
                "DELETE A RECORDING?",
                [
                    (f"{relative} moves into the trash.", theme.TEXT),
                    (
                        f"Score {row.score:,.0f}, {row.when}. You can "
                        "restore it later.",
                        theme.TEXT_DIM,
                    ),
                ],
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
                self.reload()
        elif event.type == pygame_gui.UI_BUTTON_PRESSED:
            for name, button in self.buttons.items():
                if event.ui_element is button:
                    self.press(name)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.click(event.pos)
        elif event.type == pygame.MOUSEWHEEL:
            if self.table.collidepoint(pygame.mouse.get_pos()):
                most = max(len(self.rows) * LINE - self._rows_h, 0)
                self.scroll = min(
                    max(self.scroll - event.y * SCROLL_STEP, 0), most
                )

    def click(self, pos) -> None:
        if self.dropdown_open():
            return
        for rect, path in self._hit:
            if rect.collidepoint(pos):
                self.selected = path
                self.message = None
                self._update_buttons()
                return

    @property
    def _rows_h(self) -> int:
        return self.table.h - LINE

    # Drawing

    def draw(self, surface) -> None:
        a = self.area
        kept = sum(r.kept for r in self.rows)
        title = f"RECORDINGS · {self.player or 'nobody yet'}"
        if self.player:
            title += f" · {len(self.rows)} ({kept} kept)"
        header(surface, a, title)
        table = self.table
        x = table.x
        y = table.y
        for name, width, _, align in COLUMNS:
            anchor = (x + width - 12, y) if align == "right" else (x, y)
            rect = draw_text(
                surface,
                name,
                anchor,
                theme.HEADER_SIZE,
                theme.TEXT_DIM,
                True,
                anchor="topright" if align == "right" else "topleft",
            )
            self.tips.add(rect.inflate(6, 6), help.topic(f"recording:{name}"))
            x += width
        body = Rect(table.x - 6, y + LINE, table.w + 6, self._rows_h)
        surface.set_clip(body)
        self._hit = []
        y = body.y - self.scroll
        for row in self.rows:
            line = Rect(body.x, y - 3, body.w, LINE)
            if row.path == self.selected:
                pygame.draw.rect(surface, LIT, line)
            if body.colliderect(line):
                self._hit.append((line.clip(body), row.path))
                self._draw_row(surface, row, table.x, y)
            y += LINE
        surface.set_clip(None)
        if not self.rows:
            draw_text(
                surface,
                "No recordings yet: drive a round (Commands: Drive).",
                (table.x, table.y + LINE),
                theme.TEXT_SIZE,
                theme.TEXT_DIM,
            )
        self._draw_scrollbar(surface, body)
        if self.message:
            text, color = self.message
            draw_text(
                surface,
                fit(text, a.w - 2 * PAD),
                (a.x + PAD, self.buttons_y - 30),
                theme.TEXT_SIZE,
                color,
            )

    def _draw_row(self, surface, row: Recording, x: int, y: int) -> None:
        for name, width, value, align in COLUMNS:
            text = fit(value(row), width - 12)
            color = theme.TEXT
            if name in ("kept",) or name == "game":
                color = theme.TEXT_DIM
            if align == "right":
                draw_text(
                    surface,
                    text,
                    (x + width - 12, y),
                    theme.TEXT_SIZE,
                    color,
                    anchor="topright",
                )
            else:
                draw_text(surface, text, (x, y), theme.TEXT_SIZE, color)
            x += width

    def _draw_scrollbar(self, surface, body: Rect) -> None:
        total = len(self.rows) * LINE
        if total <= body.h:
            return
        track = Rect(self.area.right - 7, body.y, 3, body.h)
        pygame.draw.rect(surface, theme.BAR_EMPTY, track)
        thumb = max(body.h * body.h // total, 24)
        most = total - body.h
        y = body.y + (body.h - thumb) * min(self.scroll, most) // most
        pygame.draw.rect(surface, theme.TEXT_DIM, Rect(track.x, y, 3, thumb))
