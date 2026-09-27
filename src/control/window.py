"""The control center window (roadmap step 6): every action, grouped by
the natural steps (actions.py), the jobs running in the background, and
their live output (the Commands tab, 6a), one form to train an agent
(the Training tab, 6b2, training_tab.py), and every run with its live
learning curves (the Runs tab, 6b1, runs_tab.py).

    make control

It never runs anything itself: each action is its own process (see
jobs.py), started with the same `app.py` command you'd type.
"""

import html
import time
from pathlib import Path

import pygame
import pygame_gui
from pygame import Rect
from pygame_gui.elements import (
    UIButton,
    UIDropDownMenu,
    UISelectionList,
    UITextBox,
    UITextEntryLine,
)

from src.control.actions import ACTIONS, GROUPS, Action
from src.control.jobs import JobManager
from src.control.chains import Chain
from src.control.runs_tab import RunsTab
from src.control.stats import CAUTION, DANGER, SystemStats
from src.control.text import fit, header, wrap
from src.control.training_plan import Plan
from src.control.training_tab import TrainingTab
from src.control.vitals import VitalsLog
from src.render import theme
from src.utils.ui import draw_text, get_font

SIZE = (1280, 820)
MARGIN = 16
PAD = 14
ROW = 30  # a row of widgets
GAP = 8  # between rows
LABEL = 124  # the width of a field's label
REFRESH = 0.5  # seconds between job list refreshes
CONSOLE_HEIGHT = 288  # about 35 % of the window
SCROLL_STEP = 40  # px per mouse wheel notch
PREVIEW_LINES = 4  # of the command, beside Run
TAB_HEIGHT = 36
STATS_HEIGHT = 32  # the machine's vital signs, above the tabs
TABS = (  # (name, the step it arrives in: None if it's here)
    ("Commands", None),
    ("Training", None),
    ("Runs", None),
    ("Agents", "6c"),
    ("Files", "6d"),
)
LIST_BG = (8, 8, 10)  # an open dropdown's list, darker than the fields
CONSOLE_FONT = "menlo"  # monospace, like a terminal: tables line up
ITEM = {  # list and dropdown rows: left-aligned, with room around the text
    "text_horiz_alignment": "left",
    "text_horiz_alignment_padding": "10",
}
# pygame_gui only uses a font set on each element type, not the defaults.
ELEMENTS = (
    "button",
    "label",
    "text_entry_line",
    "text_box",
    "drop_down_menu",
    "selection_list.@selection_list_item",
    "window",
    "confirmation_dialog",
)


def _hex(color) -> str:
    return "#{:02x}{:02x}{:02x}".format(*color)


def _font(family: str) -> dict:
    path = pygame.font.match_font(family)
    return {
        "name": family,
        "size": str(theme.TEXT_SIZE),
        "regular_path": path,
        "bold_path": path,
    }


def gui_theme() -> dict:
    """pygame_gui's look, from the game window's theme: dark flat boxes,
    gray borders, the accent color, and the same font. The console and
    the job list are monospace, so their columns line up.
    """
    look = {
        "defaults": {
            "colours": {
                "normal_bg": _hex((24, 25, 30)),
                "hovered_bg": _hex((36, 38, 46)),
                "disabled_bg": _hex(theme.BACKGROUND),
                "selected_bg": _hex((20, 60, 95)),
                "active_bg": _hex((20, 60, 95)),
                "dark_bg": _hex(theme.BACKGROUND),
                "normal_text": _hex(theme.TEXT),
                "hovered_text": _hex(theme.TEXT),
                "selected_text": _hex(theme.TEXT),
                "active_text": _hex(theme.TEXT),
                "disabled_text": _hex(theme.TEXT_DIM),
                "normal_border": _hex(theme.PANEL_BORDER),
                "hovered_border": _hex(theme.ACCENT),
                "selected_border": _hex(theme.ACCENT),
                "active_border": _hex(theme.ACCENT),
                "disabled_border": _hex(theme.PANEL_BORDER),
                "text_cursor": _hex(theme.ACCENT),
            },
            "misc": {
                "shape": "rectangle",
                "border_width": "1",
                "shadow_width": "0",
            },
        }
    }
    for element in ELEMENTS:
        look[element] = {"font": _font(theme.FONT_FAMILY)}
    look["text_entry_line"]["misc"] = {"padding": "10,4"}  # like dropdowns
    look["selection_list"] = {"misc": {"list_item_height": "26"}}
    look["selection_list.@selection_list_item"]["misc"] = ITEM
    look["drop_down_menu.#selected_option"] = {
        "font": _font(theme.FONT_FAMILY),
        "misc": ITEM,
    }
    # An open dropdown's list: darker than the fields behind it, with an
    # accent border, so it clearly sits on top.
    look["drop_down_menu.#drop_down_options_list"] = {
        "colours": {
            "dark_bg": _hex(LIST_BG),
            "normal_border": _hex(theme.ACCENT),
        },
        "misc": {"list_item_height": "26", "border_width": "1"},
    }
    look["drop_down_menu.#drop_down_options_list.@selection_list_item"] = {
        "font": _font(theme.FONT_FAMILY),
        "colours": {
            "normal_bg": _hex(LIST_BG),
            "hovered_bg": _hex((32, 34, 42)),
            "selected_bg": _hex((20, 60, 95)),
        },
        "misc": ITEM,
    }
    look["#console"] = {"font": _font(CONSOLE_FONT)}
    for list_id in ("#jobs", "#runs"):
        look[f"{list_id}.@selection_list_item"] = {
            "font": _font(CONSOLE_FONT),
            "misc": ITEM,
        }
    return look


class ControlCenter:
    def __init__(
        self,
        jobs: JobManager | None = None,
        runs_dir: Path | None = None,
        agents_dir: Path | None = None,
        logs_dir: Path | None = None,
    ) -> None:
        """`logs_dir`: where the vitals log goes (app.py passes logs/).
        None keeps no log, for tests.
        """
        pygame.init()
        pygame.display.set_caption("Maze Car · Control Center")
        self.screen = pygame.display.set_mode(SIZE)
        self.gui = pygame_gui.UIManager(SIZE, gui_theme())
        self.vitals = VitalsLog(logs_dir) if logs_dir else None
        self.jobs = jobs or JobManager()
        if self.vitals:
            self.jobs.on_event = self.vitals.note
        self.running = True
        self.confirm_quit = False  # the quit box is open
        self.quit_buttons: dict[str, Rect] = {}  # its buttons, when drawn
        self.quit_pressed: str | None = None  # the button the mouse is on
        self.tab = "Commands"
        self.stats = SystemStats()
        if self.vitals:
            self.vitals.note("open", self.stats.sample([], force=True))
        self.message: tuple[str, tuple] | None = None  # next to Run
        self.selected_job = None
        self._refreshed = 0.0
        self._log_seen = -1
        self._rows = None

        # The boxes: tabs on top, then commands and jobs, then console.
        width = SIZE[0] - 2 * MARGIN
        self.stats_bar = Rect(MARGIN, MARGIN, width, STATS_HEIGHT)
        self.tab_bar = Rect(
            MARGIN, self.stats_bar.bottom + GAP, width, TAB_HEIGHT
        )
        top = self.tab_bar.bottom + MARGIN
        # The console: about 35 % of the window's height.
        self.console = Rect(
            MARGIN, SIZE[1] - MARGIN - CONSOLE_HEIGHT, width, CONSOLE_HEIGHT
        )
        height = self.console.y - MARGIN - top
        self.jobs_box = Rect(SIZE[0] - MARGIN - 360, top, 360, height)
        self.commands_box = Rect(
            MARGIN, top, self.jobs_box.x - 2 * MARGIN, height
        )
        self.tab_rects = self._tab_rects()
        self._build()
        # The Runs tab: the full height, for its charts.
        self.runs_tab = RunsTab(
            self.gui,
            Rect(MARGIN, top, width, SIZE[1] - MARGIN - top),
            self.jobs,
            self.run_named,
            runs_dir=runs_dir,
            agents_dir=agents_dir,
        )
        self.runs_tab.hide()
        self.chains: list[Chain] = []  # the Training tab's plans
        self.training_tab = TrainingTab(
            self.gui,
            Rect(MARGIN, top, width, SIZE[1] - MARGIN - top),
            self.jobs,
            self.start_plan,
            on_battery=self._on_battery,
            busy=self._chain_agents,
            runs_dir=runs_dir,
        )
        self.training_tab.hide()

    # Widgets

    def _build(self) -> None:
        gui = self.gui
        box = self.commands_box
        self.group_menu = UIDropDownMenu(
            list(GROUPS),
            GROUPS[0],
            Rect(box.x + PAD, box.y + 40, 200, ROW),
            gui,
        )
        self.action_list = UISelectionList(
            Rect(box.x + PAD, box.y + 40 + ROW + GAP, 200, box.h - 94),
            [],
            gui,
        )
        self.detail_x = box.x + PAD + 200 + 2 * PAD
        self.detail_w = box.right - PAD - self.detail_x
        self.field_widgets: dict[str, object] = {}
        self.run_button = None
        self.selected: Action | None = None
        self._show_group(GROUPS[0])

        jobs = self.jobs_box
        self.job_list = UISelectionList(
            Rect(jobs.x + PAD, jobs.y + 40, jobs.w - 2 * PAD, jobs.h - 94),
            [],
            gui,
            object_id="#jobs",
        )
        width = (jobs.w - 2 * PAD - 3 * GAP) // 4
        self.job_buttons = {}
        for i, name in enumerate(("Stop", "Pause", "Resume", "Clear")):
            self.job_buttons[name] = UIButton(
                Rect(
                    jobs.x + PAD + i * (width + GAP),
                    jobs.bottom - PAD - ROW,
                    width,
                    ROW,
                ),
                name,
                gui,
            )

        console = self.console
        self.log_box = UITextBox(
            "",
            Rect(
                console.x + PAD,
                console.y + 36,
                console.w - 2 * PAD,
                console.h - 36 - PAD,
            ),
            gui,
            object_id="#console",
        )

    def _show_group(self, group: str) -> None:
        names = [a.name for a in ACTIONS if a.group == group]
        self.action_list.set_item_list(names)
        self._select(names[0] if names else None)

    def _select(self, name: str | None) -> None:
        for widget in self.field_widgets.values():
            widget.kill()
        self.field_widgets = {}
        if self.run_button:
            self.run_button.kill()
            self.run_button = None
        self.message = None
        self.selected = next((a for a in ACTIONS if a.name == name), None)
        if not self.selected:
            return
        # The title and description stay put. Below them, the fields, Run,
        # and the command scroll (the viewport) when they don't fit.
        self.description = wrap(self.selected.description, self.detail_w)
        top = self.commands_box.y + 40 + 30 + 20 * len(self.description) + 14
        self.viewport = Rect(
            self.detail_x,
            top,
            self.detail_w,
            self.commands_box.bottom - PAD - top,
        )
        self.scroll = 0
        self.offsets: dict[str, int] = {}  # widget -> y inside the content
        y = 0
        width = self.detail_w - LABEL
        for field in self.selected.fields:
            rect = Rect(self.detail_x + LABEL, top + y, width, ROW)
            options = field.options() if field.options else None
            if options:
                shown = [(fit(o, width - 40), o) for o in options]
                start = next(
                    (s for s in shown if s[1] == field.default), shown[0]
                )
                widget = UIDropDownMenu(shown, start, rect, self.gui)
            elif field.options:  # nothing to pick yet
                widget = UIDropDownMenu(
                    ["(none yet)"], "(none yet)", rect, self.gui
                )
                widget.disable()
            else:
                widget = UITextEntryLine(rect, self.gui)
                widget.set_text(field.default)
            self.field_widgets[field.name] = widget
            self.offsets[field.name] = y
            y += ROW + GAP
        # Run under the fields, the command it runs beside it, and
        # messages under Run.
        self.run_offset = y + 10
        self.run_button = UIButton(
            Rect(self.detail_x, top + self.run_offset, 120, ROW),
            "Run",
            self.gui,
        )
        self.content_height = self.run_offset + 18 * PREVIEW_LINES + 34
        self._place()

    @property
    def max_scroll(self) -> int:
        return max(self.content_height - self.viewport.h, 0)

    def scroll_by(self, pixels: int) -> None:
        self.scroll = min(max(self.scroll + pixels, 0), self.max_scroll)
        self._place()

    def _place(self) -> None:
        """Moves the widgets to the scroll position. A widget that isn't
        fully inside the viewport hides.
        """
        view = self.viewport
        placed = [
            (widget, self.offsets[name])
            for name, widget in self.field_widgets.items()
        ] + [(self.run_button, self.run_offset)]
        for widget, offset in placed:
            y = view.y + offset - self.scroll
            widget.set_position((widget.rect.x, y))
            if view.top <= y and y + ROW <= view.bottom:
                widget.show()
            else:
                widget.hide()

    @property
    def run_y(self) -> int:
        return self.viewport.y + self.run_offset - self.scroll

    def values(self) -> dict[str, str]:
        found = {}
        for name, widget in self.field_widgets.items():
            if isinstance(widget, UIDropDownMenu):
                option = widget.selected_option
                found[name] = option[1] if isinstance(option, tuple) else ""
            else:
                found[name] = widget.get_text().strip()
        return found

    # Actions

    def run_action(self, action: Action, values: dict, label: str = ""):
        """Runs an action, unless a field it needs is empty. Returns its
        job, or None.
        """
        empty = []
        for field in action.fields:
            value = values.get(field.name, field.default).strip()
            optional = field.options is None and field.hint
            if not value and not optional:
                empty.append(field.name)
        if empty:
            self.message = (f"Needs: {', '.join(empty)}", theme.BAD)
            return None
        if not label:
            label = action.name
            if action.fields:
                label += f": {values.get(action.fields[0].name, '')}"
        return self._start(label, action.argv(values), action.opens_window)

    def run_named(self, name: str, values: dict, label: str = ""):
        """Runs the action called `name` (for the other tabs), with its
        defaults for the fields `values` leaves out.
        """
        action = next(a for a in ACTIONS if a.name == name)
        filled = {f.name: f.default for f in action.fields}
        return self.run_action(action, {**filled, **values}, label)

    def start_plan(self, plan: Plan) -> Chain | None:
        """Runs the Training tab's plan as a chain, and has the Runs tab
        follow it.
        """

        def start(step, i, n):
            label = f"{step.action}: {plan.agent} ({i + 1}/{n})"
            return self.run_named(step.action, step.values, label)

        chain = Chain(plan.steps, start, say=self.jobs.say, agent=plan.agent)
        chain.tick()
        if not chain.jobs:
            return None
        self.chains.append(chain)
        self.runs_tab.follow = chain
        self.open_tab("Runs")
        return chain

    def _chain_agents(self) -> dict[str, str]:
        """Agents a running chain here is working on."""
        return {
            chain.agent: f"a chain here, job #{chain.job.number}"
            for chain in self.chains
            if chain.active and chain.job
        }

    def _on_battery(self) -> bool:
        snap = self.stats.snapshot
        return bool(snap and snap.battery is not None and not snap.plugged)

    def _start(self, label: str, argv: list[str], window: bool):
        job = self.jobs.start(label, argv)
        self.selected_job = job
        where = "a game window opens" if window else "headless"
        self.message = (f"Started job #{job.number} ({where})", theme.GOOD)
        self._log_seen = -1
        self._refresh(force=True)
        return job

    def _job_action(self, name: str) -> None:
        if name == "Clear":
            self.jobs.clear_finished()
            if self.selected_job not in self.jobs.jobs:
                self.selected_job = None
        elif self.selected_job:
            action = {
                "Stop": self.jobs.stop,
                "Pause": self.jobs.pause,
                "Resume": self.jobs.resume,
            }[name]
            action(self.selected_job)
        self._refresh(force=True)

    def open_tab(self, name: str) -> None:
        if name == self.tab:
            return
        self.tab = name
        commands = [
            self.group_menu,
            self.action_list,
            *self.field_widgets.values(),
            *([self.run_button] if self.run_button else []),
            self.job_list,
            *self.job_buttons.values(),
            self.log_box,
        ]
        tabs = {"Runs": self.runs_tab, "Training": self.training_tab}
        for tab_name, tab in tabs.items():
            if tab_name != name:
                tab.hide()
        if name in tabs:
            for widget in commands:
                widget.hide()
            tabs[name].show()
        else:
            for widget in commands:
                widget.show()
            if self.selected:
                self._place()  # hides the fields scrolled out of view

    def ask_to_quit(self) -> None:
        self.confirm_quit = True
        self.quit_pressed = None

    def quit(self) -> None:
        self.jobs.stop_all()
        if self.vitals:
            self.vitals.note("quit")
        self.running = False

    # The loop

    def handle(self, event) -> None:
        if self.confirm_quit:  # the quit box takes every key and click
            self._handle_quit_box(event)
            return
        self.gui.process_events(event)
        if event.type == pygame.QUIT:
            self.ask_to_quit()
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.ask_to_quit()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for name, rect in self.tab_rects.items():
                if rect.collidepoint(event.pos) and _available(name):
                    self.open_tab(name)
        if self.tab == "Runs":
            self.runs_tab.handle(event)
        elif self.tab == "Training":
            self.training_tab.handle(event)
        else:
            self._handle_commands(event)

    def _handle_commands(self, event) -> None:
        if event.type == pygame_gui.UI_DROP_DOWN_MENU_CHANGED:
            if event.ui_element is self.group_menu:
                self._show_group(event.text)
        elif event.type == pygame_gui.UI_SELECTION_LIST_NEW_SELECTION:
            if event.ui_element is self.action_list:
                self._select(event.text)
            elif event.ui_element is self.job_list:
                number = int(event.text.split()[0].lstrip("#"))
                self.selected_job = next(
                    (j for j in self.jobs.jobs if j.number == number), None
                )
                self._log_seen = -1
        elif event.type == pygame_gui.UI_BUTTON_PRESSED:
            if event.ui_element is self.run_button and self.selected:
                self.run_action(self.selected, self.values())
            for name, button in self.job_buttons.items():
                if event.ui_element is button:
                    self._job_action(name)
        elif event.type == pygame.MOUSEWHEEL and self.selected:
            over = self.viewport.collidepoint(pygame.mouse.get_pos())
            if over and not self._dropdown_open():
                self.scroll_by(-event.y * SCROLL_STEP)

    def _handle_quit_box(self, event) -> None:
        """Esc (or Cancel) goes back, Enter (or Confirm) quits. Closing the
        window again while it's open quits too. A button acts like any
        button: on release, if the mouse is still on the one it pressed.
        """
        if event.type == pygame.QUIT:
            self.quit()
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.confirm_quit = False
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.quit()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.quit_pressed = self._quit_button_at(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            pressed, self.quit_pressed = self.quit_pressed, None
            if pressed is None or self._quit_button_at(event.pos) != pressed:
                return  # released somewhere else: nothing
            if pressed == "cancel":
                self.confirm_quit = False
            else:
                self.quit()

    def _quit_button_at(self, pos) -> str | None:
        buttons = self.quit_buttons.items()
        return next((k for k, r in buttons if r.collidepoint(pos)), None)

    def _refresh(self, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self._refreshed < REFRESH:
            return
        self._refreshed = now
        for chain in self.chains:
            chain.tick()  # the next step, once the last one succeeded
        if self.vitals:
            pids = [job.process.pid for job in self.jobs.running]
            self.vitals.record(self.stats.sample(pids), now)
        rows = [
            f"#{j.number}  {j.status:<8} {_clock(j.seconds):>5}  {j.label}"
            for j in reversed(self.jobs.jobs)
        ]
        if rows != self._rows:
            self._rows = rows
            self.job_list.set_item_list(rows)
        job = self.selected_job or (
            self.jobs.jobs[-1] if self.jobs.jobs else None
        )
        if job and job.lines_seen != self._log_seen:
            self._log_seen = job.lines_seen
            text = "<br>".join(html.escape(line) for line in job.log)
            self.log_box.set_text(text)
            bar = getattr(self.log_box, "scroll_bar", None)
            if bar:
                bar.set_scroll_from_start_percentage(1.0)
        self._log_job = job

    def draw(self) -> None:
        self.screen.fill(theme.BACKGROUND)
        for rect in (self.stats_bar, self.tab_bar):
            pygame.draw.rect(self.screen, theme.PANEL_BORDER, rect, 1)
        self._draw_stats()
        self._draw_tabs()
        if self.tab == "Runs":
            self.runs_tab.draw(self.screen)
            self.gui.draw_ui(self.screen)
        elif self.tab == "Training":
            self.training_tab.draw(self.screen)
            self.gui.draw_ui(self.screen)
            self.training_tab.draw_after(self.screen)
        else:
            self._draw_commands()
        if self.confirm_quit:
            self._draw_quit_box()

    def _draw_commands(self) -> None:
        for rect in (self.commands_box, self.jobs_box, self.console):
            pygame.draw.rect(self.screen, theme.PANEL_BORDER, rect, 1)
        header(self.screen, self.commands_box, "COMMANDS")
        header(self.screen, self.jobs_box, "JOBS")
        job = getattr(self, "_log_job", None)
        title = "CONSOLE"
        if job:
            title = fit(
                f"CONSOLE · #{job.number} {job.label}",
                self.console.w - 2 * PAD,
                bold=True,
            )
        header(self.screen, self.console, title)
        if self.selected:
            self._draw_detail()
        self.gui.draw_ui(self.screen)
        if self.selected:
            self._draw_hints()

    def _dropdown_open(self) -> bool:
        menus = [self.group_menu, *self.field_widgets.values()]
        return any(
            isinstance(menu, UIDropDownMenu)
            and menu.current_state is menu.menu_states["expanded"]
            for menu in menus
        )

    # The machine's vital signs

    def _draw_stats(self) -> None:
        pids = [job.process.pid for job in self.jobs.running]
        snap = self.stats.sample(pids)
        levels = snap.levels()
        bar = self.stats_bar
        x, y = bar.x + PAD, bar.centery
        x = _stat_gauge(
            self.screen,
            "CPU",
            snap.cpu / 100,
            f"{snap.cpu:.0f}%",
            f"jobs {snap.jobs_cpu:.0f}%",
            levels["cpu"],
            x,
            y,
        )
        x = _stat_gauge(
            self.screen,
            "MEMORY",
            snap.memory_percent / 100,
            f"{snap.memory_used:.1f} / {snap.memory_total:.0f} GB",
            f"jobs {snap.jobs_memory:.1f} GB",
            levels["memory"],
            x,
            y,
        )
        if snap.battery is not None:
            where = "on power" if snap.plugged else "ON BATTERY"
            x = _stat_gauge(
                self.screen,
                "BATTERY",
                snap.battery / 100,
                f"{snap.battery:.0f}%",
                where,
                levels["battery"],
                x,
                y,
            )
        x = _stat_text(
            self.screen,
            "DISK",
            f"{snap.disk_free:.0f} GB free",
            levels["disk"],
            x,
            y,
        )
        _stat_text(self.screen, "JOBS", f"{snap.jobs} running", 0, x, y)

    # Tabs and the quit box

    def _tab_rects(self) -> dict[str, Rect]:
        """Each tab's area in the tab bar, after the title."""
        title = get_font(theme.HEADER_SIZE, True).size("CONTROL CENTER")[0]
        x = self.tab_bar.x + PAD + title + 28
        rects = {}
        font = get_font(theme.TEXT_SIZE, True)
        for name, step in TABS:
            label = _tab_label(name, step)
            width = font.size(label)[0] + 2 * 16
            rects[name] = Rect(x, self.tab_bar.y + 5, width, TAB_HEIGHT - 10)
            x += width + GAP
        return rects

    def _draw_tabs(self) -> None:
        bar = self.tab_bar
        draw_text(
            self.screen,
            "CONTROL CENTER",
            (bar.x + PAD, bar.centery),
            theme.HEADER_SIZE,
            theme.ACCENT,
            bold=True,
            anchor="midleft",
        )
        for name, step in TABS:
            rect = self.tab_rects[name]
            active = name == self.tab
            if active:  # the open tab: a lit box
                pygame.draw.rect(self.screen, (20, 60, 95), rect)
                pygame.draw.rect(self.screen, theme.ACCENT, rect, 1)
            elif step is None:
                pygame.draw.rect(self.screen, theme.PANEL_BORDER, rect, 1)
            color = theme.TEXT if active else (
                theme.TEXT_DIM if step else theme.TEXT
            )
            draw_text(
                self.screen,
                _tab_label(name, step),
                rect.center,
                theme.TEXT_SIZE,
                color,
                bold=active,
                anchor="center",
            )

    def _draw_quit_box(self) -> None:
        """Like the game window's: dims the window, then asks."""
        shade = pygame.Surface(SIZE, pygame.SRCALPHA)
        shade.fill((*theme.BACKGROUND, 170))
        self.screen.blit(shade, (0, 0))
        running = len(self.jobs.running)
        lines = [("Quit the control center?", theme.TEXT)]
        if running:
            lines.append(
                (
                    f"{running} running job{'s' if running > 1 else ''} will "
                    "be stopped (training keeps its resume state).",
                    theme.TEXT_DIM,
                )
            )
        font = get_font(theme.TEXT_SIZE)
        bold = get_font(theme.TEXT_SIZE, True)
        labels = {"cancel": "Cancel (Esc)", "confirm": "Confirm (Enter)"}
        buttons = {k: bold.size(v)[0] + 2 * 18 for k, v in labels.items()}
        width = max(
            [font.size(text)[0] for text, _ in lines]
            + [sum(buttons.values()) + GAP]
        ) + 2 * 28
        box = Rect(0, 0, width, 64 + 22 * len(lines) + 20 + ROW + 24)
        box.center = (SIZE[0] // 2, SIZE[1] // 2)
        pygame.draw.rect(self.screen, theme.BACKGROUND, box)
        pygame.draw.rect(self.screen, theme.PANEL_BORDER, box, 1)
        y = box.y + 24
        draw_text(
            self.screen,
            "QUIT?",
            (box.centerx, y),
            theme.BIG_SIZE,
            theme.WARN,
            bold=True,
            anchor="midtop",
        )
        y += 40
        for text, color in lines:
            draw_text(
                self.screen,
                text,
                (box.centerx, y),
                theme.TEXT_SIZE,
                color,
                anchor="midtop",
            )
            y += 22
        # The buttons, right-aligned: Cancel, then Confirm.
        x = box.right - 28
        top = box.bottom - 24 - ROW
        for key in ("confirm", "cancel"):
            rect = Rect(0, top, buttons[key], ROW)
            rect.right = x
            lit = key == "confirm"
            pygame.draw.rect(
                self.screen, (20, 60, 95) if lit else (24, 25, 30), rect
            )
            pygame.draw.rect(
                self.screen,
                theme.ACCENT if lit else theme.PANEL_BORDER,
                rect,
                1,
            )
            draw_text(
                self.screen,
                labels[key],
                rect.center,
                theme.TEXT_SIZE,
                theme.TEXT,
                bold=True,
                anchor="center",
            )
            self.quit_buttons[key] = rect
            x = rect.left - GAP

    def _draw_hints(self) -> None:
        """What a blank field means, dimmed, in empty fields you're not
        typing in (pygame_gui draws placeholders like real text).
        """
        if self._dropdown_open():
            return  # the open list would get the hint drawn over it
        for field in self.selected.fields:
            widget = self.field_widgets.get(field.name)
            if not field.hint or not isinstance(widget, UITextEntryLine):
                continue
            if widget.get_text() or widget.is_focused or not widget.visible:
                continue  # typed in, being typed in, or scrolled away
            rect = widget.rect
            draw_text(
                self.screen,
                fit(field.hint, rect.w - 20),
                (rect.x + 10, rect.centery),
                theme.TEXT_SIZE,
                theme.TEXT_DIM,
                anchor="midleft",
            )

    def _draw_detail(self) -> None:
        action, x, width = self.selected, self.detail_x, self.detail_w
        y = self.commands_box.y + 40
        kind = "Opens a game window" if action.opens_window else "Headless"
        kind_rect = draw_text(
            self.screen,
            kind,
            (x + width, y + 4),
            theme.TEXT_SIZE,
            theme.ACCENT,
            anchor="topright",
        )
        draw_text(
            self.screen,
            fit(action.name, kind_rect.left - x - 16, bold=True),
            (x, y),
            theme.BIG_SIZE,
            theme.TEXT,
            True,
        )
        y += 30
        for line in self.description:
            draw_text(
                self.screen, line, (x, y), theme.TEXT_SIZE, theme.TEXT_DIM
            )
            y += 20
        view = self.viewport
        self.screen.set_clip(view)  # what scrolled out isn't drawn
        for field in action.fields:
            fy = view.y + self.offsets[field.name] - self.scroll
            draw_text(
                self.screen,
                fit(field.name, LABEL - 12),
                (x, fy + 7),
                theme.TEXT_SIZE,
                theme.TEXT,
            )
        # The command it runs, beside Run, wrapped to the space left.
        side = x + 120 + PAD
        py = self.run_y
        command = action.command_line(self.values())
        for line in wrap(command, x + width - side)[:PREVIEW_LINES]:
            draw_text(
                self.screen, line, (side, py), theme.TEXT_SIZE, theme.TEXT_DIM
            )
            py += 18
        if self.message:
            text, color = self.message
            draw_text(
                self.screen,
                fit(text, width),
                (x, max(py, self.run_y + ROW) + 10),
                theme.TEXT_SIZE,
                color,
            )
        self.screen.set_clip(None)
        if self.max_scroll:  # a thin scroll indicator at the right
            track = Rect(self.commands_box.right - 7, view.y, 3, view.h)
            pygame.draw.rect(self.screen, theme.BAR_EMPTY, track)
            thumb = max(view.h * view.h // self.content_height, 24)
            y = view.y + (view.h - thumb) * self.scroll // self.max_scroll
            pygame.draw.rect(
                self.screen, theme.TEXT_DIM, Rect(track.x, y, 3, thumb)
            )

    def run(self) -> None:
        clock = pygame.time.Clock()
        while self.running:
            elapsed = clock.tick(60) / 1000
            for event in pygame.event.get():
                self.handle(event)
            self._refresh()
            if self.tab == "Runs":
                self.runs_tab.refresh()
            elif self.tab == "Training":
                self.training_tab.refresh()
            self.gui.update(elapsed)
            self.draw()
            pygame.display.flip()
        pygame.quit()


LEVEL_COLORS = {0: theme.GOOD, CAUTION: theme.WARN, DANGER: theme.BAD}


def _stat_gauge(surface, label, share, value, note, level, x, y) -> int:
    """LABEL ■■■■□□□□ value (note), in the level's color. Returns where
    the next stat starts.
    """
    color = LEVEL_COLORS[level]
    label_rect = draw_text(
        surface,
        label,
        (x, y),
        theme.HEADER_SIZE,
        theme.TEXT_DIM,
        anchor="midleft",
    )
    blocks, size, gap = 8, 8, 2
    left = label_rect.right + 8
    filled = max(round(share * blocks), 1 if share > 0 else 0)
    for i in range(blocks):
        pygame.draw.rect(
            surface,
            color if i < filled else theme.BAR_EMPTY,
            Rect(left + i * (size + gap), y - size // 2, size, size),
        )
    value_rect = draw_text(
        surface,
        value,
        (left + blocks * (size + gap) + 6, y),
        theme.TEXT_SIZE,
        color,
        bold=True,
        anchor="midleft",
    )
    note_rect = draw_text(
        surface,
        f"({note})",
        (value_rect.right + 6, y),
        theme.TEXT_SIZE,
        theme.WARN if note.isupper() else theme.TEXT_DIM,
        anchor="midleft",
    )
    return note_rect.right + 26


def _stat_text(surface, label, value, level, x, y) -> int:
    label_rect = draw_text(
        surface,
        label,
        (x, y),
        theme.HEADER_SIZE,
        theme.TEXT_DIM,
        anchor="midleft",
    )
    value_rect = draw_text(
        surface,
        value,
        (label_rect.right + 8, y),
        theme.TEXT_SIZE,
        LEVEL_COLORS[level] if level else theme.TEXT,
        bold=True,
        anchor="midleft",
    )
    return value_rect.right + 26


def _tab_label(name: str, step: str | None) -> str:
    return name.upper() if step is None else f"{name.upper()} · {step}"


def _available(tab: str) -> bool:
    return dict(TABS)[tab] is None


def _clock(seconds: float) -> str:
    minutes, seconds = divmod(int(seconds), 60)
    return f"{minutes}:{seconds:02d}"
