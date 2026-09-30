"""The control center's Files tab (roadmap step 6d1): edit reward
profiles, rules, trainers, models, datasets, and suites, checked as you
type by the validators the commands use.

    ┌ FILES ───────┐ ┌ rules/standard.json ─────────────────────────┐
    │ [Rules ▾]    │ │ description        [One 60 s round, ...     ] │
    │  marathon    │ │ round_seconds      [60                      ] │
    │ ▸standard    │ │ ... (the fields scroll)                      │
    │              │ │ Valid, saved                                 │
    │              │ │ [Save] [Revert]  [new name] [Duplicate] [Del]│
    └──────────────┘ └──────────────────────────────────────────────┘

The logic (fields, checking, writing) is in files.py. The last kind,
Recordings, swaps the editor for the recordings browser (step 6d2,
recordings_view.py): the list shows players, the right side a table.
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
from src.control.recordings_data import players
from src.control.recordings_view import RecordingsView
from src.control.text import PAD, fit, header
from src.control.tooltips import Tooltips
from src.control.trash import Trash, TrashError
from src.render import theme
from src.utils import named_files
from src.utils.ui import draw_text

LIST_WIDTH = 300
MARGIN = 16
ROW = 30
GAP = 8
LABEL = 250  # field paths are long: scenarios.1.first_seed
CHECK_EVERY = 0.3  # seconds between checks while typing
TAG = "  · "  # a list row: "sprint  · built-in", "fast  · yours"
BUILT_IN_TAG, YOURS_TAG = "built-in", "yours"
RECORDINGS = "Recordings"  # the kind that browses recordings (6d2)


class FilesTab:
    def __init__(
        self,
        gui,
        area: Rect,
        ask: Callable[[Confirm], None],
        root: Path | None = None,
        run_action: Callable[[str, dict], object] = lambda n, v: None,
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
        self._build_kind_menu(KINDS[0].label)
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
        self.built_in = False  # the open file ships with the app (7d1b)
        self._checked_values: dict | None = None
        self._checked = 0.0
        self.visible = True
        self.mode = "files"  # or "recordings"
        self.view = RecordingsView(
            gui, self.editor, ask, run_action, self.root
        )
        self._show_kind(KINDS[0])

    def _build_kind_menu(self, label: str) -> None:
        """The kind picker, showing `label` (rebuilt to undo a pick that
        waits for "discard changes?").
        """
        if self.kind_menu:
            self.kind_menu.kill()
        box = self.list_box
        self.kind_menu = UIDropDownMenu(
            [k.label for k in KINDS] + [RECORDINGS],
            label,
            Rect(box.x + PAD, box.y + 40, box.w - 2 * PAD, ROW),
            self.gui,
        )
        if not getattr(self, "visible", True):
            self.kind_menu.hide()

    # Showing and hiding with the tab

    def widgets(self) -> list:
        return [self.kind_menu, self.file_list, *self.editor_widgets()]

    def editor_widgets(self) -> list:
        return [self.new_name, *self.buttons.values()]

    def show(self) -> None:
        self.visible = True
        self.kind_menu.show()
        self.file_list.show()
        self._show_mode()

    def hide(self) -> None:
        self.visible = False
        for widget in self.widgets():
            widget.hide()
        self.form.hide()
        self.view.hide()

    def _show_mode(self) -> None:
        """The editor's widgets, or the recordings browser's."""
        editing = self.mode == "files"
        for widget in self.editor_widgets():
            widget.show() if editing and self.visible else widget.hide()
        if editing and self.visible:
            self.form.show()
            self.view.hide()
        else:
            self.form.hide()
            if self.visible:
                self.view.show()
            else:
                self.view.hide()

    def show_recordings(self) -> None:
        self.mode = "recordings"
        self.dirty = False
        self.name = None
        shown = self.kind_menu.selected_option
        if (shown[0] if isinstance(shown, tuple) else shown) != RECORDINGS:
            self._build_kind_menu(RECORDINGS)
        found = players(self.root / "recordings")
        self.file_list.set_item_list([f"{p}  ({n})" for p, n in found])
        if not self.visible:
            self.file_list.hide()
        self._show_mode()
        self.view.open(found[0][0] if found else None)
        for item in self.file_list.item_list[:1]:
            item["selected"] = True
            if item["button_element"] is not None:
                item["button_element"].select()

    # Choosing a file

    def _show_kind(self, kind: Kind, name: str | None = None) -> None:
        shown = self.kind_menu.selected_option
        if (shown[0] if isinstance(shown, tuple) else shown) != kind.label:
            self._build_kind_menu(kind.label)  # the picker follows the file
        self.kind = kind
        self.mode = "files"
        self._show_mode()
        found = list(named_files.ordered(kind.folder, self.root))
        self.file_list.set_item_list([self._row(n) for n in found])
        if not self.visible:
            self.file_list.hide()
        pick = name if name in found else (found[0] if found else None)
        self._open(pick)

    def _row(self, name: str) -> str:
        """A file list row: the name and whose it is."""
        built_in = named_files.is_built_in(self.kind.folder, name, self.root)
        return name + TAG + (BUILT_IN_TAG if built_in else YOURS_TAG)

    def _open(self, name: str | None) -> None:
        self.name = name
        self.message = None
        self.built_in = bool(name) and named_files.is_built_in(
            self.kind.folder, name, self.root
        )
        self.original = files.load(self.root, self.kind, name) if name else {}
        fields = []
        for item in files.items(self.kind.folder, self.original, self.root):
            fields.append(
                Field(
                    item.path,
                    (lambda o=item.options: list(o)) if item.options else None,
                    item.text,
                    item.hint,
                    readonly=item.type == "readonly" or self.built_in,
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
            chosen = item["text"].split(TAG)[0] == self.name
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
        """Where the open file is: rules/sprint.json, user/rules/x.json."""
        try:
            where = named_files.find(self.kind.folder, self.name, self.root)
            return str(where.relative_to(self.root))
        except (FileNotFoundError, ValueError):
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
        if not self.name or self.built_in:  # a built-in can't change here
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

    def on_data(self, kinds: set[str]) -> None:
        """Files or recordings changed elsewhere (7c7). The list updates
        in place: the open file stays open, with its unsaved edits, unless
        it's the one that was deleted.
        """
        if self.mode == "recordings":
            if "recordings" in kinds:
                found = players(self.root / "recordings")
                self.file_list.set_item_list([f"{p}  ({n})" for p, n in found])
                self.view.reload()
            return
        if self.kind.folder not in kinds:
            return
        found = list(named_files.ordered(self.kind.folder, self.root))
        if self.name and self.name not in found:
            gone = self.path
            self._show_kind(self.kind)
            self.message = (f"{gone} is gone (deleted elsewhere).", theme.WARN)
            return
        rows = [self._row(n) for n in found]
        if rows != [item["text"] for item in self.file_list.item_list]:
            self.file_list.set_item_list(rows)
            self._highlight()
        if not self.visible:
            self.file_list.hide()

    def refresh(self, force: bool = False) -> None:
        if self.mode == "files":
            self.check(force)

    def _update_buttons(self) -> None:
        yours = bool(self.name) and not self.built_in
        wanted = {
            "Save": yours and self.dirty and not self.problem,
            "Revert": yours and self.dirty,
            "Duplicate as…": bool(self.name),
            "Delete": yours,
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
        if self.built_in or not self.name:
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
        if self.mode == "recordings":
            return expanded or self.view.dropdown_open()
        return expanded or self.form.dropdown_open()

    # Events

    def handle(self, event) -> None:
        if (
            event.type == pygame_gui.UI_DROP_DOWN_MENU_CHANGED
            and event.ui_element is self.kind_menu
        ):
            self._pick_kind(event.text)
            return
        if self.mode == "recordings":
            if (
                event.type == pygame_gui.UI_SELECTION_LIST_NEW_SELECTION
                and event.ui_element is self.file_list
            ):
                self.view.open(event.text.rsplit("  (", 1)[0])
            else:
                self.view.handle(event)
            return
        if event.type == pygame_gui.UI_DROP_DOWN_MENU_CHANGED:
            self.check(force=True)
        elif event.type == pygame_gui.UI_SELECTION_LIST_NEW_SELECTION:
            if event.ui_element is self.file_list:
                name = event.text.split(TAG)[0]
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

    def _pick_kind(self, label: str) -> None:
        current = RECORDINGS if self.mode == "recordings" else self.kind.label
        if label == current:
            return
        if self.dirty:  # show the current kind until answered
            self._build_kind_menu(current)
        if label == RECORDINGS:
            self._unless_dirty(self.show_recordings)
            return
        kind = next(k for k in KINDS if k.label == label)

        def switch() -> None:
            self._build_kind_menu(kind.label)
            self._show_kind(kind)

        self._unless_dirty(switch)

    # Drawing

    def draw(self, surface) -> None:
        for rect in (self.list_box, self.editor):
            pygame.draw.rect(surface, theme.PANEL_BORDER, rect, 1)
        header(surface, self.list_box, "FILES")
        if self.mode == "recordings":
            self.view.tips = self.tips
            self.view.draw(surface)
            return
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
        if self.built_in:
            notes = [
                "built-in: it ships with the app and changes only in code; "
                "Duplicate as… makes your own copy"
            ]
        else:
            notes = [f"yours, in user/{self.kind.folder}/ (out of git)"]
        if self.kind.folder == "suites":
            notes.append(
                f"version {self.original.get('version')}: saving a change "
                "makes the next version"
            )
        if not self.built_in:
            notes.append("changes apply to future runs only")
        draw_text(
            surface,
            fit(_sentence(" · ".join(notes)), width),
            (e.x + PAD, e.y + 62),
            theme.TEXT_SIZE,
            theme.TEXT_DIM,
        )
        self.form.draw_labels(surface, self.tips)
        if self.built_in:
            status, color = "Built-in: read-only", theme.TEXT_DIM
        elif self.problem:
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
        if self.mode == "recordings":
            return
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
