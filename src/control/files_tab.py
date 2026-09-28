"""The control center's Files tab (roadmap step 6d1): edit reward
profiles, rules, trainers, models, datasets, and suites, checked as you
type by the validators the commands use.

    ┌ FILES ───────┐ ┌ rules/standard.json ─────────────────────────┐
    │ [Rules ▾]    │ │ description        [One 60 s round, ...     ] │
    │  classic     │ │ round_seconds      [60                      ] │
    │ ▸standard    │ │ ... (the fields scroll)                      │
    │              │ │ Valid, saved                                 │
    │              │ │ [Save] [Revert]  [new name] [Duplicate] [Del]│
    └──────────────┘ └──────────────────────────────────────────────┘

The logic (fields, checking, writing) is in files.py.
"""

import time
from pathlib import Path
from typing import Callable

import pygame
import pygame_gui
from pygame import Rect
from pygame_gui.elements import (
    UIButton,
    UIDropDownMenu,
    UISelectionList,
    UITextEntryLine,
)

from src.control import files, help
from src.control.actions import Field
from src.control.confirm import Confirm
from src.control.files import KINDS, FileError, Kind
from src.control.form import Form
from src.control.text import PAD, fit, header
from src.control.tooltips import Tooltips
from src.control.trash import Trash, TrashError
from src.render import theme
from src.utils.ui import draw_text

LIST_WIDTH = 300
MARGIN = 16
ROW = 30
GAP = 8
LABEL = 250  # field paths are long: scenarios.1.first_seed
CHECK_EVERY = 0.3  # seconds between checks while typing
DEFAULT_TAG = "  (default)"


class FilesTab:
    def __init__(
        self,
        gui,
        area: Rect,
        ask: Callable[[Confirm], None],
        root: Path | None = None,
    ) -> None:
        """`ask(box)` opens a confirmation box. `root`: the repo (tests
        use a scratch copy).
        """
        self.gui = gui
        self.ask = ask
        self.root = root or files.REPO
        self.list_box = Rect(area.x, area.y, LIST_WIDTH, area.h)
        self.editor = Rect(
            self.list_box.right + MARGIN,
            area.y,
            area.right - self.list_box.right - MARGIN,
            area.h,
        )
        box = self.list_box
        self.kind_menu = None
        self._build_kind_menu(KINDS[0])
        self.file_list = UISelectionList(
            Rect(
                box.x + PAD,
                box.y + 40 + ROW + GAP,
                box.w - 2 * PAD,
                box.h - 40 - ROW - GAP - PAD,
            ),
            [],
            gui,
        )
        e = self.editor
        self.buttons_y = e.bottom - PAD - ROW
        self.status_y = self.buttons_y - 30
        top = e.y + 92
        self.form = Form(
            gui,
            Rect(
                e.x + PAD, top, e.w - 2 * PAD - 12, self.status_y - 12 - top
            ),
            label_width=LABEL,
            help_for=lambda path: help.field(self.kind.folder, path),
        )
        self.tips = Tooltips()  # the window shares its own
        x = e.x + PAD
        self.buttons: dict[str, UIButton] = {}
        for name, width in (("Save", 100), ("Revert", 100)):
            self.buttons[name] = UIButton(
                Rect(x, self.buttons_y, width, ROW), name, gui
            )
            x += width + GAP
        x += 3 * GAP
        self.new_name = UITextEntryLine(
            Rect(x, self.buttons_y, 200, ROW), gui
        )
        x += 200 + GAP
        self.buttons["Duplicate as…"] = UIButton(
            Rect(x, self.buttons_y, 130, ROW), "Duplicate as…", gui
        )
        self.buttons["Delete"] = UIButton(
            Rect(e.right - PAD - 100, self.buttons_y, 100, ROW), "Delete", gui
        )

        self.kind: Kind = KINDS[0]  # (help_for above reads it)
        self.name: str | None = None
        self.original: dict = {}
        self.problem: str | None = None
        self.dirty = False
        self.message: tuple[str, tuple] | None = None
        self._tracked: set[str] = set()
        self._checked_values: dict | None = None
        self._checked = 0.0
        self.visible = True
        self._show_kind(KINDS[0])

    def _build_kind_menu(self, kind: Kind) -> None:
        """The kind picker, showing `kind` (rebuilt to undo a pick that
        waits for "discard changes?").
        """
        if self.kind_menu:
            self.kind_menu.kill()
        box = self.list_box
        self.kind_menu = UIDropDownMenu(
            [k.label for k in KINDS],
            kind.label,
            Rect(box.x + PAD, box.y + 40, box.w - 2 * PAD, ROW),
            self.gui,
        )
        if not getattr(self, "visible", True):
            self.kind_menu.hide()

    # Showing and hiding with the tab

    def widgets(self) -> list:
        return [
            self.kind_menu,
            self.file_list,
            self.new_name,
            *self.buttons.values(),
        ]

    def show(self) -> None:
        self.visible = True
        for widget in self.widgets():
            widget.show()
        self.form.show()

    def hide(self) -> None:
        self.visible = False
        for widget in self.widgets():
            widget.hide()
        self.form.hide()

    # Choosing a file

    def _show_kind(self, kind: Kind, name: str | None = None) -> None:
        shown = self.kind_menu.selected_option
        if (shown[0] if isinstance(shown, tuple) else shown) != kind.label:
            self._build_kind_menu(kind)  # the picker follows the file
        self.kind = kind
        self._tracked = files.tracked(self.root, kind)
        found = files.names(self.root / kind.folder)
        self.file_list.set_item_list(
            [n + (DEFAULT_TAG if n in kind.defaults else "") for n in found]
        )
        if not self.visible:
            self.file_list.hide()
        pick = name if name in found else (found[0] if found else None)
        self._open(pick)

    def _open(self, name: str | None) -> None:
        self.name = name
        self.message = None
        self.original = files.load(self.root, self.kind, name) if name else {}
        fields = []
        for item in files.items(self.kind.folder, self.original, self.root):
            fields.append(
                Field(
                    item.path,
                    (lambda o=item.options: list(o)) if item.options else None,
                    item.text,
                    item.hint,
                    readonly=item.type == "readonly",
                )
            )
        self.form.scroll = 0
        self.form.build(fields)
        if not self.visible:
            self.form.hide()
        self._highlight()
        self._checked_values = None
        self.check(force=True)

    def _highlight(self) -> None:
        for item in self.file_list.item_list:
            chosen = item["text"].replace(DEFAULT_TAG, "") == self.name
            item["selected"] = chosen
            button = item["button_element"]
            if button is not None:
                button.select() if chosen else button.unselect()

    def _unless_dirty(self, then: Callable[[], None]) -> None:
        """Runs `then`, asking first if there are unsaved changes."""
        if not self.dirty:
            then()
            return
        self._highlight()  # keep showing the file being edited
        self.ask(
            Confirm(
                "DISCARD CHANGES?",
                [
                    (f"{self.path} has unsaved changes.", theme.TEXT),
                    ("They'll be lost.", theme.TEXT_DIM),
                ],
                then,
                confirm_label="Discard (Enter)",
            )
        )

    @property
    def path(self) -> str:
        return f"{self.kind.folder}/{self.name}.json"

    # Checking

    def edited(self) -> dict:
        """The file as the fields have it (FileError if a value is wrong
        for its field).
        """
        values = self.form.values()
        return files.rebuild(self.kind.folder, self.original, values)

    def check(self, force: bool = False) -> None:
        """Checks the fields, at most every CHECK_EVERY seconds while you
        type.
        """
        now = time.monotonic()
        values = self.form.values()
        if not force and (
            values == self._checked_values
            or now - self._checked < CHECK_EVERY
        ):
            return
        self._checked, self._checked_values = now, values
        if not self.name:
            self.problem, self.dirty = None, False
        else:
            try:
                data = self.edited()
            except FileError as error:
                self.problem, self.dirty = str(error), True
            else:
                self.problem = files.check(self.kind, data)
                self.dirty = files.dump(data) != files.dump(self.original)
        self._update_buttons()

    def refresh(self, force: bool = False) -> None:
        self.check(force)

    def _update_buttons(self) -> None:
        default = self.name in self.kind.defaults
        wanted = {
            "Save": self.dirty and not self.problem,
            "Revert": self.dirty,
            "Duplicate as…": bool(self.name),
            "Delete": bool(self.name) and not default,
        }
        for name, on in wanted.items():
            button = self.buttons[name]
            if on and not button.is_enabled:
                button.enable()
            elif not on and button.is_enabled:
                button.disable()

    # Acting

    def save(self) -> None:
        try:
            data = self.edited()
            written = files.save(self.root, self.kind, self.name, data)
        except FileError as error:
            self.message = (str(error), theme.BAD)
            return
        version = written.get("version")
        before = self.original.get("version")
        self._open(self.name)
        if self.kind.folder == "suites" and version != before:
            self.message = (
                f"Saved {self.path} as version {version}: scores of version "
                f"{before} stay apart.",
                theme.GOOD,
            )
        else:
            self.message = (f"Saved {self.path}.", theme.GOOD)

    def duplicate(self) -> None:
        new = self.new_name.get_text().strip()
        try:
            files.duplicate(self.root, self.kind, self.name, new)
        except FileError as error:
            self.message = (str(error), theme.BAD)
            return
        self.new_name.set_text("")
        self._show_kind(self.kind, new)
        self.message = (f"Made {self.path}: edit it, then Save.", theme.GOOD)

    def delete(self) -> None:
        if self.name in self.kind.defaults:
            return
        path, name = self.path, self.name

        def go() -> None:
            try:
                entry = Trash(self.root).delete_file(self.kind.folder, name)
            except TrashError as error:
                self.message = (str(error), theme.BAD)
                return
            self._show_kind(self.kind)
            self.message = (
                f"Moved {path} into the trash ({entry.name}).",
                theme.GOOD,
            )

        self.ask(
            Confirm(
                "DELETE A FILE?",
                [
                    (f"{path} moves into the trash.", theme.TEXT),
                    (
                        "Runs and replays keep their own copy. You can "
                        "restore it later.",
                        theme.TEXT_DIM,
                    ),
                ],
                go,
                confirm_label="Delete (Enter)",
                title_color=theme.BAD,
            )
        )

    def dropdown_open(self) -> bool:
        menu = self.kind_menu
        expanded = menu.current_state is menu.menu_states["expanded"]
        return expanded or self.form.dropdown_open()

    # Events

    def handle(self, event) -> None:
        if event.type == pygame_gui.UI_DROP_DOWN_MENU_CHANGED:
            if event.ui_element is self.kind_menu:
                kind = next(k for k in KINDS if k.label == event.text)
                if kind != self.kind:
                    if self.dirty:  # show the current kind until answered
                        self._build_kind_menu(self.kind)

                    def switch() -> None:
                        self._build_kind_menu(kind)
                        self._show_kind(kind)

                    self._unless_dirty(switch)
            else:
                self.check(force=True)
        elif event.type == pygame_gui.UI_SELECTION_LIST_NEW_SELECTION:
            if event.ui_element is self.file_list:
                name = event.text.replace(DEFAULT_TAG, "")
                if name != self.name:
                    self._unless_dirty(lambda: self._open(name))
        elif event.type == pygame_gui.UI_TEXT_ENTRY_CHANGED:
            if event.ui_element is not self.new_name:
                self.message = None
        elif event.type == pygame_gui.UI_BUTTON_PRESSED:
            if event.ui_element is self.buttons["Save"]:
                self.save()
            elif event.ui_element is self.buttons["Revert"]:
                self._open(self.name)
            elif event.ui_element is self.buttons["Duplicate as…"]:
                self.duplicate()
            elif event.ui_element is self.buttons["Delete"]:
                self.delete()
        elif event.type == pygame.MOUSEWHEEL:
            self.form.handle_wheel(event)

    # Drawing

    def draw(self, surface) -> None:
        for rect in (self.list_box, self.editor):
            pygame.draw.rect(surface, theme.PANEL_BORDER, rect, 1)
        header(surface, self.list_box, "FILES")
        e = self.editor
        header(surface, e, "EDITOR")
        if not self.name:
            draw_text(
                surface,
                f"No {self.kind.label.lower()} yet.",
                (e.x + PAD, e.y + 40),
                theme.TEXT_SIZE,
                theme.TEXT_DIM,
            )
            return
        width = e.w - 2 * PAD
        draw_text(
            surface,
            fit(self.path, width, True, theme.BIG_SIZE),
            (e.x + PAD, e.y + 34),
            theme.BIG_SIZE,
            theme.TEXT,
            bold=True,
        )
        notes = []
        if self.name in self.kind.defaults:
            notes.append("a default the code relies on: it can't be deleted")
        if self.name in self._tracked:
            notes.append("tracked by git: a saved change shows in git status")
        if self.kind.folder == "suites":
            notes.append(
                f"version {self.original.get('version')}: saving a change "
                "makes the next version"
            )
        notes.append("changes apply to future runs only")
        draw_text(
            surface,
            fit(_sentence(" · ".join(notes)), width),
            (e.x + PAD, e.y + 62),
            theme.TEXT_SIZE,
            theme.TEXT_DIM,
        )
        self.form.draw_labels(surface, self.tips)
        if self.problem:
            status, color = f"Can't save: {self.problem}", theme.BAD
        elif self.dirty:
            status, color = "Valid, unsaved changes", theme.WARN
        else:
            status, color = "Valid, saved", theme.GOOD
        if self.message:
            status, color = self.message
        draw_text(
            surface,
            fit(status, width),
            (e.x + PAD, self.status_y),
            theme.TEXT_SIZE,
            color,
        )

    def draw_after(self, surface) -> None:
        """After the GUI: the hints in blank fields, and the new name's."""
        self.form.draw_hints(surface)
        entry = self.new_name
        if not entry.get_text() and not entry.is_focused and entry.visible:
            draw_text(
                surface,
                "new name",
                (entry.rect.x + 10, entry.rect.centery),
                theme.TEXT_SIZE,
                theme.TEXT_DIM,
                anchor="midleft",
            )


def _sentence(text: str) -> str:
    return text[:1].upper() + text[1:]
