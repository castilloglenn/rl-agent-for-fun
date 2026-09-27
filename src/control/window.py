"""The control center window (roadmap step 6a): every action, grouped by
the natural steps (actions.py), the jobs running in the background, and
their live output.

    make control

It never runs anything itself: each action is its own process (see
jobs.py), started with the same `app.py` command you'd type. The console's
command line also takes make commands, like the terminal.
"""

import html
import time

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
from src.control.makefile import read_commands
from src.render import theme
from src.utils.ui import draw_text, get_font

SIZE = (1280, 820)
MARGIN = 16
PAD = 14
ROW = 30  # a row of widgets
GAP = 8  # between rows
LABEL = 124  # the width of a field's label
REFRESH = 0.5  # seconds between job list refreshes
TAB_HEIGHT = 36
TABS = (  # (name, the step it arrives in: None if it's here)
    ("Commands", None),
    ("Training", "6b"),
    ("Runs", "6b"),
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
    look["#jobs.@selection_list_item"] = {
        "font": _font(CONSOLE_FONT),
        "misc": ITEM,
    }
    return look


def fit(text: str, width: float, bold: bool = False) -> str:
    """`text`, shortened with "…" to fit `width` pixels."""
    font = get_font(theme.TEXT_SIZE, bold)
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


class ControlCenter:
    def __init__(self, jobs: JobManager | None = None) -> None:
        pygame.init()
        pygame.display.set_caption("Maze Car · Control Center")
        self.screen = pygame.display.set_mode(SIZE)
        self.gui = pygame_gui.UIManager(SIZE, gui_theme())
        self.jobs = jobs or JobManager()
        self.make_commands = read_commands()  # for the typed command line
        self.running = True
        self.confirm_quit = False  # the quit box is open
        self.quit_buttons: dict[str, Rect] = {}  # its buttons, when drawn
        self.tab = "Commands"
        self.message: tuple[str, tuple] | None = None  # next to Run
        self.selected_job = None
        self._refreshed = 0.0
        self._log_seen = -1
        self._rows = None

        # The boxes: tabs on top, then commands and jobs, then console.
        width = SIZE[0] - 2 * MARGIN
        self.tab_bar = Rect(MARGIN, MARGIN, width, TAB_HEIGHT)
        top = self.tab_bar.bottom + MARGIN
        self.console = Rect(MARGIN, SIZE[1] - MARGIN - 224, width, 224)
        height = self.console.y - MARGIN - top
        self.jobs_box = Rect(SIZE[0] - MARGIN - 360, top, 360, height)
        self.commands_box = Rect(
            MARGIN, top, self.jobs_box.x - 2 * MARGIN, height
        )
        self.tab_rects = self._tab_rects()
        self._build()

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
                console.h - 36 - ROW - 2 * PAD,
            ),
            gui,
            object_id="#console",
        )
        self.command_line = UITextEntryLine(
            Rect(
                console.x + PAD,
                console.bottom - PAD - ROW,
                console.w - 2 * PAD,
                ROW,
            ),
            gui,
            placeholder_text="Or type a make command, for example: "
            "train AGENT=rookie",
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
        # The description wraps to the detail area; the fields follow.
        self.description = wrap(self.selected.description, self.detail_w)
        y = self.commands_box.y + 40 + 30 + 20 * len(self.description) + 14
        self.fields_y = y
        width = self.detail_w - LABEL
        for field in self.selected.fields:
            rect = Rect(self.detail_x + LABEL, y, width, ROW)
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
            y += ROW + GAP
        # Run under the fields, the command it runs beside it, and
        # messages under Run.
        self.run_y = y + 10
        self.run_button = UIButton(
            Rect(self.detail_x, self.run_y, 120, ROW), "Run", self.gui
        )

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

    def run_action(self, action: Action, values: dict) -> None:
        """Runs an action, unless a field it needs is empty."""
        empty = []
        for field in action.fields:
            value = values.get(field.name, field.default).strip()
            optional = field.options is None and field.hint
            if not value and not optional:
                empty.append(field.name)
        if empty:
            self.message = (f"Needs: {', '.join(empty)}", theme.BAD)
            return
        label = action.name
        if action.fields:
            label += f": {values.get(action.fields[0].name, '')}"
        self._start(label, action.argv(values), action.opens_window)

    def _start(self, label: str, argv: list[str], window: bool) -> None:
        job = self.jobs.start(label, argv)
        self.selected_job = job
        where = "a game window opens" if window else "headless"
        self.message = (f"Started job #{job.number} ({where})", theme.GOOD)
        self._log_seen = -1
        self._refresh(force=True)

    def run_typed(self, text: str) -> None:
        """A make command, typed: `train AGENT=rookie` (make is optional)."""
        words = text.split()
        if words and words[0] == "make":
            words = words[1:]
        if not words:
            return
        command = next(
            (c for c in self.make_commands if c.name == words[0]), None
        )
        if not command:
            self.message = (f"No make command {words[0]!r}", theme.BAD)
            return
        values = dict(w.split("=", 1) for w in words[1:] if "=" in w)
        try:
            argv = command.argv(values)
        except ValueError as error:
            self.message = (str(error), theme.BAD)
            return
        self._start(command.make_line(values), argv, command.opens_window)

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

    def ask_to_quit(self) -> None:
        self.confirm_quit = True

    def quit(self) -> None:
        self.jobs.stop_all()
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
                    self.tab = name
        elif event.type == pygame_gui.UI_DROP_DOWN_MENU_CHANGED:
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
        elif event.type == pygame_gui.UI_TEXT_ENTRY_FINISHED:
            if event.ui_element is self.command_line:
                self.run_typed(event.text)
                self.command_line.set_text("")

    def _handle_quit_box(self, event) -> None:
        """Esc (or Cancel) goes back, Enter (or Confirm) quits. Closing the
        window again while it's open quits too.
        """
        if event.type == pygame.QUIT:
            self.quit()
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.confirm_quit = False
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.quit()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            nowhere = Rect(0, 0, 0, 0)
            if self.quit_buttons.get("cancel", nowhere).collidepoint(
                event.pos
            ):
                self.confirm_quit = False
            elif self.quit_buttons.get("confirm", nowhere).collidepoint(
                event.pos
            ):
                self.quit()

    def _refresh(self, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self._refreshed < REFRESH:
            return
        self._refreshed = now
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
        boxes = (self.tab_bar, self.commands_box, self.jobs_box, self.console)
        for rect in boxes:
            pygame.draw.rect(self.screen, theme.PANEL_BORDER, rect, 1)
        self._draw_tabs()
        _header(self.screen, self.commands_box, "COMMANDS")
        _header(self.screen, self.jobs_box, "JOBS")
        job = getattr(self, "_log_job", None)
        title = "CONSOLE"
        if job:
            title = fit(
                f"CONSOLE · #{job.number} {job.label}",
                self.console.w - 2 * PAD,
                bold=True,
            )
        _header(self.screen, self.console, title)
        if self.selected:
            self._draw_detail()
        self.gui.draw_ui(self.screen)
        if self.selected:
            self._draw_hints()
        if self.confirm_quit:
            self._draw_quit_box()

    def _dropdown_open(self) -> bool:
        menus = [self.group_menu, *self.field_widgets.values()]
        return any(
            isinstance(menu, UIDropDownMenu)
            and menu.current_state is menu.menu_states["expanded"]
            for menu in menus
        )

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
            if widget.get_text() or widget.is_focused:
                continue
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
        fy = self.fields_y
        for field in action.fields:
            draw_text(
                self.screen,
                fit(field.name, LABEL - 12),
                (x, fy + 7),
                theme.TEXT_SIZE,
                theme.TEXT,
            )
            fy += ROW + GAP
        # The command it runs, beside Run, wrapped to the space left.
        side = x + 120 + PAD
        py = self.run_y
        command = action.command_line(self.values())
        for line in wrap(command, x + width - side)[:4]:
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

    def run(self) -> None:
        clock = pygame.time.Clock()
        while self.running:
            elapsed = clock.tick(60) / 1000
            for event in pygame.event.get():
                self.handle(event)
            self._refresh()
            self.gui.update(elapsed)
            self.draw()
            pygame.display.flip()
        pygame.quit()


def _tab_label(name: str, step: str | None) -> str:
    return name.upper() if step is None else f"{name.upper()} · {step}"


def _available(tab: str) -> bool:
    return dict(TABS)[tab] is None


def _header(surface, rect: Rect, text: str) -> None:
    draw_text(
        surface,
        text,
        (rect.x + PAD, rect.y + 12),
        theme.HEADER_SIZE,
        theme.ACCENT,
        bold=True,
    )


def _clock(seconds: float) -> str:
    minutes, seconds = divmod(int(seconds), 60)
    return f"{minutes}:{seconds:02d}"
