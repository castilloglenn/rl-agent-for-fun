from dataclasses import dataclass

from pygame import Rect

MARGIN = 16
TOP_BAR_HEIGHT = 44  # one row: round, time, score, status, gauges
PLAYBACK_HEIGHT = 44  # under the field, in replays and the showcase
LEFT_WIDTH = 250  # the game: map, driver, setup, score, board, display
RIGHT_WIDTH = 260  # the car and its AI: car, senses, mind, reward


@dataclass(frozen=True)
class Layout:
    """Screen rects of the simulation window, derived from the field size.

    ┌──────┬──────────────────┬──────┐
    │ left │ top_bar          │right │
    │      ├──────────────────┤      │
    │      │ field_view       │      │
    │      ├──────────────────┤      │
    │      │ playback_bar     │      │  (replays and the showcase)
    └──────┴──────────────────┴──────┘

    On a stage bigger than the view, a map card (`map_box`) sits at the
    top of the left column, above the game's cards (7f10).
    """

    window: Rect
    top_bar: Rect
    field_view: Rect
    left_panel: Rect
    right_panel: Rect
    playback_bar: Rect | None = None
    map_box: Rect | None = None

    @staticmethod
    def for_field(
        field_width: float,
        field_height: float,
        playback: bool = False,
        map_height: int = 0,
    ) -> "Layout":
        width, height = int(field_width), int(field_height)
        side_height = TOP_BAR_HEIGHT + MARGIN + height
        if playback:
            side_height += MARGIN + PLAYBACK_HEIGHT
        left_panel = Rect(MARGIN, MARGIN, LEFT_WIDTH, side_height)
        top_bar = Rect(
            left_panel.right + MARGIN, MARGIN, width, TOP_BAR_HEIGHT
        )
        field_view = Rect(
            top_bar.x, top_bar.bottom + MARGIN, width, height
        )
        right_panel = Rect(
            field_view.right + MARGIN, MARGIN, RIGHT_WIDTH, side_height
        )
        map_box = None
        if map_height:
            map_box = Rect(left_panel.x, MARGIN, LEFT_WIDTH, map_height)
            left_panel = Rect(
                left_panel.x,
                map_box.bottom + MARGIN,
                LEFT_WIDTH,
                side_height - map_height - MARGIN,
            )
        playback_bar = None
        if playback:
            playback_bar = Rect(
                field_view.x,
                field_view.bottom + MARGIN,
                width,
                PLAYBACK_HEIGHT,
            )
        window = Rect(
            0, 0, right_panel.right + MARGIN, right_panel.bottom + MARGIN
        )
        return Layout(
            window,
            top_bar,
            field_view,
            left_panel,
            right_panel,
            playback_bar,
            map_box,
        )
