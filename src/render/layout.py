from dataclasses import dataclass

from pygame import Rect

MARGIN = 16
TOP_BAR_HEIGHT = 56
BOTTOM_BAR_HEIGHT = 40
PANEL_WIDTH = 300


@dataclass(frozen=True)
class Layout:
    """Screen rects of the simulation window, derived from the field size.

    ┌──────────────────────┬───────┐
    │ top_bar              │ panel │
    ├──────────────────────┤       │
    │ field_view           │       │
    ├──────────────────────┴───────┤
    │ bottom_bar                   │
    └──────────────────────────────┘
    """

    window: Rect
    top_bar: Rect
    field_view: Rect
    panel: Rect
    bottom_bar: Rect

    @staticmethod
    def for_field(field_width: float, field_height: float) -> "Layout":
        width, height = int(field_width), int(field_height)
        top_bar = Rect(MARGIN, MARGIN, width, TOP_BAR_HEIGHT)
        field_view = Rect(MARGIN, top_bar.bottom + MARGIN, width, height)
        panel = Rect(
            field_view.right + MARGIN,
            MARGIN,
            PANEL_WIDTH,
            field_view.bottom - MARGIN,
        )
        bottom_bar = Rect(
            MARGIN,
            field_view.bottom + MARGIN,
            panel.right - MARGIN,
            BOTTOM_BAR_HEIGHT,
        )
        window = Rect(
            0, 0, panel.right + MARGIN, bottom_bar.bottom + MARGIN
        )
        return Layout(window, top_bar, field_view, panel, bottom_bar)
