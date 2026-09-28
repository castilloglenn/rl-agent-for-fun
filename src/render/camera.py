"""The field's camera (roadmap step 7b): how stage coordinates become
screen pixels. Drawing only: the simulation never sees it.

A stage that fits the largest field view (`window.max_field`) shows 1:1,
exactly as before. A bigger one gets a view of that size, and two modes
(F switches):

    fit     the whole stage, scaled down to the view
    follow  1:1, centered on the car, stopping at the stage's edges
"""

from dataclasses import dataclass

from pygame import Rect

MAX_FIELD = (1100, 640)  # px: the largest field view
# The smallest field view (the box's size): the top bar above it needs
# the width. A narrower fitted stage is centered in it.
MIN_FIELD = (855, 480)
FIT, FOLLOW = "fit", "follow"


def view_size(
    stage_width: float, stage_height: float, max_field=MAX_FIELD
) -> tuple[int, int]:
    """The field view's size: the stage's, scaled down to fit, and at
    least MIN_FIELD.
    """
    scale = fit_scale(stage_width, stage_height, max_field)
    return (
        max(round(stage_width * scale), MIN_FIELD[0]),
        max(round(stage_height * scale), MIN_FIELD[1]),
    )


def fit_scale(
    stage_width: float, stage_height: float, max_field=MAX_FIELD
) -> float:
    """1.0 when the stage fits, else the scale that fits it."""
    return min(
        1.0, max_field[0] / stage_width, max_field[1] / stage_height
    )


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
        stage_width: float, stage_height: float, view: Rect, max_field
    ) -> "Camera":
        scale = fit_scale(stage_width, stage_height, max_field)
        return Camera(stage_width, stage_height, view, scale)

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
