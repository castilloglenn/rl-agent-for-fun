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
    # Replays: where it comes from, (label, value) rows for the SOURCE
    # card (a training run's episode, your recording, ...).
    source: tuple[tuple[str, str], ...] = ()
    busy: bool = False  # getting ready: a spinner over the messages


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
    ("F", "camera: follow or fit (big stages)"),
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
    """One row of essentials: round, time, score, and the car's status on
    the right. (The car's health is a bar above the car, 7c4.)
    """
    _box(surface, rect)
    y = rect.y + (rect.height - theme.BIG_SIZE) // 2 - 2

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

    if mode and mode.source:  # a replay: where it comes from, instead
        column.header("SOURCE")  # of a one-car leaderboard
        for label, value in mode.source:
            column.row(label, value)
    else:
        column.header("LEADERBOARD")
        ranked = sorted(cars, key=lambda info: -info.score.total)
        for rank, info in enumerate(ranked, start=1):
            column.row(f"{rank}  {info.label}", f"{info.score.total:,.0f}")

    # What an agent learns from, and the simulation it steps through.
    # Its reward this game (decision 032), and the simulation it runs in.
    title = f"AGENT · {reward.profile}" if reward else "AGENT"
    width = column.right - column.left
    column.header(_fit(title, width, theme.HEADER_SIZE, bold=True))
    if reward:
        gains, costs = reward_groups(reward)
        column.row(
            "Gains",
            signed(sum(v for _, v in gains)),
            colors=(theme.TEXT, theme.GOOD),
        )
        column.row(
            "Costs",
            signed(sum(v for _, v in costs)),
            colors=(theme.TEXT, theme.BAD),
        )
        column.row("Net", signed(reward.total))
        worst = next(((t, v) for t, v in costs if round(v, 1) < 0), None)
        column.row(
            "Biggest cost",
            f"{worst[0]} {signed(worst[1])}" if worst else "none",
            colors=(theme.TEXT_DIM, theme.TEXT_DIM),
        )
    else:
        column.note("No reward profile")
    step = world.resource(SimClock).step
    sim_rate = world.resource(SimConfig).steps_per_second
    column.row("Sim", f"step {step:,} at {sim_rate}/s")
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


def signed(value: float) -> str:
    """+3,901.0, -1,480.0, and a plain 0.0 (no sign on nothing)."""
    if round(value, 1) == 0:
        return "0.0"
    return f"{value:+,.1f}"


def draw_car_panel(
    surface: Surface,
    rect: Rect,
    world: World,
    cars: list[CarInfo],
    hud: ConfigDict,
    display: tuple[float, int, bool] = (0.0, 60, False),
    camera: str = "1:1",
) -> None:
    """Right: the car's live instruments, next to the field, and the
    display. display: (fps, target frame rate, vsync). camera: its mode
    (step 7b), for example "fit 53 %".
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

    column.header("SENSORS (px to a wall)")
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
    column.row("Camera", camera)
    column.note("?  shortcuts  ·  O  settings")
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
