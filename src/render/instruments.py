"""The side panel's instruments (7f3, decision 059): what changes every
frame is drawn as a shape your eye reads at a glance (a speed bar, a
steering slider, a heading dial, a sensor radar, a checkpoint arrow), and
the few numbers left are steady: each shows its mean over the last
quarter second, redrawn 4 times a second. Display only: the simulation,
the agent's observation, and replays never see any of it.
"""

import math

import pygame
from pygame import Rect

from src.render import theme, warnings
from src.utils.ui import draw_text

REFRESH_MS = 250  # a number is redrawn this often (4 times a second)
RADAR_RANGE = 300.0  # px: a spoke this long or longer is full length
DIM_SPOKE = (70, 74, 84)  # a ray that sees nothing near


class Readouts:
    """Steady numbers: each key's value is averaged until its text is due
    again, then shown until the next refresh. `mean=False` holds the
    latest value instead (an angle, where a mean of 359 and 1 is wrong).
    """

    def __init__(self) -> None:
        self._sums: dict[str, list[float]] = {}
        self._shown: dict[str, tuple[str, int]] = {}
        self._peaks: dict[str, float] = {}

    def peak(self, key: str, value: float) -> float:
        """The largest size `value` has had so far: a gauge's scale."""
        found = max(self._peaks.get(key, 0.0), abs(value), 1e-6)
        self._peaks[key] = found
        return found

    def text(
        self,
        key: str,
        value: float,
        fmt,
        now: int | None = None,
        mean: bool = True,
    ) -> str:
        now = pygame.time.get_ticks() if now is None else now
        total = self._sums.setdefault(key, [0.0, 0])
        total[0] += value
        total[1] += 1
        shown = self._shown.get(key)
        if shown is None or now - shown[1] >= REFRESH_MS:
            show = total[0] / total[1] if mean else value
            self._shown[key] = (fmt(show), now)
            self._sums[key] = [0.0, 0]
        return self._shown[key][0]


def ray_label(name: str) -> str:
    """front_left_15 -> "front-left 15°", back_left -> "back-left"."""
    side, _, angle = name.rpartition("_")
    if angle.isdigit():
        return f"{side.replace('_', '-')} {angle}°"
    return name.replace("_", "-")


def draw_speed_bar(
    surface, rect: Rect, speed: float, max_speed: float, max_reverse: float,
    level: int,
) -> None:
    """Zero sits where reverse's share ends: forward fills right (colored
    by how safe the speed is), reversing fills left in red.
    """
    pygame.draw.rect(surface, theme.BAR_EMPTY, rect)
    span = max_speed + max_reverse
    zero = rect.x + round(rect.w * max_reverse / span)
    if speed > 0:
        width = round((rect.right - zero) * min(speed / max_speed, 1.0))
        color = {
            warnings.CAUTION: theme.WARN,
            warnings.DANGER: theme.BAD,
        }.get(level, theme.ACCENT)
        pygame.draw.rect(surface, color, Rect(zero, rect.y, width, rect.h))
    elif speed < 0:
        width = round((zero - rect.x) * min(-speed / max_reverse, 1.0))
        pygame.draw.rect(
            surface, theme.BAD, Rect(zero - width, rect.y, width, rect.h)
        )
    pygame.draw.line(
        surface, theme.TEXT, (zero, rect.y - 2), (zero, rect.bottom + 1)
    )


def draw_segments(surface, rect: Rect, parts) -> None:
    """A bar split into (share, color) parts, left to right."""
    pygame.draw.rect(surface, theme.BAR_EMPTY, rect)
    x = rect.x
    for share, color in parts:
        width = round(rect.w * share)
        if width > 0:
            pygame.draw.rect(surface, color, Rect(x, rect.y, width, rect.h))
        x += width


def draw_center_gauge(surface, rect: Rect, share: float) -> None:
    """A bar filled from its middle: right (green) for good, left (red)
    for bad; `share` from -1 to 1.
    """
    pygame.draw.rect(surface, theme.BAR_EMPTY, rect)
    middle = rect.centerx
    width = round(rect.w / 2 * min(abs(share), 1.0))
    if share > 0:
        fill = Rect(middle, rect.y, width, rect.h)
        pygame.draw.rect(surface, theme.GOOD, fill)
    elif share < 0:
        pygame.draw.rect(
            surface, theme.BAD, Rect(middle - width, rect.y, width, rect.h)
        )
    pygame.draw.line(
        surface, theme.TEXT, (middle, rect.y - 2), (middle, rect.bottom + 1)
    )


def draw_slider(surface, rect: Rect, steering: float) -> None:
    """The steering wheel: the dot left of center turns left."""
    y = rect.centery
    pygame.draw.line(
        surface, theme.PANEL_BORDER, (rect.x, y), (rect.right, y), 2
    )
    pygame.draw.line(
        surface, theme.TEXT_DIM, (rect.centerx, y - 4), (rect.centerx, y + 4)
    )
    x = rect.centerx - steering * (rect.w / 2)
    color = theme.ACCENT if steering else theme.TEXT_DIM
    pygame.draw.circle(surface, color, (round(x), y), 5)


def draw_dial(surface, center: tuple[int, int], radius: int, angle: float):
    """A heading dial: the needle points where the car faces (0 = east,
    counterclockwise, as on the field).
    """
    pygame.draw.circle(surface, theme.PANEL_BORDER, center, radius, 1)
    rad = math.radians(angle)
    tip = (
        center[0] + math.cos(rad) * (radius - 1),
        center[1] - math.sin(rad) * (radius - 1),
    )
    pygame.draw.line(surface, theme.ACCENT, center, tip, 2)


def draw_arrow(
    surface, center: tuple[int, int], size: int, relative: float, color
) -> None:
    """A triangle pointing `relative` degrees from straight up (ahead),
    counterclockwise: + is to the car's left.
    """
    rad = math.radians(relative)
    forward = (-math.sin(rad), -math.cos(rad))
    side = (-forward[1], forward[0])
    cx, cy = center
    points = [
        (cx + forward[0] * size, cy + forward[1] * size),
        (
            cx - forward[0] * size * 0.6 + side[0] * size * 0.6,
            cy - forward[1] * size * 0.6 + side[1] * size * 0.6,
        ),
        (
            cx - forward[0] * size * 0.6 - side[0] * size * 0.6,
            cy - forward[1] * size * 0.6 - side[1] * size * 0.6,
        ),
    ]
    pygame.draw.polygon(surface, color, points)


def draw_radar(
    surface,
    center: tuple[int, int],
    radius: int,
    rays: list,
    levels: dict,
    speed: float,
    stop_distance: float,
) -> tuple[str, float] | None:
    """The car from above, facing up, a spoke per ray at its angle: as
    long as the way is clear (up to RADAR_RANGE px), colored by danger;
    and the stopping distance as an arc in the direction of travel.
    Returns the closest ray (name, px).
    """
    pygame.draw.circle(surface, theme.PANEL_BORDER, center, radius, 1)
    if speed and stop_distance > 0:
        reach = radius * min(stop_distance / RADAR_RANGE, 1.0)
        start = math.radians(45 if speed > 0 else 225)
        arc = Rect(0, 0, 2 * reach, 2 * reach)
        arc.center = center
        pygame.draw.arc(
            surface, theme.ACCENT, arc, start, start + math.radians(90), 1
        )
    closest = None
    for ray in rays:
        rad = math.radians(ray.angle)
        dx, dy = -math.sin(rad), -math.cos(rad)
        share = min(ray.distance / RADAR_RANGE, 1.0)
        reach = radius * share
        end = (center[0] + dx * reach, center[1] + dy * reach)
        level = levels.get(ray.name, warnings.NORMAL)
        color = {
            warnings.CAUTION: theme.WARN,
            warnings.DANGER: theme.BAD,
        }.get(level, theme.TEXT if share < 1 else DIM_SPOKE)
        pygame.draw.line(surface, color, center, end, 2)
        pygame.draw.circle(surface, color, (round(end[0]), round(end[1])), 3)
        if closest is None or ray.distance < closest[1]:
            closest = (ray.name, ray.distance)
    body = Rect(0, 0, 9, 15)
    body.center = center
    pygame.draw.rect(surface, theme.ACCENT, body)
    nose = (center[0], body.top), (center[0], body.top + 4)
    pygame.draw.line(surface, theme.TEXT, *nose, 2)
    return closest


def draw_label(surface, column, text: str) -> None:
    draw_text(
        surface, text, (column.left, column.y), theme.TEXT_SIZE, theme.TEXT_DIM
    )
