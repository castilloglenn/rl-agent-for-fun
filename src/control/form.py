"""A column of fields for the control center's tabs (roadmap step 6b2):
a label per field, a dropdown (from the files on disk) or a typed value,
dimmed hints in blank typed fields, and scrolling with the mouse wheel
when the fields don't fit.

The scrolling is done by hand, like the Commands tab's: pygame_gui's
scrolling container would clip an open dropdown's list at its edge.
"""

import pygame
from pygame import Rect
from pygame_gui.elements import UIDropDownMenu, UITextEntryLine

from src.control.actions import Field
from src.control.text import fit
from src.render import theme
from src.utils.ui import draw_text

ROW = 30
GAP = 8
LABEL = 124
SCROLL_STEP = 40


class Form:
    def __init__(self, gui, viewport: Rect, extra_height: int = 0) -> None:
        """`viewport`: where the fields go. `extra_height`: room below the
        fields for the caller's own widgets (they scroll too).
        """
        self.gui = gui
        self.viewport = viewport
        self.extra_height = extra_height
        self.fields: list[Field] = []
        self.widgets: dict[str, object] = {}
        self.offsets: dict[str, int] = {}
        self.scroll = 0
        self.visible = True

    def build(self, fields: list[Field], values: dict | None = None) -> None:
        """New fields, keeping the values of fields that stay."""
        values = values or {}
        for widget in self.widgets.values():
            widget.kill()
        self.fields, self.widgets, self.offsets = list(fields), {}, {}
        view = self.viewport
        width = view.w - LABEL
        for i, field in enumerate(self.fields):
            y = i * (ROW + GAP)
            rect = Rect(view.x + LABEL, view.y + y, width, ROW)
            value = values.get(field.name, field.default)
            options = field.options() if field.options else None
            if options:
                shown = [(fit(o, width - 40), o) for o in options]
                start = next(
                    (s for s in shown if s[1] == value),
                    next((s for s in shown if s[1] == field.default), None)
                    or shown[0],
                )
                widget = UIDropDownMenu(shown, start, rect, self.gui)
            elif field.options:  # nothing to pick yet
                widget = UIDropDownMenu(
                    ["(none yet)"], "(none yet)", rect, self.gui
                )
                widget.disable()
            else:
                widget = UITextEntryLine(rect, self.gui)
                widget.set_text(value)
            self.widgets[field.name] = widget
            self.offsets[field.name] = y
        self.scroll = min(self.scroll, self.max_scroll)
        self.place()

    @property
    def fields_height(self) -> int:
        return len(self.fields) * (ROW + GAP)

    @property
    def content_height(self) -> int:
        return self.fields_height + self.extra_height

    @property
    def max_scroll(self) -> int:
        return max(self.content_height - self.viewport.h, 0)

    def scroll_by(self, pixels: int) -> None:
        self.scroll = min(max(self.scroll + pixels, 0), self.max_scroll)
        self.place()

    def y_of(self, offset: int) -> int:
        """Where content at `offset` is on screen, after scrolling."""
        return self.viewport.y + offset - self.scroll

    def place(self) -> None:
        """Moves the widgets to the scroll position. A widget that isn't
        fully inside the viewport hides.
        """
        view = self.viewport
        for name, widget in self.widgets.items():
            y = self.y_of(self.offsets[name])
            widget.set_position((widget.rect.x, y))
            inside = view.top <= y and y + ROW <= view.bottom
            if inside and self.visible:
                widget.show()
            else:
                widget.hide()

    def show(self) -> None:
        self.visible = True
        self.place()

    def hide(self) -> None:
        self.visible = False
        for widget in self.widgets.values():
            widget.hide()

    def values(self) -> dict[str, str]:
        found = {}
        for name, widget in self.widgets.items():
            if isinstance(widget, UIDropDownMenu):
                option = widget.selected_option
                found[name] = option[1] if isinstance(option, tuple) else ""
            else:
                found[name] = widget.get_text().strip()
        return found

    def field_of(self, element) -> str | None:
        """The field an element belongs to, if it's one of ours."""
        return next(
            (n for n, w in self.widgets.items() if w is element), None
        )

    def dropdown_open(self) -> bool:
        return any(
            isinstance(menu, UIDropDownMenu)
            and menu.current_state is menu.menu_states["expanded"]
            for menu in self.widgets.values()
        )

    def handle_wheel(self, event) -> None:
        over = self.viewport.collidepoint(pygame.mouse.get_pos())
        if over and not self.dropdown_open():
            self.scroll_by(-event.y * SCROLL_STEP)

    # Drawing

    def draw_labels(self, surface) -> None:
        """Before the GUI: each field's label, and the scroll indicator."""
        view = self.viewport
        surface.set_clip(view)
        for field in self.fields:
            y = self.y_of(self.offsets[field.name])
            draw_text(
                surface,
                fit(field.name, LABEL - 12),
                (view.x, y + 7),
                theme.TEXT_SIZE,
                theme.TEXT,
            )
        surface.set_clip(None)
        if self.max_scroll:  # a thin indicator at the right
            track = Rect(view.right + 7, view.y, 3, view.h)
            pygame.draw.rect(surface, theme.BAR_EMPTY, track)
            thumb = max(view.h * view.h // self.content_height, 24)
            y = view.y + (view.h - thumb) * self.scroll // self.max_scroll
            pygame.draw.rect(
                surface, theme.TEXT_DIM, Rect(track.x, y, 3, thumb)
            )

    def draw_hints(self, surface) -> None:
        """After the GUI: what a blank field means, dimmed, in empty
        fields you're not typing in (pygame_gui draws placeholders like
        real text).
        """
        if self.dropdown_open():
            return  # the open list would get the hint drawn over it
        for field in self.fields:
            widget = self.widgets.get(field.name)
            if not field.hint or not isinstance(widget, UITextEntryLine):
                continue
            if widget.get_text() or widget.is_focused or not widget.visible:
                continue
            rect = widget.rect
            draw_text(
                surface,
                fit(field.hint, rect.w - 20),
                (rect.x + 10, rect.centery),
                theme.TEXT_SIZE,
                theme.TEXT_DIM,
                anchor="midleft",
            )
