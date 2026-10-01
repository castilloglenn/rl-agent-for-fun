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
from src.render import instruments, theme, warnings
from src.drivers.actions import CANONICAL_NAMES
from src.sim import route
from src.sim.observation import OBSERVATION_NAMES
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
    mind: "MindInfo | None" = None  # an agent drives: what it's thinking


@dataclass(frozen=True)
class MindInfo:
    """What an agent's network thinks at its latest decision (7f7): the
    probability of each of the 12 canonical actions, its value (how good
    it thinks the situation is), and whether the car was stopped (then
    only gas or reverse can be picked, 7f6).
    """

    probabilities: tuple[float, ...]
    value: float
    stopped: bool


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
    stuck: float | None = None  # s since it last got closer (7f7)


def _stuck(world: World, car: int) -> float | None:
    sense = world.try_component(car, route.RouteSense)
    return None if sense is None else route.stuck_seconds(world, sense)


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
            stuck=_stuck(world, car),
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


def health_color(share: float) -> ColorValue:
    if share > 0.6:
        return theme.GOOD
    if share >= 0.3:
        return theme.WARN
    return theme.BAD


def nearest_checkpoint(
    world: World, car: CarInfo
) -> tuple[float, float] | None:
    """Distance (center to center) and angle, relative to the car's
    heading (counterclockwise: + is to its left), of the nearest
    checkpoint.
    """
    spots = [spot for _, (spot, _) in world.query(Transform, Checkpoint)]
    if not spots:
        return None
    x, y = car.center
    spot = min(spots, key=lambda s: math.dist((s.x, s.y), (x, y)))
    bearing = math.degrees(math.atan2(-(spot.y - y), spot.x - x))
    relative = (bearing - car.heading + 180) % 360 - 180
    return math.dist((spot.x, spot.y), (x, y)), relative


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
    readouts: instruments.Readouts | None = None,
) -> None:
    """Left: who's playing, which game, and how it's going, and, when an
    agent drives, what it's thinking (MIND, 7f7).
    """
    readouts = readouts or instruments.Readouts()
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
    if mode and mode.mind:  # an agent drives: what it's thinking
        _draw_mind(column, mode.mind, readouts)
    elif not (mode and mode.source):
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


# The MIND card's colors: steering as in the Agents tab's turning bar,
# pedals as in the driving style charts.
STEER_PARTS = (
    ("left", "left", (90, 150, 230)),
    ("none", "straight", (95, 100, 112)),
    ("right", "right", (150, 110, 220)),
)
PEDAL_PARTS = (
    ("gas", "gas", theme.GOOD),
    ("none", "coast", (95, 100, 112)),
    ("brake", "brake", theme.WARN),
    ("reverse", "reverse", theme.BAD),
)


SPEED_INPUT = OBSERVATION_NAMES.index("speed")


def mind_of(driver) -> MindInfo | None:
    """An agent driver's latest decision as a MindInfo (None for any
    other driver, or before its first decision).
    """
    probabilities = getattr(driver, "probabilities", None)
    if not probabilities:
        return None
    observation = getattr(driver, "observation", None)
    stopped = observation is not None and float(observation[SPEED_INPUT]) == 0
    return MindInfo(tuple(probabilities), driver.value, stopped)


def _draw_mind(column: "_Column", mind: MindInfo, readouts) -> None:
    """Its next move's odds (steering, pedal) and its outlook (the value
    head: how good it thinks things look), at its latest decision.
    """
    surface = column.surface
    title = "MIND · stopped: gas or reverse" if mind.stopped else "MIND"
    column.header(title)
    steer, pedal = {}, {}
    for name, p in zip(CANONICAL_NAMES, mind.probabilities):
        s, d = name.split("+")
        steer[s] = steer.get(s, 0.0) + p
        pedal[d] = pedal.get(d, 0.0) + p
    for label, odds, parts in (
        ("Steer", steer, STEER_PARTS),
        ("Pedal", pedal, PEDAL_PARTS),
    ):
        key, shown, _ = max(parts, key=lambda part: odds.get(part[0], 0))
        _instrument_row(
            column,
            label,
            readouts.text(
                f"mind_{label}",
                0.0,
                lambda _, k=key, n=shown: f"{n} {odds.get(k, 0):.0%}",
                mean=False,
            ),
            theme.TEXT,
            lambda area, o=odds, ps=parts: instruments.draw_segments(
                surface,
                Rect(area.x, area.centery - 4, area.w, 8),
                [(o.get(k, 0.0), color) for k, _, color in ps],
            ),
        )
    peak = readouts.peak("outlook", mind.value)
    _instrument_row(
        column,
        "Outlook",
        readouts.text("outlook", mind.value, lambda v: f"{v:+.2f}"),
        theme.GOOD if mind.value >= 0 else theme.BAD,
        lambda area: instruments.draw_center_gauge(
            surface,
            Rect(area.x, area.centery - 4, area.w, 8),
            mind.value / peak,
        ),
    )


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
    readouts: instruments.Readouts | None = None,
) -> None:
    """Right: the car's live instruments, next to the field, and the
    display. display: (fps, target frame rate, vsync). camera: its mode
    (step 7b), for example "fit 53 %". readouts: the window's steady
    numbers (7f3: a mean, redrawn 4 times a second).
    """
    readouts = readouts or instruments.Readouts()
    column = _Column(surface, rect)
    car = cars[0] if cars else None
    sim = world.resource(SimConfig)
    stop_distance = 0.0
    if car:
        stop_distance = warnings.stopping_distance(
            car.speed, hud.reaction_time, sim.brake_deceleration
        )

    column.header("CAR")
    if car:
        level = warnings.speed_level(
            _ahead_distance(car), car.speed, stop_distance
        )
        _instrument_row(
            column,
            "Speed",
            readouts.text("speed", car.speed, lambda v: f"{v:,.0f} px/s"),
            warnings.value_color(level),
            lambda area: instruments.draw_speed_bar(
                surface,
                Rect(area.x, area.centery - 4, area.w, 8),
                car.speed,
                sim.max_speed,
                sim.max_reverse_speed,
                level,
            ),
        )
        _instrument_row(
            column,
            "Steering",
            "",
            theme.TEXT,
            lambda area: instruments.draw_slider(surface, area, car.steering),
        )
        _instrument_row(
            column,
            "Heading",
            readouts.text(
                "heading", car.heading, lambda v: f"{v:.0f}°", mean=False
            ),
            theme.TEXT,
            lambda area: instruments.draw_dial(
                surface, (area.x + 8, area.centery), 8, car.heading
            ),
        )
        x = readouts.text("x", car.center[0], lambda v: f"{v:.0f}")
        y = readouts.text("y", car.center[1], lambda v: f"{v:.0f}")
        column.row("Position", f"{x}, {y}")
        _draw_inputs(column, car.action)
    else:
        column.note("No car")
    column.gap()

    column.header("SENSORS")
    if car:
        levels = warnings.ray_levels(
            car.rays, car.speed, sim.brake_deceleration, hud
        )
        radius = 50
        center = ((column.left + column.right) // 2, column.y + radius + 4)
        closest = instruments.draw_radar(
            surface, center, radius, car.rays, levels, car.speed,
            stop_distance,
        )
        column.y += 2 * radius + 12
        if closest:
            name, distance = closest
            near = readouts.text(
                "closest", distance, lambda v: f"{v:,.0f} px"
            )
            which = readouts.text(
                "closest_ray",
                0.0,
                lambda _, n=name: instruments.ray_label(n),
                mean=False,
            )
            column.note(
                f"closest {near} · {which}",
                warnings.value_color(levels.get(name, warnings.NORMAL)),
            )
    column.gap()

    column.header("OBJECTIVE")
    checkpoint = nearest_checkpoint(world, car) if car else None
    if checkpoint:
        distance, relative = checkpoint
        level = warnings.checkpoint_level(distance, hud)
        color = warnings.value_color(level)

        def compass(area: Rect) -> None:
            instruments.draw_arrow(
                surface, (area.x + 8, area.centery), 8, relative, theme.ACCENT
            )
            bar = Rect(area.x + 24, area.centery - 3, area.w - 24, 6)
            pygame.draw.rect(surface, theme.BAR_EMPTY, bar)
            share = min(distance / instruments.RADAR_RANGE / 3, 1.0)
            fill = Rect(bar.x, bar.y, round(bar.w * share), bar.h)
            pygame.draw.rect(surface, color, fill)

        _instrument_row(
            column,
            "Checkpoint",
            readouts.text("checkpoint", distance, lambda v: f"{v:,.0f} px"),
            color,
            compass,
        )
    else:
        column.row("Checkpoint", DASH)
    if car and car.stuck is not None:
        stuck = car.stuck

        def timer(area: Rect) -> None:
            share = min(stuck / route.STUCK_CAP, 1.0)
            bar = Rect(area.x, area.centery - 3, area.w, 6)
            pygame.draw.rect(surface, theme.BAR_EMPTY, bar)
            color = theme.BAD if stuck >= 5 else theme.WARN
            if share:
                fill = Rect(bar.x, bar.y, round(bar.w * share), bar.h)
                pygame.draw.rect(surface, color, fill)

        _instrument_row(
            column,
            "Stuck",
            readouts.text("stuck", stuck, lambda v: f"{v:.0f} s"),
            theme.TEXT_DIM if stuck < 1 else theme.WARN,
            timer,
        )
    column.row("Collected", str(car.score.checkpoints) if car else DASH)

    fps, frame_rate, vsync = display
    column.header("DISPLAY")
    column.row(
        "FPS",
        f"{readouts.text('fps', fps, lambda v: f'{v:.0f}')}/{frame_rate}",
        warnings.fps_level(fps, frame_rate, hud),
    )
    column.row("Camera", f"{camera} · vsync {'on' if vsync else 'off'}")
    column.note("?  shortcuts  ·  O  settings")
    column.finish()


LABEL_WIDTH = 86  # an instrument row's label column


def _instrument_row(
    column: "_Column", label: str, text: str, color, draw
) -> None:
    """A label, an instrument drawn in the room between, and a steady
    number on the right.
    """
    surface = column.surface
    draw_text(
        surface, label, (column.left, column.y), theme.TEXT_SIZE,
        theme.TEXT_DIM,
    )
    right = column.right
    if text:
        shown = draw_text(
            surface, text, (column.right, column.y), theme.TEXT_SIZE, color,
            anchor="topright",
        )
        right = shown.left - 10
    area = Rect(
        column.left + LABEL_WIDTH,
        column.y,
        max(right - column.left - LABEL_WIDTH, 10),
        theme.LINE_HEIGHT - 4,
    )
    draw(area)
    column.y += theme.LINE_HEIGHT


def _ahead_distance(car: CarInfo) -> float | None:
    """Distance straight along the direction of travel."""
    name = "front" if car.speed > 0 else "back" if car.speed < 0 else None
    return next((ray.distance for ray in car.rays if ray.name == name), None)


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
