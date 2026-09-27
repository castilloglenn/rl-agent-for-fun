"""Line charts for the control center (roadmap step 6b1), drawn by hand in
the game window's style: dark, thin gray grid, the accent color.

A chart has series: a line, dots (for example the suite score at each
checkpoint), a ring (the best checkpoint), or a level (a dashed line
across, for example the heuristic's score). Hovering reads out the
nearest point of each series.
"""

import math
from bisect import bisect_left
from dataclasses import dataclass, field
from typing import Callable

import pygame
from pygame import Rect

from src.render import theme
from src.utils.ui import draw_text, get_font

GRID = (26, 27, 32)  # fainter than the box borders
HEADER = 30  # the title and legend row
LEFT = 58  # the y labels
BOTTOM = 24  # the x labels
RIGHT = 14
DOT = 4
DASH, DASH_GAP = 6, 4
LINE, DOTS, RING, LEVEL = "line", "dots", "ring", "level"


@dataclass
class Series:
    label: str
    points: list[tuple[float, float]]  # (x, y), sorted by x
    color: tuple
    style: str = LINE


@dataclass
class Chart:
    title: str
    series: list[Series]
    x_label: str  # the hovered x: "{} decisions", "epoch {}"
    x_format: Callable[[float], str] = field(default=lambda v: compact(v))
    y_format: Callable[[float], str] = field(default=lambda v: compact(v))
    # The legend's values: exact, where the axes round.
    value_format: Callable[[float], str] = field(
        default=lambda v: readable(v)
    )

    @property
    def empty(self) -> bool:
        return not any(s.points for s in self.series if s.style != LEVEL)


def compact(value: float) -> str:
    """Short numbers for axes: 5,347 -> 5.3k, 2,000,000 -> 2M."""
    size = abs(value)
    for limit, suffix in ((1e6, "M"), (1e3, "k")):
        if size >= limit:
            text = f"{value / limit:.1f}".rstrip("0").rstrip(".")
            return text + suffix
    if size >= 10 or value == int(value):
        return f"{value:,.0f}"
    if size >= 0.1:
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return f"{value:.3g}"


def readable(value: float) -> str:
    """4,412 and 2.46: whole numbers from 100 up."""
    if abs(value) >= 100:
        return f"{value:,.0f}"
    return compact(value)


def percent(value: float) -> str:
    return f"{value:.0%}"


def nice_ticks(low: float, high: float, count: int = 5) -> list[float]:
    """Round tick values covering [low, high]: 0, 2k, 4k, ..."""
    if high <= low:  # flat data: a band around it
        pad = abs(low) * 0.1 or 1.0
        low, high = low - pad, high + pad
    raw = (high - low) / max(count - 1, 1)
    magnitude = 10 ** math.floor(math.log10(raw))
    step = next(
        m * magnitude for m in (1, 2, 2.5, 5, 10) if m * magnitude >= raw
    )
    first = math.floor(low / step + 1e-9)  # 0.3 / 0.1 is 2.999...
    last = math.ceil(high / step - 1e-9)
    return [round(i * step, 10) for i in range(first, last + 1)]


def plot_area(rect: Rect) -> Rect:
    return Rect(
        rect.x + LEFT,
        rect.y + HEADER + 6,
        rect.w - LEFT - RIGHT,
        rect.h - HEADER - 6 - BOTTOM,
    )


def draw_chart(
    surface,
    rect: Rect,
    chart: Chart,
    mouse: tuple[int, int] | None = None,
    title: bool = True,
) -> None:
    """The chart inside `rect` (its box border included). `title` False
    leaves the title's place free, for a dropdown over it.
    """
    pygame.draw.rect(surface, theme.PANEL_BORDER, rect, 1)
    if title:
        draw_text(
            surface,
            chart.title,
            (rect.x + 12, rect.y + 10),
            theme.HEADER_SIZE,
            theme.ACCENT,
            bold=True,
        )
    area = plot_area(rect)
    if chart.empty:
        _legend(surface, rect, chart, None)
        draw_text(
            surface,
            "No data yet",
            area.center,
            theme.TEXT_SIZE,
            theme.TEXT_DIM,
            anchor="center",
        )
        return
    xs = [x for s in chart.series if s.style != LEVEL for x, _ in s.points]
    ys = [y for s in chart.series for _, y in s.points]
    x_low, x_high = min(xs), max(xs)
    if x_high <= x_low:
        x_high = x_low + 1
    y_ticks = nice_ticks(min(ys), max(ys))
    y_low, y_high = y_ticks[0], y_ticks[-1]

    def to_screen(x: float, y: float) -> tuple[float, float]:
        sx = area.x + (x - x_low) / (x_high - x_low) * area.w
        sy = area.bottom - (y - y_low) / (y_high - y_low) * area.h
        return sx, sy

    # The grid and the axes' labels.
    for tick in y_ticks:
        _, y = to_screen(x_low, tick)
        pygame.draw.line(surface, GRID, (area.x, y), (area.right, y))
        draw_text(
            surface,
            chart.y_format(tick),
            (area.x - 8, y),
            theme.HEADER_SIZE,
            theme.TEXT_DIM,
            anchor="midright",
        )
    for tick in nice_ticks(x_low, x_high, 6):
        if not x_low <= tick <= x_high:
            continue
        x, _ = to_screen(tick, y_low)
        pygame.draw.line(surface, GRID, (x, area.y), (x, area.bottom))
        draw_text(
            surface,
            chart.x_format(tick),
            (x, area.bottom + 5),
            theme.HEADER_SIZE,
            theme.TEXT_DIM,
            anchor="midtop",
        )
    pygame.draw.rect(surface, theme.PANEL_BORDER, area, 1)

    surface.set_clip(area.inflate(2 * DOT + 4, 2 * DOT + 4))
    for series in chart.series:
        _draw_series(surface, series, to_screen, area)
    surface.set_clip(None)

    # Hovering: a line at the mouse, and each series' nearest point.
    hovered = None
    if mouse and area.collidepoint(mouse):
        x_value = x_low + (mouse[0] - area.x) / area.w * (x_high - x_low)
        pygame.draw.line(
            surface, theme.TEXT_DIM, (mouse[0], area.y), (mouse[0], area.bottom)
        )
        hovered = {}
        # The x of the nearest real point, not the mouse's in-between one.
        first = next(
            (s for s in chart.series if s.style != LEVEL and s.points), None
        )
        if first:
            x_value = nearest(first, x_value)[0]
        for series in chart.series:
            point = nearest(series, x_value)
            if point is None:
                continue
            hovered[series.label] = point
            if series.style != LEVEL:
                pygame.draw.circle(
                    surface, theme.TEXT, to_screen(*point), DOT + 1, 1
                )
        hovered["_x"] = x_value
    _legend(surface, rect, chart, hovered)


def nearest(series: Series, x: float) -> tuple[float, float] | None:
    """The point of `series` closest to `x` (a level: its value)."""
    points = series.points
    if not points:
        return None
    if series.style == LEVEL:
        return points[0]
    i = bisect_left([p[0] for p in points], x)
    near = [p for p in points[max(i - 1, 0) : i + 1]]
    return min(near, key=lambda p: abs(p[0] - x))


def _draw_series(surface, series: Series, to_screen, area: Rect) -> None:
    if not series.points:
        return
    if series.style == LEVEL:
        _, y = to_screen(0, series.points[0][1])
        x = area.x
        while x < area.right:
            end = min(x + DASH, area.right)
            pygame.draw.line(surface, series.color, (x, y), (end, y))
            x += DASH + DASH_GAP
        return
    screen = [to_screen(x, y) for x, y in series.points]
    if series.style == LINE:
        if len(screen) > 1:
            pygame.draw.lines(surface, series.color, False, screen, 2)
        else:
            pygame.draw.circle(surface, series.color, screen[0], 2)
    elif series.style == DOTS:
        for point in screen:
            pygame.draw.circle(surface, series.color, point, DOT)
    elif series.style == RING:
        for point in screen:
            pygame.draw.circle(surface, series.color, point, DOT + 3, 2)


def _legend(surface, rect: Rect, chart: Chart, hovered: dict | None) -> None:
    """Right-aligned in the header row: each series with its latest value,
    or the hovered one. Hovering also shows the x value first.
    """
    items = []
    if hovered:
        x = hovered["_x"]
        text = f"{x:,.0f}" if x < 1e4 else chart.x_format(x)
        items.append((None, chart.x_label.format(text)))
    for series in chart.series:
        if not series.points:
            continue
        if hovered is not None:
            point = hovered.get(series.label)
        else:
            point = series.points[-1]
        value = "" if point is None else f" {chart.value_format(point[1])}"
        items.append((series, series.label + value))
    font = get_font(theme.HEADER_SIZE)
    x = rect.right - 12
    y = rect.y + 10 + font.get_height() // 2
    for series, text in reversed(items):
        width = font.size(text)[0]
        x -= width
        draw_text(
            surface,
            text,
            (x, y),
            theme.HEADER_SIZE,
            theme.TEXT if series else theme.TEXT_DIM,
            anchor="midleft",
        )
        if series:
            x -= 18
            _swatch(surface, series, (x + 6, y))
        x -= 16


def _swatch(surface, series: Series, center: tuple[int, int]) -> None:
    x, y = center
    if series.style == LINE:
        pygame.draw.line(surface, series.color, (x - 6, y), (x + 6, y), 2)
    elif series.style == LEVEL:
        pygame.draw.line(surface, series.color, (x - 6, y), (x - 1, y))
        pygame.draw.line(surface, series.color, (x + 2, y), (x + 6, y))
    elif series.style == DOTS:
        pygame.draw.circle(surface, series.color, center, DOT)
    else:
        pygame.draw.circle(surface, series.color, center, DOT + 2, 2)
