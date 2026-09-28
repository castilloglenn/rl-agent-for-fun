"""HUD panels around the field: top bar, side panel, bottom bar.

Retro style: only lines and text, with colors and bold for distinction.
Graphics belong inside the field.

Sections for features that don't exist yet (round, score, checkpoints,
rewards, agent) show a dash. Their roadmap steps fill them in.
"""

import math
from dataclasses import dataclass, field

from ml_collections import ConfigDict

import pygame
from pygame import Rect, Surface

from src.ecs import World
from src.render import theme, warnings
from src.render.layout import MARGIN
from src.sim.components import (
    ActionInput,
    Checkpoint,
    Eliminated,
    Health,
    Motion,
    Ray,
    Renderable,
    Score,
    Sensors,
    Transform,
)
from src.sim.resources import (
    EventLog,
    Rng,
    RoundState,
    SimClock,
    SimConfig,
)
from src.sim.rules import Rules
from src.sim.stage import Stage
from src.utils.types import ColorValue
from src.utils.ui import draw_text, get_font

DASH = "—"
PADDING = 14
CARD_GAP = MARGIN  # between boxes, the same as around them


@dataclass(frozen=True)
class ModeInfo:
    """A window mode other than live play (for example a replay): a label
    for the top bar, the bottom bar's key hints, and messages for the
    field. The renderer shows it without knowing what the mode is.
    """

    label: str
    label_color: ColorValue
    shortcuts: tuple[tuple[str, str], ...]  # (key, what it does), for "?"
    messages: tuple[tuple[str, ColorValue], ...] = ()
    playback: "PlaybackInfo | None" = None  # replays: the control bar
    # Replays: where the car has been, oldest first (T shows it).
    trail: tuple[tuple[float, float], ...] | list | None = None


@dataclass(frozen=True)
class PlaybackInfo:
    """What the playback control bar shows (replays, the showcase)."""

    speed: float
    speeds: tuple[float, ...]
    paused: bool
    position: float  # seconds into the round
    length: float  # seconds the round lasts


# Live play's keys, shown by "?" when no mode is active.
LIVE_SHORTCUTS = (
    ("W A S D / arrows", "drive"),
    ("SPACE", "brake"),
    ("P", "pause / resume"),
    ("R", "restart"),
    ("H", "lines"),
    ("?", "these shortcuts"),
    ("Esc", "quit (asks first)"),
)


@dataclass(frozen=True)
class RewardStatus:
    """The agent reward, from the env (it isn't part of the simulation)."""

    profile: str  # reward profile name
    last: float  # reward of the latest step
    total: float  # summed over this game
    # Each term's weight x value, summed over this game (they add up to
    # total), and the profile's weights.
    terms: dict = field(default_factory=dict)
    weights: dict = field(default_factory=dict)


@dataclass
class CarInfo:
    label: str
    speed: float  # px/s, negative while reversing
    pedal: str
    steering: float  # -1 full right .. +1 full left
    heading: float  # degrees
    center: tuple[float, float]
    action: ActionInput
    rays: list[Ray]
    eliminated: bool
    score: Score
    health: float  # 0 (wrecked) .. 1 (full)


def car_infos(world: World) -> list[CarInfo]:
    config = world.resource(SimConfig)
    return [
        CarInfo(
            label=renderable.label,
            speed=motion.speed * config.steps_per_second,
            pedal=motion.pedal,
            steering=motion.steering,
            heading=transform.angle,
            center=(transform.x, transform.y),
            action=action,
            rays=sensors.rays,
            eliminated=world.try_component(car, Eliminated) is not None,
            score=score,
            health=health.share,
        )
        for car, (
            renderable,
            motion,
            transform,
            action,
            sensors,
            score,
            health,
        ) in world.query(
            Renderable, Motion, Transform, ActionInput, Sensors, Score, Health
        )
    ]


DIRECTIONS = (
    "ahead",
    "ahead-left",
    "left",
    "behind-left",
    "behind",
    "behind-right",
    "right",
    "ahead-right",
)


def health_color(share: float) -> ColorValue:
    if share > 0.6:
        return theme.GOOD
    if share >= 0.3:
        return theme.WARN
    return theme.BAD


def nearest_checkpoint(
    world: World, car: CarInfo
) -> tuple[float, str] | None:
    """Distance (center to center) and direction, relative to the car's
    heading, of the nearest checkpoint.
    """
    spots = [spot for _, (spot, _) in world.query(Transform, Checkpoint)]
    if not spots:
        return None
    x, y = car.center
    spot = min(spots, key=lambda s: math.dist((s.x, s.y), (x, y)))
    bearing = math.degrees(math.atan2(-(spot.y - y), spot.x - x))
    relative = (bearing - car.heading) % 360
    direction = DIRECTIONS[int((relative + 22.5) // 45) % 8]
    return math.dist((spot.x, spot.y), (x, y)), direction


def format_time(seconds: float) -> str:
    minutes, seconds = divmod(max(seconds, 0.0), 60)
    return f"{int(minutes):02d}:{seconds:04.1f}"


def seconds_left(world: World) -> float:
    state = world.resource(RoundState)
    return state.steps_left / world.resource(SimConfig).steps_per_second


def _box(surface: Surface, rect: Rect) -> None:
    pygame.draw.rect(surface, theme.PANEL_BORDER, rect, 1)


# Top bar


def draw_top_bar(
    surface: Surface,
    rect: Rect,
    world: World,
    car: CarInfo | None,
    hud: ConfigDict,
) -> None:
    """One row of essentials: the car's gauges on the left (fuel joins in
    step 9), and round, time, score, and the car's status on the right.
    """
    _box(surface, rect)
    y = rect.y + (rect.height - theme.BIG_SIZE) // 2 - 2
    if car is not None:
        draw_gauge(surface, "HEALTH", car.health, rect.x + PADDING, y)

    state = world.resource(RoundState)
    time_left = seconds_left(world)
    items = [
        ("ROUND", f"{state.number}/{state.total}", warnings.NORMAL),
        ("TIME", format_time(time_left), warnings.time_level(time_left, hud)),
        ("SCORE", f"{car.score.total:,.0f}" if car else DASH, warnings.NORMAL),
    ]
    status = car_status(car) if car is not None else None
    # Measured first, so the group ends at the right edge.
    label_font = get_font(theme.HEADER_SIZE)
    value_font = get_font(theme.BIG_SIZE, True)
    widths = [
        label_font.size(label)[0] + 8 + value_font.size(value)[0]
        for label, value, _ in items
    ]
    total = sum(widths) + 28 * (len(items) - 1)
    if status:  # a fixed slot: a changing status never moves the rest
        status_font = get_font(theme.TEXT_SIZE, True)
        total += 28 + max(status_font.size(text)[0] for text in STATUSES)
    x = rect.right - PADDING - total
    for (label, value, level), width in zip(items, widths):
        label_rect = draw_text(
            surface, label, (x, y + 3), theme.HEADER_SIZE, theme.TEXT_DIM
        )
        draw_text(
            surface,
            value,
            (label_rect.right + 8, y),
            theme.BIG_SIZE,
            warnings.value_color(level),
            bold=True,
        )
        x += width + 28
    if status:
        text, color = status
        draw_text(surface, text, (x, y + 2), theme.TEXT_SIZE, color, True)


STATUSES = ("DRIVING", "REVERSING", "STOPPED", "WRECKED")


def car_status(car: CarInfo) -> tuple[str, ColorValue]:
    if car.eliminated:
        return "WRECKED", theme.BAD
    if car.speed > 0:
        return "DRIVING", theme.GOOD
    if car.speed < 0:
        return "REVERSING", theme.GOOD
    return "STOPPED", theme.WARN


def draw_gauge(
    surface: Surface,
    label: str,
    share: float,
    left: float,
    y: float,
    blocks: int = 10,
) -> Rect:
    """A retro gauge starting at `left`: label, filled blocks, and a
    percentage. Green above 60 %, amber from 30 %, red below. Returns its
    area.
    """
    color = health_color(share)
    label_rect = draw_text(
        surface, label, (left, y + 3), theme.HEADER_SIZE, theme.TEXT_DIM
    )
    filled = max(round(share * blocks), 1 if share > 0 else 0)
    size, gap = 10, 3
    start = label_rect.right + 8
    top = y + 6
    for i in range(blocks):
        pygame.draw.rect(
            surface,
            color if i < filled else theme.BAR_EMPTY,
            Rect(start + i * (size + gap), top, size, size),
        )
    value = draw_text(
        surface,
        f"{share:.0%}",
        (start + blocks * (size + gap) - gap + 10, y + 2),
        theme.TEXT_SIZE,
        color,
        bold=True,
    )
    return label_rect.union(value)


def _fit(text: str, width: float, size: int, bold: bool = False) -> str:
    """`text`, shortened with "…" to fit `width` pixels."""
    font = get_font(size, bold)
    if font.size(text)[0] <= width:
        return text
    while text and font.size(text + "…")[0] > width:
        text = text[:-1]
    return text + "…" if text else ""


def round_details(
    world: World, reward: RewardStatus | None = None
) -> list[tuple[str, str]]:
    """Which stage, seed, and reward profile this round runs on."""
    stage = world.resource(Stage)
    details = [
        ("STAGE", f"{stage.name} {stage.width:g}×{stage.height:g}"),
        ("RULES", world.resource(Rules).name),
        ("SPAWNS", stage.checkpoints.mode),
        ("SEED", str(world.resource(Rng).seed)),
    ]
    if reward:
        details.append(("REWARD", reward.profile))
    return details


# Side panel


class _Column:
    """Draws panel sections top to bottom, each in its own box (a card),
    with a gap between them.
    """

    def __init__(self, surface: Surface, rect: Rect) -> None:
        self.surface = surface
        self.rect = rect
        self.left = rect.x + PADDING
        self.right = rect.right - PADDING
        self.y = rect.y
        self.card_top: int | None = None

    def header(self, title: str) -> None:
        """Starts a section: closes the previous card, opens a new one."""
        self.finish()
        self.card_top = self.y
        self.y += 10
        draw_text(
            self.surface,
            title,
            (self.left, self.y),
            theme.HEADER_SIZE,
            theme.ACCENT,
            bold=True,
        )
        self.y += theme.LINE_HEIGHT

    def row(
        self,
        label: str,
        value: str,
        level: int = warnings.NORMAL,
        colors: tuple | None = None,
        indent: int = 0,
    ) -> None:
        """label ... value. `colors`: (label, value) instead of the
        level's. `indent`: px, for a row under another.
        """
        font = get_font(theme.TEXT_SIZE)
        left = self.left + indent
        width = self.right - left
        # The value keeps at least half the row, then the label fits.
        label_width = min(font.size(label)[0], width // 2)
        value = _fit(value, width - label_width - 12, theme.TEXT_SIZE)
        label = _fit(label, width - font.size(value)[0] - 12, theme.TEXT_SIZE)
        label_color, value_color = colors or (
            warnings.label_color(level),
            warnings.value_color(level),
        )
        draw_text(
            self.surface,
            label,
            (left, self.y),
            theme.TEXT_SIZE,
            label_color,
        )
        draw_text(
            self.surface,
            value,
            (self.right, self.y),
            theme.TEXT_SIZE,
            value_color,
            anchor="topright",
        )
        self.y += theme.LINE_HEIGHT

    def note(
        self, text: str, color: ColorValue = theme.TEXT_DIM, bold=False
    ) -> None:
        draw_text(
            self.surface,
            _fit(text, self.right - self.left, theme.TEXT_SIZE, bold),
            (self.left, self.y),
            theme.TEXT_SIZE,
            color,
            bold=bold,
        )
        self.y += theme.LINE_HEIGHT

    def gap(self) -> None:
        """The end of a section (finish draws its card)."""

    def finish(self) -> None:
        """Draws the open card's box around what was drawn in it."""
        if self.card_top is None:
            return
        bottom = self.y + 6  # rows leave ~5 px under their text
        _box(
            self.surface,
            Rect(
                self.rect.x,
                self.card_top,
                self.rect.width,
                bottom - self.card_top,
            ),
        )
        self.y = bottom + CARD_GAP
        self.card_top = None


def draw_game_panel(
    surface: Surface,
    rect: Rect,
    world: World,
    cars: list[CarInfo],
    reward: RewardStatus | None = None,
    mode: ModeInfo | None = None,
) -> None:
    """Left: who's playing, which game, and how it's going."""
    column = _Column(surface, rect)
    car = cars[0] if cars else None

    column.header("DRIVER")
    column.note(car.label if car else DASH, theme.TEXT, bold=True)
    if mode:
        column.note(mode.label, mode.label_color, bold=True)
    else:
        column.note("Live play")
    column.gap()

    column.header("GAME")
    for label, value in round_details(world):
        column.row(label.capitalize(), value)

    column.header("SCORE (game points)")
    if car:
        column.row("Distance", f"+{car.score.distance_points:,.0f}")
        column.row("Checkpoints", f"+{car.score.checkpoint_points:,.0f}")

    column.header("LEADERBOARD")
    ranked = sorted(cars, key=lambda info: -info.score.total)
    for rank, info in enumerate(ranked, start=1):
        column.row(f"{rank}  {info.label}", f"{info.score.total:,.0f}")

    # What an agent learns from, and the simulation it steps through.
    column.header("AGENT")
    if reward:
        column.row("Reward profile", reward.profile)
        column.row("Reward this game", f"{reward.total:+,.2f}")
    else:
        column.note("No reward profile")
    column.row("Step", f"{world.resource(SimClock).step:,}")
    sim_rate = world.resource(SimConfig).steps_per_second
    column.row("Sim rate", f"{sim_rate} steps/s")
    column.finish()


def reward_groups(reward: RewardStatus) -> tuple[list, list]:
    """(gains, costs): (term, total) pairs, biggest first. A term goes by
    the sign of its sum so far (0: by its weight's sign).
    """
    gains, costs = [], []
    for term, total in reward.terms.items():
        weight = reward.weights.get(term, 0.0)
        if total > 0 or (total == 0 and weight >= 0):
            gains.append((term, total))
        else:
            costs.append((term, total))
    gains.sort(key=lambda t: -t[1])
    costs.sort(key=lambda t: t[1])
    return gains, costs


def draw_reward_bar(
    surface: Surface, rect: Rect, reward: RewardStatus
) -> None:
    """The agent reward by term, under the field (decision 032), in one
    line:

        REWARD default   GAINS +3,901.0 points +3,901.0
        COSTS -1,480.0 contact -1,200.0 · damage -250.0 ...   NET +2,421.0

    When less fits, zero terms go first, then terms past the first two
    of a group are summed as "other", then the terms themselves.
    """
    pygame.draw.rect(surface, theme.PANEL_BORDER, rect, 1)
    y = rect.centery
    x = _bar_text(surface, "REWARD", rect.x + 14, y, theme.ACCENT, head=True)
    x = _bar_text(surface, reward.profile, x + 8, y, theme.TEXT_DIM)
    net = signed(reward.total)
    net_width = (
        get_font(theme.HEADER_SIZE, True).size("NET ")[0]
        + get_font(theme.TEXT_SIZE, True).size(net)[0]
    )
    room = rect.right - 14 - net_width - 24 - (x + 24)
    gains, costs = reward_groups(reward)
    groups = [("GAINS", gains, theme.GOOD), ("COSTS", costs, theme.BAD)]
    x += 24
    for title, total, terms, color in _fit_groups(groups, room):
        x = _bar_text(surface, title, x, y, theme.TEXT_DIM, head=True)
        x = _bar_text(surface, signed(total), x + 6, y, color, bold=True)
        if terms:
            x = _bar_text(surface, terms, x + 10, y, theme.TEXT_DIM)
        x += 24
    right = draw_text(
        surface,
        net,
        (rect.right - 14, y),
        theme.TEXT_SIZE,
        theme.TEXT,
        bold=True,
        anchor="midright",
    )
    draw_text(
        surface,
        "NET",
        (right.x - 6, y),
        theme.HEADER_SIZE,
        theme.TEXT_DIM,
        bold=True,
        anchor="midright",
    )


def signed(value: float) -> str:
    """+3,901.0, -1,480.0, and a plain 0.0 (no sign on nothing)."""
    if round(value, 1) == 0:
        return "0.0"
    return f"{value:+,.1f}"


def _bar_text(
    surface, text: str, x: float, y: float, color, bold=False, head=False
) -> int:
    """Draws one piece of the bar's line; returns where it ends."""
    return draw_text(
        surface,
        text,
        (x, y),
        theme.HEADER_SIZE if head else theme.TEXT_SIZE,
        color,
        bold=bold or head,
        anchor="midleft",
    ).right


def _terms_text(items: list, most: int | None) -> str:
    if most is not None and len(items) > most:
        rest = sum(v for _, v in items[most:])
        items = items[:most] + [("other", rest)]
    return " · ".join(f"{term} {signed(value)}" for term, value in items)


def _fit_groups(groups: list, room: float) -> list:
    """(title, total, terms text, color) per group, as much as fits."""
    font = get_font(theme.TEXT_SIZE)
    bold = get_font(theme.TEXT_SIZE, True)
    head = get_font(theme.HEADER_SIZE, True)

    def build(drop_zero: bool, most: int | None, terms: bool) -> list:
        built = []
        for title, items, color in groups:
            if not items:
                continue
            total = sum(v for _, v in items)
            shown = [(t, v) for t, v in items if v or not drop_zero]
            text = _terms_text(shown, most) if terms else ""
            built.append((title, total, text, color))
        return built

    def width(built: list) -> float:
        return sum(
            head.size(title)[0]
            + 6
            + bold.size(signed(total))[0]
            + 10
            + font.size(text)[0]
            + 24
            for title, total, text, _ in built
        )

    for drop_zero, most, terms in (
        (False, None, True),
        (True, None, True),
        (True, 2, True),
        (True, 1, True),
        (True, None, False),
    ):
        built = build(drop_zero, most, terms)
        if width(built) <= room:
            return built
    return built


def draw_car_panel(
    surface: Surface,
    rect: Rect,
    world: World,
    cars: list[CarInfo],
    hud: ConfigDict,
    display: tuple[float, int, bool] = (0.0, 60, False),
) -> None:
    """Right: the car's live instruments, next to the field, and the
    display. display: (fps, target frame rate, vsync).
    """
    column = _Column(surface, rect)
    car = cars[0] if cars else None
    stop_distance = 0.0
    if car:
        stop_distance = warnings.stopping_distance(
            car.speed,
            hud.reaction_time,
            world.resource(SimConfig).brake_deceleration,
        )

    column.header("CAR")
    if car:
        column.row(
            "Speed",
            f"{car.speed:,.1f} px/s",
            warnings.speed_level(
                _ahead_distance(car), car.speed, stop_distance
            ),
        )
        column.row("Stop dist", f"{stop_distance:,.0f} px")
        column.row("Pedal", car.pedal)
        column.row("Steering", _steering_text(car.steering))
        column.row("Heading", f"{car.heading:.0f}°")
        column.row("Position", f"{car.center[0]:.1f}, {car.center[1]:.1f}")
        _draw_inputs(column, car.action)
    else:
        column.note("No car")
    column.gap()

    column.header("SENSORS (px to border)")
    if car:
        _draw_sensors(
            column, car, world.resource(SimConfig).brake_deceleration, hud
        )
    column.gap()

    column.header("OBJECTIVE")
    checkpoint = nearest_checkpoint(world, car) if car else None
    if checkpoint:
        distance, direction = checkpoint
        column.row(
            "Checkpoint",
            f"{distance:,.0f} px {direction}",
            warnings.checkpoint_level(distance, hud),
        )
    else:
        column.row("Checkpoint", DASH)
    column.row("Collected", str(car.score.checkpoints) if car else DASH)

    fps, frame_rate, vsync = display
    column.header("DISPLAY")
    column.row(
        "FPS",
        f"{fps:.0f}/{frame_rate}",
        warnings.fps_level(fps, frame_rate, hud),
    )
    column.row("Vsync", "on" if vsync else "off")
    column.note("?  shortcuts")
    column.finish()


# Mirrored columns: the car's left side on the left, right side on the right.
SENSOR_ROWS = (
    ("front", "back"),
    ("front_left", "front_right"),
    ("left", "right"),
    ("back_left", "back_right"),
)
SENSOR_LABELS = {
    "front": "Front",
    "front_left": "F-left",
    "left": "Left",
    "back_left": "B-left",
    "back": "Back",
    "back_right": "B-right",
    "right": "Right",
    "front_right": "F-right",
}


def _ahead_distance(car: CarInfo) -> float | None:
    """Distance straight along the direction of travel."""
    name = "front" if car.speed > 0 else "back" if car.speed < 0 else None
    return next((ray.distance for ray in car.rays if ray.name == name), None)


def _draw_sensors(
    column: _Column, car: CarInfo, brake_deceleration: float, hud: ConfigDict
) -> None:
    rays = {ray.name: ray for ray in car.rays}
    levels = warnings.ray_levels(car.rays, car.speed, brake_deceleration, hud)
    middle = (column.left + column.right) // 2
    for left_name, right_name in SENSOR_ROWS:
        for name, x, right_edge in (
            (left_name, column.left, middle - 12),
            (right_name, middle + 12, column.right),
        ):
            if name not in rays:
                continue
            ray = rays[name]
            level = levels[name]
            draw_text(
                column.surface,
                SENSOR_LABELS.get(name, name),
                (x, column.y),
                theme.TEXT_SIZE,
                warnings.label_color(level),
            )
            draw_text(
                column.surface,
                f"{ray.distance:.1f}",
                (right_edge, column.y),
                theme.TEXT_SIZE,
                warnings.value_color(level),
                anchor="topright",
            )
        column.y += theme.LINE_HEIGHT


def _steering_text(steering: float) -> str:
    if steering == 0:
        return "Center"
    side = "Left" if steering > 0 else "Right"
    return f"{side} {abs(steering) * 100:.0f} %"


def _draw_inputs(column: _Column, action: ActionInput) -> None:
    """Keys as text: pressed keys are bright and bold, others dim."""
    draw_text(
        column.surface,
        "Inputs",
        (column.left, column.y),
        theme.TEXT_SIZE,
        theme.TEXT_DIM,
    )
    keys = (
        ("W", action.gas),
        ("A", action.turn_left),
        ("S", action.reverse),
        ("D", action.turn_right),
        ("SPACE", action.brake),
    )
    x = column.right
    for letter, pressed in reversed(keys):
        rect = draw_text(
            column.surface,
            letter,
            (x, column.y),
            theme.TEXT_SIZE,
            theme.ACCENT if pressed else theme.TEXT_DIM,
            bold=pressed,
            anchor="topright",
        )
        x = rect.left - 10
    column.y += theme.LINE_HEIGHT
