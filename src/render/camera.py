"""The field's camera (roadmap step 7b): how stage coordinates become
screen pixels. Drawing only: the simulation never sees it.

The field view is the box's size (855 x 480), so the car looks the same
on every stage. A stage that fits shows 1:1. A bigger one gets a map card
at the top right (the renderer's), the view grows as tall as the card,
and it has two modes (F switches):

    follow  1:1, centered on the car, stopping at the stage's edges (the
            default)
    fit     the whole stage, scaled down to the view: an overview
"""

from dataclasses import dataclass

from pygame import Rect

VIEW = (855, 480)  # px: the field view, the box's size
FIT, FOLLOW = "fit", "follow"
MAP_LONG_SIDE = 200  # px: the map card's drawing of a big stage
MAP_TOP = 34  # px: from the card's top to the map (under its header)
MAP_CARD_EXTRA = MAP_TOP + 14  # the card's height beyond the map's


def view_size(stage_width: float, stage_height: float) -> tuple[int, int]:
    """The field view's size: always VIEW (a smaller stage is centered
    in it, a bigger one is followed or fitted).
    """
    return VIEW


def map_size(stage_width: float, stage_height: float):
    """The map card's drawing size for a stage bigger than the view
    (its long side MAP_LONG_SIDE), or None for one that fits.
    """
    if fit_scale(stage_width, stage_height) >= 1.0:
        return None
    s = MAP_LONG_SIDE / max(stage_width, stage_height)
    return round(stage_width * s), round(stage_height * s)


def fit_scale(stage_width: float, stage_height: float, view=VIEW) -> float:
    """1.0 when the stage fits the view, else the scale that fits it."""
    return min(1.0, view[0] / stage_width, view[1] / stage_height)


@dataclass
class Camera:
    stage_width: float
    stage_height: float
    view: Rect  # the field view on screen
    fit: float = 1.0  # the fit mode's scale
    mode: str = FIT
    origin: tuple[float, float] = (0.0, 0.0)  # follow: the view's top left

    @staticmethod
    def for_stage(
        stage_width: float, stage_height: float, view: Rect
    ) -> "Camera":
        """Follow for a stage bigger than the view, else 1:1."""
        scale = fit_scale(stage_width, stage_height, view.size)
        mode = FOLLOW if scale < 1.0 else FIT
        return Camera(stage_width, stage_height, view, scale, mode)

    @property
    def zoomable(self) -> bool:
        """The stage is bigger than the view: fit and follow differ."""
        return self.fit < 1.0

    @property
    def scale(self) -> float:
        return 1.0 if self.mode == FOLLOW else self.fit

    def toggle(self) -> None:
        if self.zoomable:
            self.mode = FOLLOW if self.mode == FIT else FIT

    def follow(self, x: float, y: float) -> None:
        """Follow mode: center on (x, y), stopping at the stage's edges
        (an axis where the stage fits the view stays centered).
        """
        if self.mode != FOLLOW:
            self.origin = (0.0, 0.0)
            return
        width, height = self.view.w, self.view.h
        self.origin = (
            min(max(x - width / 2, 0.0), max(self.stage_width - width, 0.0)),
            min(
                max(y - height / 2, 0.0),
                max(self.stage_height - height, 0.0),
            ),
        )

    @property
    def pad(self) -> tuple[float, float]:
        """Screen px from the view's corner to the stage, on an axis where
        the stage (at this scale) is smaller than the view: it's centered.
        """
        s = self.scale
        return (
            max((self.view.w - self.stage_width * s) / 2, 0.0),
            max((self.view.h - self.stage_height * s) / 2, 0.0),
        )

    def to_screen(self, x: float, y: float) -> tuple[float, float]:
        s = self.scale
        ox, oy = self.origin
        px, py = self.pad
        return (
            self.view.x + px + (x - ox) * s,
            self.view.y + py + (y - oy) * s,
        )

    def to_world(self, sx: float, sy: float) -> tuple[float, float]:
        s = self.scale
        ox, oy = self.origin
        px, py = self.pad
        return (
            (sx - self.view.x - px) / s + ox,
            (sy - self.view.y - py) / s + oy,
        )

    def label(self) -> str:
        """For the DISPLAY card."""
        if not self.zoomable:
            return "1:1"
        if self.mode == FOLLOW:
            return "follow"
        return f"fit {self.fit:.0%}"
