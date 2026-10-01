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
LEGEND_ROW = 18  # each legend row under the header (7d4)
LEFT = 58  # the y labels
BOTTOM = 24  # the x labels
RIGHT = 14
DOT = 4
DASH, DASH_GAP = 6, 4
LINE, DOTS, RING, LEVEL = "line", "dots", "ring", "level"
DASHED = "dashed"  # a line drawn in dashes (7d4: a skill trained on)


@dataclass
class Series:
    label: str
    points: list[tuple[float, float]]  # (x, y), sorted by x
    color: tuple
    style: str = LINE
    priority: int = 0  # the legend drops the highest first when it's full


@dataclass(frozen=True)
class Plot:
    """Where a chart drew: for finding what a click (or the mouse, for a
    tooltip) is on. `to_screen` is None when it had no data.
    """

    area: Rect
    to_screen: Callable[[float, float], tuple[float, float]] | None
    title: Rect  # the title's area (empty without a title)
    legend: list  # (Rect, series label) per legend item


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
    # Legend rows at most: past the header row, full-width rows under it
    # (as many as it needs), and the plot shrinks by them (7d4).
    legend_rows: int = 1

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


def plot_area(rect: Rect, extra_rows: int = 0) -> Rect:
    header = HEADER + extra_rows * LEGEND_ROW
    return Rect(
        rect.x + LEFT,
        rect.y + header + 6,
        rect.w - LEFT - RIGHT,
        rect.h - header - 6 - BOTTOM,
    )


def draw_chart(
    surface,
    rect: Rect,
    chart: Chart,
    mouse: tuple[int, int] | None = None,
    title: bool = True,
    reserved: int = 0,
) -> Plot:
    """The chart inside `rect` (its box border included), and where it
    drew. `title` False leaves `reserved` pixels of the title's place
    free, for a dropdown over it.
    """
    pygame.draw.rect(surface, theme.PANEL_BORDER, rect, 1)
    title_width = reserved
    title_rect = Rect(rect.x + 12, rect.y + 10, 0, 0)
    if title:
        title_rect = draw_text(
            surface,
            chart.title,
            (rect.x + 12, rect.y + 10),
            theme.HEADER_SIZE,
            theme.ACCENT,
            bold=True,
        )
        title_width = title_rect.w + 22  # room for its help marker
    left = rect.x + 12 + title_width + 16  # where the legend must stop
    rows = len(
        _legend_rows(_legend_items(chart, None), rect, left, chart.legend_rows)
    )
    area = plot_area(rect, rows - 1)
    if chart.empty:
        legend = _legend(surface, rect, chart, None, left, rows)
        draw_text(
            surface,
            "No data yet",
            area.center,
            theme.TEXT_SIZE,
            theme.TEXT_DIM,
            anchor="center",
        )
        return Plot(area, None, title_rect, legend)
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
    legend = _legend(surface, rect, chart, hovered, left, rows)
    return Plot(area, to_screen, title_rect, legend)


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
    elif series.style == DASHED:
        if len(screen) == 1:
            pygame.draw.circle(surface, series.color, screen[0], 2)
        for start, end in zip(screen, screen[1:]):
            _dashes(surface, series.color, start, end)
    elif series.style == DOTS:
        for point in screen:
            pygame.draw.circle(surface, series.color, point, DOT)
    elif series.style == RING:
        for point in screen:
            pygame.draw.circle(surface, series.color, point, DOT + 3, 2)


def _dashes(surface, color, start, end) -> None:
    """A line from `start` to `end` in dashes."""
    (x0, y0), (x1, y1) = start, end
    length = math.hypot(x1 - x0, y1 - y0)
    if not length:
        return
    step = DASH + DASH_GAP
    at = 0.0
    while at < length:
        stop = min(at + DASH, length)
        pygame.draw.line(
            surface,
            color,
            (x0 + (x1 - x0) * at / length, y0 + (y1 - y0) * at / length),
            (x0 + (x1 - x0) * stop / length, y0 + (y1 - y0) * stop / length),
            2,
        )
        at += step


def _legend_items(chart: Chart, hovered: dict | None) -> list:
    """(series, text) per legend item: each series with its latest value,
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
        items.append((series, (series.label + value).strip()))
    return items


def _item_width(item) -> int:
    series, text = item
    swatch = 18 if series else 0
    return get_font(theme.HEADER_SIZE).size(text)[0] + swatch + 16


def _fill(items: list, rect: Rect, left: int, rows: int, force: bool):
    """`items` in rows, placed from the last: the header row (right of
    `left`) first, then full-width rows under it. None if they don't fit
    (with `force`, the last row takes the rest).
    """
    found: list[list] = [[]]
    room = rect.right - 12 - left
    for item in reversed(items):
        width = _item_width(item)
        while width > room and found[-1]:
            if len(found) == rows:
                if not force:
                    return None
                break
            found.append([])
            room = rect.w - 24
        found[-1].insert(0, item)
        room -= width
    return found


def _legend_rows(items: list, rect: Rect, left: int, rows: int) -> list:
    """The items' rows. Past the last row there's no room: the
    highest-priority-number items go first.
    """
    items = list(items)
    while True:
        found = _fill(items, rect, left, rows, False)
        if found is not None:
            return found
        droppable = [i for i in items if i[0] and i[0].priority > 0]
        if not droppable:
            return _fill(items, rect, left, rows, True)
        items.remove(max(droppable, key=lambda i: i[0].priority))


def _legend(
    surface,
    rect: Rect,
    chart: Chart,
    hovered: dict | None,
    left: int,
    rows: int = 1,
) -> list:
    """Right-aligned in the header row (and the rows under it): each
    series with its latest value, or the hovered one.
    """
    font = get_font(theme.HEADER_SIZE)
    laid = _legend_rows(_legend_items(chart, hovered), rect, left, rows)
    drawn = []
    for row, items in enumerate(laid):
        x = rect.right - 12
        y = rect.y + 10 + font.get_height() // 2 + row * LEGEND_ROW
        for series, text in reversed(items):
            x -= font.size(text)[0]
            label = draw_text(
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
                swatch = Rect(x, label.y, 18, label.h)
                drawn.append((label.union(swatch), series.label))
            x -= 16
    return drawn


def _swatch(surface, series: Series, center: tuple[int, int]) -> None:
    x, y = center
    if series.style == LINE:
        pygame.draw.line(surface, series.color, (x - 6, y), (x + 6, y), 2)
    elif series.style in (LEVEL, DASHED):
        pygame.draw.line(surface, series.color, (x - 6, y), (x - 1, y))
        pygame.draw.line(surface, series.color, (x + 2, y), (x + 6, y))
    elif series.style == DOTS:
        pygame.draw.circle(surface, series.color, center, DOT)
    else:
        pygame.draw.circle(surface, series.color, center, DOT + 2, 2)
