"""The control center's Runs tab (roadmap step 6b1): every run, and the
selected run's progress and live learning curves. Step 6b3 adds clicking
a checkpoint's suite dot (watch it drive, or branch from it), comparing
with another run of the same kind, and deleting a run into the trash.

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

from src.control import help, runs
from src.control.charts import DOTS, LINE, Plot, Series, compact, draw_chart
from src.control.jobs import JobManager
from src.control.maps_data import watch_stage
from src.control.runs import LIVE, STARTING, STATUS_COLORS, RunData, RunRow
from src.control.text import fit, header, wrap
from src.control.tooltips import Tooltips
from src.render import theme
from src.render.spinner import draw_spinner
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
DELETE_WIDTH = 110
COMPARE_WIDTH = 300
NO_COMPARE = "(none)"
COMPARE_COLORS = ((205, 150, 90), (150, 150, 160))  # muted, apart
HIT = 9  # px: how close a click must be to a suite dot
POPOVER = (250, 96)  # the smallest size; it widens to fit its text
POPOVER_PAD = 12
POPOVER_BUTTONS = (("watch", "Watch it drive"), ("branch", "Branch from it"))
CHART_TOPICS = {  # the main chart's help
    runs.TRAINING: "chart:score",
    runs.IMITATION: "chart:accuracy",
    runs.EPISODES: "chart:episodes",
}
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
        branch: Callable[[str], None] = lambda start: None,
    ) -> None:
        """`run_action(name, values)` runs a Commands tab action and
        returns its job (or None). `branch("agent@checkpoint")` opens the
        Training tab to branch a new agent from it.
        """
        self.gui = gui
        self.jobs = jobs
        self.run_action = run_action
        self.branch = branch
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
        # A chain the tab follows: it selects each run the chain starts,
        # until you pick another run yourself.
        self.follow = None
        self.chains: list = []  # the window's chains (their runs starting)
        self.data: RunData | None = None
        self.choice: dict[str, str] = {}  # the second chart, per kind
        self.menu: UIDropDownMenu | None = None
        self.message: tuple[str, tuple] | None = None
        self._refreshed = 0.0
        self.visible = True
        self.compare: RunData | None = None  # another run, drawn muted
        self.compare_menu: UIDropDownMenu | None = None
        self._compare_options: list | None = None
        # The suite dot you clicked: (checkpoint, decisions, score), and
        # its box's buttons (drawn by hand, acting on release).
        self.picked: tuple[str, float, float] | None = None
        self.popover_buttons: dict[str, Rect] = {}
        self._pressed: str | None = None
        self._plot: Plot | None = None  # where the score chart drew
        self.tips = Tooltips()  # the window shares its own

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
        # Deleting stays apart from the rest, at the right.
        self.buttons["Delete run"] = UIButton(
            Rect(
                d.right - PAD - DELETE_WIDTH,
                self.buttons_y,
                DELETE_WIDTH,
                ROW,
            ),
            "Delete run",
            gui,
        )
        self.refresh(force=True)

    # Showing and hiding with the tab

    def widgets(self) -> list:
        menus = [m for m in (self.menu, self.compare_menu) if m]
        return [self.run_list, *self.buttons.values(), *menus]

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

    def on_data(self, kinds: set[str]) -> None:
        """Runs or agents changed elsewhere (7c7): read them again."""
        if kinds & {"runs", "agents", "checkpoints", "suites"}:
            self.refresh(force=True)

    def refresh(self, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self._refreshed < REFRESH:
            return
        self._refreshed = now
        self.rows = runs.scan(
            self.runs_dir,
            self.jobs.jobs,
            configs=self._configs,
            chains=self.chains,
        )
        lines = [row.line for row in self.rows]
        if lines != self._lines:
            self._set_lines(lines)
        names = [row.name for row in self.rows]
        followed = self._followed()
        if followed in names and followed != self.selected:
            self.select(followed)
        elif self.selected not in names:
            self.select(names[0] if names else None)
        elif self.data:
            self.data.refresh()
        if self.compare:
            if self.compare.folder.name in names:
                self.compare.refresh()
            else:  # deleted meanwhile
                self.compare = None
        self._build_compare_menu()
        self._update_buttons()

    def _followed(self) -> str | None:
        """The row of the chain the tab follows: its newest run, or the
        step still starting (no run folder yet).
        """
        chain = self.follow
        if not chain:
            return None
        job = chain.job
        if job and job.running and not job.run:
            return runs.starting_name(job)
        return chain.run

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
        self.picked = None
        previous = self.data.kind if self.data else None
        row = next((r for r in self.rows if r.name == name), None)
        starting = row is not None and row.status == STARTING
        self.data = (
            RunData(self.runs_dir / name, self.agents_dir)
            if name and not starting  # a starting run has no folder yet
            else None
        )
        kind = self.data.kind if self.data else None
        if kind != previous or self.menu is None:
            self._build_menu()
        if self.compare and (
            self.compare.kind != kind or self.compare.folder.name == name
        ):
            self.compare = None
        self._compare_options = None  # rebuilt for this run
        self._build_compare_menu()
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

    def _build_compare_menu(self) -> None:
        """Runs of the same kind to compare with. Rebuilt when they change,
        but never while its list is open.
        """
        if not self.data:
            options = None
        else:
            options = [NO_COMPARE] + [
                (fit(r.line, COMPARE_WIDTH - 40), r.name)
                for r in self.rows
                if r.kind == self.data.kind
                and r.name != self.selected
                and r.status != STARTING
            ]
        if options is None and self.compare_menu:  # nothing to compare
            self.compare_menu.kill()
            self.compare_menu = None
        if options == self._compare_options or _expanded(self.compare_menu):
            return
        self._compare_options = options
        if self.compare_menu:
            self.compare_menu.kill()
            self.compare_menu = None
        if not options:
            return
        chosen = self.compare.folder.name if self.compare else None
        start = next(
            (o for o in options[1:] if o[1] == chosen), NO_COMPARE
        )
        d = self.detail
        self.compare_menu = UIDropDownMenu(
            options,
            start,
            Rect(d.right - PAD - COMPARE_WIDTH, d.y + 6, COMPARE_WIDTH, 26),
            self.gui,
        )
        if len(options) == 1:
            self.compare_menu.disable()  # nothing of this kind to compare
        if not self.visible:
            self.compare_menu.hide()

    def _set_compare(self, option) -> None:
        """pygame_gui keeps a plain option as a pair too: ("(none)",
        "(none)"). So "(none)", or a run gone meanwhile, compares nothing.
        """
        name = option[1] if isinstance(option, tuple) else option
        folder = self.runs_dir / name if name else None
        if name == NO_COMPARE or not (folder / "config.json").exists():
            self.compare = None
            return
        self.compare = RunData(folder, self.agents_dir)

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
            "Delete run": bool(row and row.status not in LIVE),
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
                self.follow = None  # you picked one yourself
                self.select(self._by_line.get(event.text))
        elif event.type == pygame_gui.UI_DROP_DOWN_MENU_CHANGED:
            if event.ui_element is self.menu and self.data:
                self.choice[self.data.kind] = event.text
            elif event.ui_element is self.compare_menu:
                self._set_compare(self.compare_menu.selected_option)
        elif event.type == pygame_gui.UI_BUTTON_PRESSED:
            for name, button in self.buttons.items():
                if event.ui_element is button:
                    self.press(name)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._pressed = self._popover_button_at(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.click(event.pos)

    def click(self, pos) -> None:
        """A release: a popover button (if it was pressed there too), a
        suite dot (opens its box), or anywhere else (closes it).
        """
        pressed, self._pressed = self._pressed, None
        if self.picked and pressed:
            if self._popover_button_at(pos) == pressed:
                self._act(pressed)
            return
        if self.dropdown_open():
            return
        dot = self._dot_at(pos)
        if dot:
            self.picked = dot
        elif self.picked and not self._popover_rect().collidepoint(pos):
            self.picked = None

    def _dot_at(self, pos) -> tuple[str, float, float] | None:
        plot, data = self._plot, self.data
        if not plot or not plot.to_screen or not data:
            return None
        if data.kind != runs.TRAINING:
            return None
        if not plot.area.inflate(2 * HIT, 2 * HIT).collidepoint(pos):
            return None
        best, distance = None, HIT
        for point in data.suite_points:
            x, y = plot.to_screen(point[1], point[2])
            d = ((x - pos[0]) ** 2 + (y - pos[1]) ** 2) ** 0.5
            if d <= distance:
                best, distance = point, d
        return best

    def _popover_button_at(self, pos) -> str | None:
        if not self.picked:
            return None
        found = self.popover_buttons.items()
        return next((k for k, r in found if r.collidepoint(pos)), None)

    def _act(self, key: str) -> None:
        name = self.picked[0]
        start = f"{self.data.who}@{name}"
        self.picked = None
        if key == "watch":
            values = {"Driver": f"agent:{start}", "Stage": self._stage()}
            self._started(self.run_action("Watch a driver", values))
        else:
            self.branch(start)

    def escape(self) -> bool:
        """Esc closes the checkpoint box first. True if it did."""
        if self.picked:
            self.picked = None
            return True
        return False

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
        elif name == "Delete run":
            # It asks first (the Commands tab's action has its own box).
            self.run_action("Delete a run", {"Run": row.name})
        self.refresh(force=True)

    def _started(self, job) -> None:
        if job:
            self.message = (f"Started job #{job.number}", theme.GOOD)

    def dropdown_open(self) -> bool:
        return _expanded(self.menu) or _expanded(self.compare_menu)

    # Drawing

    def draw(self, surface) -> None:
        for rect in (self.list_box, self.detail):
            pygame.draw.rect(surface, theme.PANEL_BORDER, rect, 1)
        header(surface, self.list_box, f"RUNS · {len(self.rows)}")
        if not self.rows:
            draw_text(
                surface,
                "No runs yet: train an agent or run episodes.",
                (self.list_box.x + PAD, self.list_box.y + 48),
                theme.TEXT_SIZE,
                theme.TEXT_DIM,
            )
        data, row = self.data, self.row
        if row and row.status == STARTING:
            self._draw_starting(surface, row)
            return
        if not data or not row:
            return
        d = self.detail
        header(surface, d, KIND_TITLES[data.kind])
        x, width = d.x + PAD, d.w - 2 * PAD
        draw_text(
            surface,
            fit(row.name, width, True, theme.BIG_SIZE),
            (x, d.y + 34),
            theme.BIG_SIZE,
            theme.TEXT,
            bold=True,
        )
        draw_text(
            surface,
            fit(data.description(), width),
            (x, d.y + 62),
            theme.TEXT_SIZE,
            theme.TEXT_DIM,
        )
        self._draw_status(surface, data, row, x, d.y + 86, width)
        if self.compare_menu:
            label = draw_text(
                surface,
                "COMPARE WITH",
                (self.compare_menu.rect.x - 24, d.y + 19),
                theme.HEADER_SIZE,
                theme.TEXT_DIM,
                bold=True,
                anchor="midright",
            )
            mark = self.tips.marker(surface, label.right + 6, label.centery)
            self.tips.add(label.union(mark), help.topic("compare"))
        mouse = pygame.mouse.get_pos()
        if self.dropdown_open() or self.picked:
            mouse = None  # an open list or box covers the chart
        main = self._with_compare(
            data.main_chart(), lambda c: c.main_chart(), (LINE,)
        )
        self._plot = draw_chart(surface, self.main_rect, main, mouse)
        self._chart_help(surface, self._plot, CHART_TOPICS[data.kind])
        option = self.choice.get(data.kind, data.options()[0])
        # Skills compares the average share, not seven more lines (7d4);
        # six more term lines would be unreadable: no compare there (6e).
        styles = {runs.SKILLS_CHART: (DOTS,), runs.TERMS_CHART: ()}
        second = self._with_compare(
            data.second_chart(option),
            lambda c: c.second_chart(option),
            styles.get(option, (LINE, DOTS)),
        )
        plot = draw_chart(
            surface,
            self.second_rect,
            second,
            mouse,
            title=False,
            reserved=MENU_WIDTH + 22,
        )
        if self.menu:
            menu = self.menu.rect
            mark = self.tips.marker(surface, menu.right + 8, menu.centery)
            self.tips.add(menu.union(mark), help.topic(f"chart:{option}"))
        self._chart_help(surface, plot, None)
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

    def _chart_help(self, surface, plot: Plot, title_topic) -> None:
        """The chart title's marker and tooltip, and the legend's."""
        if title_topic and plot.title.w:
            mark = self.tips.marker(
                surface, plot.title.right + 6, plot.title.centery
            )
            self.tips.add(plot.title.union(mark), help.topic(title_topic))
        for rect, label in plot.legend:
            key = label.split(" ")[0]  # "average share", "best d1700k"
            skill = label.replace(" (trained here)", "")
            text = (
                help.topic(f"legend:{key}")
                or help.topic(f"skill:{skill}")
                or help.TERMS.get(label, ("", ""))[1]  # a reward term (6e)
            )
            if label.endswith("(trained here)"):
                text += (
                    " Trained here: this run's map is this skill's test map, "
                    "so it measures memory too."
                )
            self.tips.add(rect, text)

    def draw_after(self, surface) -> None:
        """After the GUI: the checkpoint box, on top of everything."""
        if self.picked and self._plot and self._plot.to_screen and self.data:
            self._draw_popover(surface)

    def _with_compare(self, chart, of, styles):
        """`chart` plus the compared run's series of `styles`, muted and
        tagged with that run's agent and time.
        """
        other = self.compare
        if not other:
            return chart
        clock = (other.folder.name.split("_") + ["", ""])[1]
        tag = f"{other.who} {clock[:2]}:{clock[2:4]}"  # rookie 00:33
        extra = [s for s in of(other).series if s.style in styles]
        for series, color in zip(extra, COMPARE_COLORS):
            label = tag if len(extra) == 1 else f"{tag} {series.label}"
            chart.series.append(
                Series(label, series.points, color, series.style)
            )
        return chart

    def _popover_rect(self) -> Rect:
        if not (self.picked and self._plot and self._plot.to_screen):
            return Rect(0, 0, 0, 0)
        x, y = self._plot.to_screen(self.picked[1], self.picked[2])
        title, detail = self._popover_texts()
        needed = max(
            get_font(theme.TEXT_SIZE, True).size(title)[0],
            get_font(theme.TEXT_SIZE).size(detail)[0],
        )
        width = min(
            max(POPOVER[0], needed + 2 * POPOVER_PAD),
            self.main_rect.w - 16,  # a longer name is cut with "…"
        )
        rect = Rect(0, 0, width, POPOVER[1])
        rect.midbottom = (int(x), int(y) - 14)  # above the dot
        if rect.top < self.main_rect.y + 4:
            rect.midtop = (int(x), int(y) + 14)  # no room: below it
        rect.clamp_ip(self.main_rect.inflate(-8, -8))
        return rect

    def _stage(self) -> str:
        """Where to watch a checkpoint: the stage this run trained on."""
        return watch_stage((self.data.config.get("stage") or {}).get("name"))

    def _popover_texts(self) -> tuple[str, str]:
        name, decisions, score = self.picked
        share = self.data.shares.get(name)
        detail = f"score {score:,.0f} · "
        if share is not None:
            detail += f"share {share:.2f} · "
        return (
            f"{self.data.who}@{name}",
            detail + f"{compact(decisions)} decisions",
        )

    def _draw_popover(self, surface) -> None:
        name, decisions, score = self.picked
        title, detail = self._popover_texts()
        x, y = self._plot.to_screen(decisions, score)
        pygame.draw.circle(surface, theme.TEXT, (x, y), 8, 2)  # pinned
        box = self._popover_rect()
        pygame.draw.rect(surface, theme.BACKGROUND, box)
        pygame.draw.rect(surface, theme.ACCENT, box, 1)
        room = box.w - 2 * POPOVER_PAD
        draw_text(
            surface,
            fit(title, room, True),
            (box.x + POPOVER_PAD, box.y + 10),
            theme.TEXT_SIZE,
            theme.TEXT,
            bold=True,
        )
        draw_text(
            surface,
            fit(detail, room),
            (box.x + POPOVER_PAD, box.y + 32),
            theme.TEXT_SIZE,
            theme.TEXT_DIM,
        )
        bx = box.x + POPOVER_PAD
        width = (room - GAP) // 2
        for key, label in POPOVER_BUTTONS:
            rect = Rect(bx, box.bottom - 12 - 28, width, 28)
            lit = key == self._pressed
            fill = (20, 60, 95) if lit else (24, 25, 30)
            pygame.draw.rect(surface, fill, rect)
            pygame.draw.rect(surface, theme.PANEL_BORDER, rect, 1)
            draw_text(
                surface,
                label,
                rect.center,
                theme.TEXT_SIZE,
                theme.TEXT,
                anchor="center",
            )
            self.popover_buttons[key] = rect
            if key == "watch":
                self.tips.add(rect, f"Watch it drive on {self._stage()}.")
            bx += width + GAP

    def _draw_starting(self, surface, row: RunRow) -> None:
        """A run still getting ready (no folder yet): what it's doing, for
        how long, and what the plan does next, with a spinner.
        """
        d = self.detail
        header(surface, d, "STARTING")
        x, width = d.x + PAD, d.w - 2 * PAD
        job = row.job
        draw_text(
            surface,
            fit(job.label, width, True, theme.BIG_SIZE),
            (x, d.y + 34),
            theme.BIG_SIZE,
            theme.TEXT,
            bold=True,
        )
        center = (d.centerx, d.y + 170)
        draw_spinner(surface, center, shade=False)
        lines = [
            (_doing(job), theme.TEXT),
            (f"{_duration(job.seconds)} so far", theme.TEXT_DIM),
        ]
        chain = next((c for c in self.chains if job in c.jobs), None)
        if chain:
            for step in chain.steps[len(chain.jobs) :]:
                lines.append((f"Then: {step.text}", theme.TEXT_DIM))
        lines.append(
            ("Its charts appear once the run starts.", theme.TEXT_DIM)
        )
        y = center[1] + 52
        for text, color in lines:
            for part in wrap(text, width):
                draw_text(
                    surface,
                    part,
                    (d.centerx, y),
                    theme.TEXT_SIZE,
                    color,
                    anchor="midtop",
                )
                y += 22
            y += 4

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
        self.tips.add(rect, help.topic(f"status:{row.status}"))
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
                fit(notes, x + width - right - 16),
                (x + width, y),
                theme.TEXT_SIZE,
                theme.WARN if data.best else theme.TEXT_DIM,
                anchor="topright",
            )


def _doing(job) -> str:
    """The job's latest output line: what it's doing right now."""
    for line in reversed(job.log):
        line = line.strip()
        if line and not line.startswith("(exited"):
            return line
    return "Starting Python…"


def _expanded(menu) -> bool:
    return bool(menu and menu.current_state is menu.menu_states["expanded"])


def _duration(seconds: float) -> str:
    """3 min, 45 s, 1 h 05 min."""
    seconds = max(seconds, 0)
    if seconds < 60:
        return f"{seconds:.0f} s"
    minutes = round(seconds / 60)
    if minutes < 60:
        return f"{minutes} min"
    return f"{minutes // 60} h {minutes % 60:02d} min"
