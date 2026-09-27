"""The control center's Runs tab (roadmap step 6b1): every run, and the
selected run's progress and live learning curves.

    ┌ RUNS ──────────┐ ┌ TRAINING RUN ───────────────────────────┐
    │ newest first   │ │ name, settings, status and progress     │
    │                │ │ ┌ SCORE ──────────────────────────────┐ │
    │                │ │ └─────────────────────────────────────┘ │
    │                │ │ ┌ Entropy ▾ ──────────────────────────┐ │
    │                │ │ └─────────────────────────────────────┘ │
    │                │ │ [Stop] [Pause] [Resume] [Resume ...]    │
    └────────────────┘ └─────────────────────────────────────────┘

It reads the run folders every second (runs.py) and starts the same
actions as the Commands tab, so nothing here is its own command.
"""

import time
from pathlib import Path
from typing import Callable

import pygame
import pygame_gui
from pygame import Rect
from pygame_gui.elements import UIButton, UIDropDownMenu, UISelectionList

from src.control import runs
from src.control.charts import draw_chart
from src.control.jobs import JobManager
from src.control.runs import LIVE, STATUS_COLORS, RunData, RunRow
from src.render import theme
from src.utils.ui import draw_text, get_font

LIST_WIDTH = 400
PAD = 14
ROW = 30
GAP = 8
MARGIN = 16
REFRESH = 1.0  # seconds between reads of the run folders
MENU_WIDTH = 190  # the second chart's picker
BUTTONS = (  # (name, width)
    ("Stop", 84),
    ("Pause", 84),
    ("Resume", 84),
    ("Resume training", 150),
    ("Watch best replay", 164),
)
KIND_TITLES = {
    runs.TRAINING: "TRAINING RUN",
    runs.IMITATION: "IMITATION RUN",
    runs.EPISODES: "EPISODE RUN",
}


class RunsTab:
    def __init__(
        self,
        gui,
        area: Rect,
        jobs: JobManager,
        run_action: Callable[[str, dict], object],
        runs_dir: Path | None = None,
        agents_dir: Path | None = None,
    ) -> None:
        """`run_action(name, values)` runs a Commands tab action and
        returns its job (or None).
        """
        self.gui = gui
        self.jobs = jobs
        self.run_action = run_action
        self.runs_dir = runs_dir or runs.RUNS_DIR
        self.agents_dir = agents_dir
        self.list_box = Rect(area.x, area.y, LIST_WIDTH, area.h)
        self.detail = Rect(
            self.list_box.right + MARGIN,
            area.y,
            area.right - self.list_box.right - MARGIN,
            area.h,
        )
        d = self.detail
        self.buttons_y = d.bottom - PAD - ROW
        charts_top = d.y + 112
        height = (self.buttons_y - 14 - charts_top - 12) // 2
        self.main_rect = Rect(d.x + PAD, charts_top, d.w - 2 * PAD, height)
        self.second_rect = Rect(
            d.x + PAD, self.main_rect.bottom + 12, d.w - 2 * PAD, height
        )

        self.rows: list[RunRow] = []
        self._lines: list[str] | None = None
        self._by_line: dict[str, str] = {}
        self._configs: dict = {}  # never change: read once
        self.selected: str | None = None  # a run folder's name
        self.data: RunData | None = None
        self.choice: dict[str, str] = {}  # the second chart, per kind
        self.menu: UIDropDownMenu | None = None
        self.message: tuple[str, tuple] | None = None
        self._refreshed = 0.0
        self.visible = True

        box = self.list_box
        self.run_list = UISelectionList(
            Rect(box.x + PAD, box.y + 40, box.w - 2 * PAD, box.h - 40 - PAD),
            [],
            gui,
            object_id="#runs",
        )
        self.buttons: dict[str, UIButton] = {}
        x = d.x + PAD
        for name, width in BUTTONS:
            self.buttons[name] = UIButton(
                Rect(x, self.buttons_y, width, ROW), name, gui
            )
            x += width + GAP
            if name == "Resume":
                x += 2 * GAP  # the job's controls, then the run's
        self.message_x = x + GAP
        self.refresh(force=True)

    # Showing and hiding with the tab

    def widgets(self) -> list:
        return [self.run_list, *self.buttons.values()] + (
            [self.menu] if self.menu else []
        )

    def show(self) -> None:
        self.visible = True
        for widget in self.widgets():
            widget.show()
        self.refresh(force=True)

    def hide(self) -> None:
        self.visible = False
        for widget in self.widgets():
            widget.hide()

    # Reading the runs

    def refresh(self, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self._refreshed < REFRESH:
            return
        self._refreshed = now
        self.rows = runs.scan(
            self.runs_dir, self.jobs.jobs, configs=self._configs
        )
        lines = [row.line for row in self.rows]
        if lines != self._lines:
            self._set_lines(lines)
        names = [row.name for row in self.rows]
        if self.selected not in names:
            self.select(names[0] if names else None)
        elif self.data:
            self.data.refresh()
        self._update_buttons()

    def _set_lines(self, lines: list[str]) -> None:
        """New list text, keeping the selection and the scroll place."""
        bar = getattr(self.run_list, "scroll_bar", None)
        place = bar.start_percentage if bar else 0.0
        self._lines = lines
        self._by_line = {row.line: row.name for row in self.rows}
        self.run_list.set_item_list(lines)
        self._highlight()
        bar = getattr(self.run_list, "scroll_bar", None)
        if bar and place:
            bar.set_scroll_from_start_percentage(place)
        if not self.visible:
            self.run_list.hide()

    def _highlight(self) -> None:
        """Lights the selected run's row (also when picked in code)."""
        for item, row in zip(self.run_list.item_list, self.rows):
            chosen = row.name == self.selected
            item["selected"] = chosen
            button = item["button_element"]
            if button is not None:
                button.select() if chosen else button.unselect()

    def select(self, name: str | None) -> None:
        self.selected = name
        self._highlight()
        self.message = None
        previous = self.data.kind if self.data else None
        self.data = (
            RunData(self.runs_dir / name, self.agents_dir) if name else None
        )
        kind = self.data.kind if self.data else None
        if kind != previous or self.menu is None:
            self._build_menu()
        self._update_buttons()

    def _build_menu(self) -> None:
        if self.menu:
            self.menu.kill()
            self.menu = None
        if not self.data:
            return
        options = self.data.options()
        choice = self.choice.get(self.data.kind, options[0])
        rect = self.second_rect
        self.menu = UIDropDownMenu(
            options,
            choice,
            Rect(rect.x + 6, rect.y + 4, MENU_WIDTH, 26),
            self.gui,
        )
        if not self.visible:
            self.menu.hide()

    @property
    def row(self) -> RunRow | None:
        return next((r for r in self.rows if r.name == self.selected), None)

    def _update_buttons(self) -> None:
        row = self.row
        job = row.job if row else None
        running = bool(job and job.running)
        wanted = {
            "Stop": running,
            "Pause": running and not job.paused,
            "Resume": running and job.paused,
            "Resume training": bool(row and row.resumable),
            "Watch best replay": bool(row and row.has_replays),
        }
        for name, on in wanted.items():
            button = self.buttons[name]
            if on and not button.is_enabled:
                button.enable()
            elif not on and button.is_enabled:
                button.disable()

    # Events

    def handle(self, event) -> None:
        if event.type == pygame_gui.UI_SELECTION_LIST_NEW_SELECTION:
            if event.ui_element is self.run_list:
                self.select(self._by_line.get(event.text))
        elif event.type == pygame_gui.UI_DROP_DOWN_MENU_CHANGED:
            if event.ui_element is self.menu and self.data:
                self.choice[self.data.kind] = event.text
        elif event.type == pygame_gui.UI_BUTTON_PRESSED:
            for name, button in self.buttons.items():
                if event.ui_element is button:
                    self.press(name)

    def press(self, name: str) -> None:
        row = self.row
        if not row:
            return
        if name in ("Stop", "Pause", "Resume") and row.job:
            {
                "Stop": self.jobs.stop,
                "Pause": self.jobs.pause,
                "Resume": self.jobs.resume,
            }[name](row.job)
        elif name == "Resume training":
            self._started(self.run_action("Resume training", {"Run": row.name}))
        elif name == "Watch best replay":
            self._started(
                self.run_action("Watch a run's best replay", {"Run": row.name})
            )
        self.refresh(force=True)

    def _started(self, job) -> None:
        if job:
            self.message = (f"Started job #{job.number}", theme.GOOD)

    def dropdown_open(self) -> bool:
        menu = self.menu
        return bool(
            menu and menu.current_state is menu.menu_states["expanded"]
        )

    # Drawing

    def draw(self, surface) -> None:
        for rect in (self.list_box, self.detail):
            pygame.draw.rect(surface, theme.PANEL_BORDER, rect, 1)
        _header(surface, self.list_box, f"RUNS · {len(self.rows)}")
        if not self.rows:
            draw_text(
                surface,
                "No runs yet: train an agent or run episodes.",
                (self.list_box.x + PAD, self.list_box.y + 48),
                theme.TEXT_SIZE,
                theme.TEXT_DIM,
            )
        data, row = self.data, self.row
        if not data or not row:
            return
        d = self.detail
        _header(surface, d, KIND_TITLES[data.kind])
        x, width = d.x + PAD, d.w - 2 * PAD
        draw_text(
            surface,
            _fit(row.name, width, theme.BIG_SIZE),
            (x, d.y + 34),
            theme.BIG_SIZE,
            theme.TEXT,
            bold=True,
        )
        draw_text(
            surface,
            _fit(data.description(), width, theme.TEXT_SIZE),
            (x, d.y + 62),
            theme.TEXT_SIZE,
            theme.TEXT_DIM,
        )
        self._draw_status(surface, data, row, x, d.y + 86, width)
        mouse = pygame.mouse.get_pos()
        if self.dropdown_open():
            mouse = None  # the open list covers the chart
        draw_chart(surface, self.main_rect, data.main_chart(), mouse)
        option = self.choice.get(data.kind, data.options()[0])
        draw_chart(
            surface,
            self.second_rect,
            data.second_chart(option),
            mouse,
            title=False,
        )
        if self.message:
            text, color = self.message
            draw_text(
                surface,
                text,
                (self.message_x, self.buttons_y + ROW // 2),
                theme.TEXT_SIZE,
                color,
                anchor="midleft",
            )

    def _draw_status(self, surface, data, row, x, y, width) -> None:
        """RUNNING ▰▰▰▱▱ 1,340,000 / 2,000,000 decisions · 3 min left."""
        color = STATUS_COLORS[row.status]
        rect = draw_text(
            surface,
            row.status.upper(),
            (x, y),
            theme.TEXT_SIZE,
            color,
            bold=True,
        )
        done, total, unit = data.counts()
        right = rect.right + 12
        if total:
            bar = Rect(right, y + 5, 160, 8)
            pygame.draw.rect(surface, theme.BAR_EMPTY, bar)
            share = 1.0 if row.status == runs.DONE else min(done / total, 1)
            filled = Rect(bar.x, bar.y, round(bar.w * share), bar.h)
            pygame.draw.rect(surface, color, filled)
            text = f"{done:,.0f} / {total:,.0f} {unit}"
            left = data.seconds_left() if row.status in LIVE else None
            if left is not None:
                text += f" · {_duration(left)} left"
            elif data.summary.get("seconds"):
                text += f" · took {_duration(data.summary['seconds'])}"
            rect = draw_text(
                surface,
                text,
                (bar.right + 12, y),
                theme.TEXT_SIZE,
                theme.TEXT,
            )
            right = rect.right
        notes = data.notes()
        if notes:
            draw_text(
                surface,
                _fit(notes, x + width - right - 16, theme.TEXT_SIZE),
                (x + width, y),
                theme.TEXT_SIZE,
                theme.WARN if data.best else theme.TEXT_DIM,
                anchor="topright",
            )


def _header(surface, rect: Rect, text: str) -> None:
    draw_text(
        surface,
        text,
        (rect.x + PAD, rect.y + 12),
        theme.HEADER_SIZE,
        theme.ACCENT,
        bold=True,
    )


def _fit(text: str, width: float, size: int) -> str:
    font = get_font(size, size == theme.BIG_SIZE)
    if font.size(text)[0] <= width:
        return text
    while text and font.size(text + "…")[0] > width:
        text = text[:-1]
    return text + "…"


def _duration(seconds: float) -> str:
    """3 min, 45 s, 1 h 05 min."""
    seconds = max(seconds, 0)
    if seconds < 60:
        return f"{seconds:.0f} s"
    minutes = round(seconds / 60)
    if minutes < 60:
        return f"{minutes} min"
    return f"{minutes // 60} h {minutes % 60:02d} min"
