import math

import pygame
from ml_collections import ConfigDict
from pygame import Rect, Surface

from src.ecs import World
from src.render import camera, panels, theme, warnings
from src.render.camera import FIT, FOLLOW, MAP_CARD_EXTRA, MAP_TOP
from src.render.layout import MARGIN, Layout
from src.sim.components import (
    Checkpoint,
    Eliminated,
    Health,
    Hitbox,
    Motion,
    PreviousPose,
    Renderable,
    Sensors,
    Transform,
    Trigger,
)
from src.sim.geometry import car_corners, direction
from src.sim.stage import Stage, load_stage
from src.sim.resources import (
    EventLog,
    Field,
    Rng,
    RoundState,
    SimClock,
    SimConfig,
    Walls,
)
from src.utils.common import (
    get_triangle_coordinates_from_rect,
    lerp,
    lerp_angle,
)
from src.utils.settings import OPTIONS, Settings
from src.utils.types import Colors, ColorValue
from src.utils.ui import draw_text, get_font


class Command:
    """Window commands, returned by `Renderer.poll_events`."""

    QUIT = "quit"
    RESTART = "restart"


class Renderer:
    """Draws a World in a pygame window. Only reads components, so
    turning it on or off never changes the simulation.

    World coordinates are drawn shifted by `offset`, so the field lands in
    the layout's field view.

    Frames run at the display's refresh rate (or `display.max_fps`), with
    vsync when available. The simulation rate is separate: see
    docs/decisions/008-fixed-timestep-clock.md.
    """

    FALLBACK_FPS = 60

    def __init__(self, config: ConfigDict, stage: Stage | None = None) -> None:
        """stage: sizes the window. Defaults to loading `config.stage` (a
        replay passes its embedded stage).
        """
        self.config = config
        field_rect = Field.from_stage(stage or load_stage(config.stage)).rect
        # The field view is the box's size (step 7b). A bigger stage adds
        # a map card at the top right, and the view grows as tall.
        view_w, view_h = camera.view_size(field_rect.width, field_rect.height)
        self.map_size = camera.map_size(field_rect.width, field_rect.height)
        map_height = 0
        if self.map_size:
            map_height = self.map_size[1] + MAP_CARD_EXTRA
            view_h += map_height + MARGIN
        self.layout = Layout.for_field(
            view_w,
            view_h,
            playback=config.window.playback_bar,
            map_height=map_height,
        )
        self.camera = camera.Camera.for_stage(
            field_rect.width, field_rect.height, self.layout.field_view
        )
        # The map intro, at each round's start on a big stage (7b).
        self.map_intro = config.window.get("map_intro", True)
        self._intro_world = None  # the round whose intro has started
        self._frame_ticks: int | None = None
        # Debug lines (rays, hitbox, the checkpoint guide). H toggles them
        # (your "lines" setting); the config flags pick which kinds exist.
        self.show_lines = True
        self.show_shortcuts = False  # "?" toggles the shortcuts box
        # Your display settings (7c5): O opens their box. No file in the
        # config (tests, headless) keeps them in memory, at the defaults.
        self.settings = Settings.load(config.window.get("settings_file"))
        self.show_settings = False
        self.setting = 0  # the box's selected row
        self.show_trail = False  # T toggles the trail (replays, watching)
        self._logged_world = None  # the game whose events were printed
        self._logged = 0  # how many of its events
        self.confirm_quit = False  # Esc asks first, Enter confirms
        # The quit box's words (a test drive goes back to the editor).
        self.quit_words = ("QUIT?", "Enter quits  ·  Esc goes back")
        # Keys a mode takes over from the window (a test drive's T).
        self.mode_keys: set[int] = set()
        self.keys_pressed: list[int] = []  # this frame's keys, for modes
        # The playback state last drawn (speed, paused), and when it
        # changed (ms), for the flash.
        self._speed: tuple | None = None
        self._speed_changed = -10_000

        pygame.init()
        pygame.display.set_caption(config.window.title)
        try:
            self.display = pygame.display.set_mode(
                self.layout.window.size, vsync=1
            )
        except pygame.error:
            self.display = pygame.display.set_mode(self.layout.window.size)
        self.vsync = bool(pygame.display.is_vsync())
        self.frame_rate = (
            config.display.max_fps
            or pygame.display.get_current_refresh_rate()
            or self.FALLBACK_FPS
        )
        self.clock = pygame.time.Clock()
        self._car_surfaces: dict[tuple, Surface] = {}
        for option in OPTIONS:
            self._apply(option.key)

    def _apply(self, key: str) -> None:
        """A setting that lives in the window's state (the rest are read
        as the frame is drawn).
        """
        value = self.settings[key]
        if key == "lines":
            self.show_lines = value
        elif key == "trail":
            self.show_trail = value
        elif key == "big_stage_camera" and self.camera.zoomable:
            self.camera.mode = FIT if value == "fit" else FOLLOW
        elif key == "map_intro":
            wanted = self.config.window.get("map_intro", True)
            self.map_intro = wanted and value
        elif key == "fps_cap":
            self.frame_rate = (
                value
                or self.config.display.max_fps
                or pygame.display.get_current_refresh_rate()
                or self.FALLBACK_FPS
            )

    @property
    def offset(self) -> tuple[float, float]:
        """Where the stage's (0, 0) is on screen (1:1 stages)."""
        return self.camera.to_screen(0.0, 0.0)

    @property
    def modal_open(self) -> bool:
        """The game waits: a box is open (shortcuts, quit prompt), or the
        map intro plays.
        """
        return (
            self.show_shortcuts
            or self.show_settings
            or self.confirm_quit
            or self.camera.in_intro
        )

    def poll_events(self, game_over: bool = False) -> set[str]:
        """Handles window events. Returns the commands asked for.

        Esc closes an open box first. Otherwise it asks before quitting
        (Enter quits, Esc goes back), except when the game is over: then
        it quits at once. Closing the window always quits.
        """
        commands = set()
        # Keys pressed this frame, for modes with their own controls. Keys
        # pressed while a box is open are for the box, not the mode, and
        # keys during the map intro only hurry it along.
        self.keys_pressed: list[int] = []
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                commands.add(Command.QUIT)
            elif event.type == pygame.KEYDOWN:
                if self.camera.in_intro:
                    self.camera.hurry_intro()  # on to the zoom; else ignored
                    continue
                self._key(event.key, game_over, commands)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    x, y = self.camera.to_world(*event.pos)
                    print(f"click at world ({x:g}, {y:g})", flush=True)
        return commands

    def _key(self, key: int, game_over: bool, commands: set) -> None:
        if self.show_settings:
            self._settings_key(key)
            return
        if key in self.mode_keys:
            self.keys_pressed.append(key)
            return
        if key == pygame.K_ESCAPE:
            if self.show_shortcuts:
                self.show_shortcuts = False
            elif self.confirm_quit:
                self.confirm_quit = False
            elif game_over:
                commands.add(Command.QUIT)
            else:
                self.confirm_quit = True
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER) and self.confirm_quit:
            commands.add(Command.QUIT)
        elif self.confirm_quit:
            return  # only Enter or Esc answer the prompt
        elif key in (pygame.K_SLASH, pygame.K_QUESTION):
            self.show_shortcuts = not self.show_shortcuts
        elif key == pygame.K_o:
            self.show_shortcuts = False
            self.show_settings = True
        # H, T, and F change your settings too, so the keys, the SETTINGS
        # box, and the next window always agree.
        elif key == pygame.K_h:
            self.show_lines = not self.show_lines
            self.settings.set("lines", self.show_lines)
        elif key == pygame.K_t:
            self.show_trail = not self.show_trail
            self.settings.set("trail", self.show_trail)
        elif key == pygame.K_f:
            self.camera.toggle()
            if self.camera.zoomable:  # a small stage has one camera
                self.settings.set("big_stage_camera", self.camera.mode)
        elif self.show_shortcuts:
            return
        else:
            self.keys_pressed.append(key)
            if key == pygame.K_r:
                commands.add(Command.RESTART)

    def _settings_key(self, key: int) -> None:
        """The SETTINGS box: Up and Down pick a setting, Left and Right
        change it (applied and saved at once), Esc or O closes it.
        """
        if key in (pygame.K_ESCAPE, pygame.K_o):
            self.show_settings = False
        elif key in (pygame.K_UP, pygame.K_w):
            self.setting = (self.setting - 1) % len(OPTIONS)
        elif key in (pygame.K_DOWN, pygame.K_s):
            self.setting = (self.setting + 1) % len(OPTIONS)
        elif key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_a, pygame.K_d):
            by = -1 if key in (pygame.K_LEFT, pygame.K_a) else 1
            option = OPTIONS[self.setting]
            self.settings.step(option.key, by)
            self._apply(option.key)

    def draw(
        self,
        world: World,
        alpha: float = 1.0,
        reward: panels.RewardStatus | None = None,
        mode: panels.ModeInfo | None = None,
    ) -> None:
        """alpha: how far between the previous and current step to draw
        the cars (1.0 = exactly the current step). reward: the agent
        reward to show (it comes from the env, not the simulation).
        mode: a window mode other than live play, such as a replay.
        """
        self.display.fill(theme.BACKGROUND)
        self._print_events(world)
        self._advance_intro(world)
        self._draw_field(world, alpha, mode.trail if mode else None)
        if mode and mode.playback:
            self._draw_playback(mode.playback)
        cars = panels.car_infos(world)
        panels.draw_top_bar(
            self.display,
            self.layout.top_bar,
            world,
            cars[0] if cars else None,
            self.config.hud,
        )
        panels.draw_game_panel(
            self.display, self.layout.left_panel, world, cars, reward, mode
        )
        if self.layout.map_box:
            self._draw_map(world, alpha)
        panels.draw_car_panel(
            self.display,
            self.layout.right_panel,
            world,
            cars,
            self.config.hud,
            (self.clock.get_fps(), self.frame_rate, self.vsync),
            self.camera.label(),
        )
        if self.confirm_quit:
            self._draw_centered_lines(
                [
                    (self.quit_words[0], theme.BIG_SIZE, theme.WARN, True),
                    (
                        self.quit_words[1],
                        theme.TEXT_SIZE,
                        theme.TEXT,
                        False,
                    ),
                ]
            )
        elif self.show_settings:
            self._draw_settings()
        elif self.show_shortcuts:
            self._draw_shortcuts(mode)
        else:
            self._draw_round_over(world, mode)

    def present(self) -> float:
        """Shows the frame. Returns the real seconds since the last one."""
        pygame.display.flip()
        return self.clock.tick(self.frame_rate) / 1000

    def _advance_intro(self, world: World) -> None:
        """A new round starts the map intro (a big stage only); each frame
        moves it on by the real time since the last frame.
        """
        now = pygame.time.get_ticks()
        seconds = 0.0
        if self._frame_ticks is not None:
            seconds = min((now - self._frame_ticks) / 1000, 0.1)
        self._frame_ticks = now
        if world is not self._intro_world:
            self._intro_world = world
            if self.map_intro:
                self.camera.start_intro()
            return
        self.camera.update(seconds)

    MARKER_INSET = 16  # px from the view's edge
    MARKER_SIZE = 12  # px, tip to base

    def _draw_offscreen_checkpoints(self, world: World, alpha: float) -> None:
        """A green triangle on the view's edge for a checkpoint outside it,
        on the line from the car to the checkpoint, pointing to it.
        """
        car = self._first_car(world, alpha)
        if car is None:
            return
        start = self.camera.to_screen(car[0], car[1])
        for _, (spot, _) in self._checkpoints:
            point = self.camera.to_screen(spot.x, spot.y)
            marker = offscreen_marker(
                start, point, self.camera.view, self.MARKER_INSET
            )
            if marker is None:
                continue
            (x, y), (dx, dy) = marker
            size, half = self.MARKER_SIZE, self.MARKER_SIZE * 0.55
            tip = (x + dx * size / 2, y + dy * size / 2)
            back = (x - dx * size / 2, y - dy * size / 2)
            pygame.draw.polygon(
                self.display,
                theme.CHECKPOINT,
                [
                    tip,
                    (back[0] - dy * half, back[1] + dx * half),
                    (back[0] + dy * half, back[1] - dx * half),
                ],
            )

    def _draw_intro_hint(self) -> None:
        """During the intro's overview: what's happening, and the skip."""
        if not self.camera.holding:
            return
        view = self.camera.view
        text = "The whole map · any key zooms in"
        rect = get_font(theme.TEXT_SIZE).size(text)
        box = pygame.Rect(0, 0, rect[0] + 24, rect[1] + 12)
        box.midbottom = (view.centerx, view.bottom - 14)
        self._draw_backdrop(box)
        draw_text(
            self.display,
            text,
            box.center,
            theme.TEXT_SIZE,
            theme.TEXT_DIM,
            anchor="center",
        )

    def _draw_walls(self, world: World) -> None:
        """Walls inside the field (7a): filled, with the border's outline
        (1 px wider, as for the border, so the line is on the surface).
        """
        s = self.camera.scale
        for box in world.resource(Walls).boxes:
            left, top = self.camera.to_screen(box.left, box.top)
            rect = pygame.Rect(
                round(left),
                round(top),
                round((box.right - box.left) * s) + 1,
                round((box.bottom - box.top) * s) + 1,
            )
            pygame.draw.rect(self.display, theme.WALL, rect)
            pygame.draw.rect(self.display, theme.FIELD_BORDER, rect, 1)

    def _draw_field(self, world: World, alpha: float, trail=None) -> None:
        self._checkpoints = world.query(Transform, Checkpoint)
        cam = self.camera
        self._follow(world, alpha)
        view = cam.view
        clip = pygame.Rect(view.x, view.y, view.w + 1, view.h + 1)
        if cam.zoomable:  # the view is a window onto a bigger stage
            pygame.draw.rect(self.display, theme.PANEL_BORDER, clip, 1)
        self.display.set_clip(clip)
        field = world.resource(Field).rect
        left, top = cam.to_screen(field.x, field.y)
        # pygame draws a 1 px outline inside the rect's right and bottom
        # edges. One extra pixel puts the line exactly on the physics
        # boundary, where car corners stop.
        border = pygame.Rect(
            round(left),
            round(top),
            round(field.w * cam.scale) + 1,
            round(field.h * cam.scale) + 1,
        )
        pygame.draw.rect(self.display, theme.FIELD_BORDER, border, 1)
        self._draw_walls(world)
        for _, (spot, trigger, _) in world.query(
            Transform, Trigger, Checkpoint
        ):
            pygame.draw.circle(
                self.display,
                theme.CHECKPOINT,
                cam.to_screen(spot.x, spot.y),
                max(trigger.radius * cam.scale, 3),
                width=2,
            )
        if trail and self.show_trail:
            self._draw_trail(trail)  # under the car
        sim = world.resource(SimConfig)
        step = world.resource(SimClock).step
        for car, (transform, motion, hitbox, sensors, renderable, previous) in (
            world.query(
                Transform, Motion, Hitbox, Sensors, Renderable, PreviousPose
            )
        ):
            ray_levels = warnings.ray_levels(
                sensors.rays,
                motion.speed * sim.steps_per_second,
                sim.brake_deceleration,
                self.config.hud,
            )
            screen_center = self._draw_car(
                transform,
                hitbox,
                sensors,
                self._car_color(world, car, renderable, step, sim),
                previous,
                alpha,
                ray_levels,
            )
            health = world.try_component(car, Health)
            if health is not None:
                self._draw_health_bar(screen_center, hitbox, health.share)
        self._draw_offscreen_checkpoints(world, alpha)
        self._draw_intro_hint()
        self.display.set_clip(None)

    def _draw_map(self, world: World, alpha: float) -> None:
        """The MAP card (big stages): the whole stage, small, at the top
        of the right column: walls, the checkpoint, the car with its
        heading, and in follow mode the area the view shows.
        """
        card = self.layout.map_box
        cam = self.camera
        pygame.draw.rect(self.display, theme.PANEL_BORDER, card, 1)
        draw_text(
            self.display,
            "MAP",
            (card.x + 14, card.y + 10),
            theme.HEADER_SIZE,
            theme.ACCENT,
            bold=True,
        )
        width, height = self.map_size
        box = pygame.Rect(0, card.y + MAP_TOP, width, height)
        box.centerx = card.centerx
        s = width / cam.stage_width
        pygame.draw.rect(self.display, theme.FIELD_BORDER, box, 1)

        def at(x: float, y: float) -> tuple[float, float]:
            return box.x + x * s, box.y + y * s

        for wall in world.resource(Walls).boxes:
            left, top = at(wall.left, wall.top)
            rect = pygame.Rect(
                round(left),
                round(top),
                max(round((wall.right - wall.left) * s), 1),
                max(round((wall.bottom - wall.top) * s), 1),
            )
            pygame.draw.rect(self.display, theme.TEXT_DIM, rect)
        if cam.mode == FOLLOW:
            ox, oy = cam.origin
            seen = pygame.Rect(
                round(box.x + ox * s),
                round(box.y + oy * s),
                round(min(cam.view.w, cam.stage_width) * s),
                round(min(cam.view.h, cam.stage_height) * s),
            )
            pygame.draw.rect(self.display, theme.PANEL_BORDER, seen, 1)
        for _, (spot, _) in self._checkpoints:
            pygame.draw.circle(
                self.display, theme.CHECKPOINT, at(spot.x, spot.y), 3
            )
        car = self._first_car(world, alpha)
        if car:
            x, y, angle = car
            dx, dy = direction(angle)
            head = at(x, y)
            pygame.draw.line(
                self.display,
                theme.TRAIL_RECENT,
                head,
                (head[0] + dx * 8, head[1] + dy * 8),
                2,
            )
            pygame.draw.circle(self.display, theme.TRAIL_RECENT, head, 3)

    def _first_car(self, world: World, alpha: float):
        """(x, y, angle) of the first car, where it's drawn, or None."""
        for _, (transform, previous) in world.query(Transform, PreviousPose):
            return (
                lerp(previous.center_x, transform.x, alpha),
                lerp(previous.center_y, transform.y, alpha),
                lerp_angle(previous.angle, transform.angle, alpha),
            )
        return None

    def _follow(self, world: World, alpha: float) -> None:
        """Follow mode centers on the first car, where it's drawn."""
        car = self._first_car(world, alpha)
        if car:
            self.camera.follow(car[0], car[1])

    def _car_color(self, world, car, renderable, step, sim) -> ColorValue:
        """Dark red once wrecked. After a hit, it blinks red for a moment
        (in simulation time, so replays and pauses show it the same way).
        """
        if world.try_component(car, Eliminated):
            return theme.WRECKED
        health = world.try_component(car, Health)
        if health is None or health.last_hit_step is None:
            return renderable.color
        since = step - health.last_hit_step
        hud = self.config.hud
        if since < hud.hit_flash_seconds * sim.steps_per_second:
            blink = max(round(hud.hit_blink_seconds * sim.steps_per_second), 1)
            if (since // blink) % 2 == 0:
                return theme.HIT
        return renderable.color

    def _draw_round_over(
        self, world: World, mode: panels.ModeInfo | None = None
    ) -> None:
        state = world.resource(RoundState)
        messages = [
            (text, theme.TEXT_SIZE, color, False)
            for text, color in (mode.messages if mode else ())
        ]
        if not state.over:
            if messages:
                self._draw_centered_lines(messages)
            return
        reason = {
            "time": "Time up",
            "all_out": "Every car is out",
        }.get(state.reason, "")
        sps = world.resource(SimConfig).steps_per_second
        eliminations = [
            (
                f"{panels.format_time(event.step / sps)}  {event.text}",
                theme.TEXT_SIZE,
                theme.BAD,
                False,
            )
            for event in world.resource(EventLog).of_kind("elimination")[-3:]
        ]
        lines = [
            ("ROUND OVER", theme.BIG_SIZE, theme.BAD, True),
            (reason, theme.TEXT_SIZE, theme.TEXT, False),
            *eliminations,
            *messages,
            (
                "R restarts  ·  Esc quits",
                theme.TEXT_SIZE,
                theme.TEXT_DIM,
                False,
            ),
        ]
        self._draw_centered_lines(lines)

    def _print_events(self, world: World) -> None:
        """Prints the game's new events (hits, scrapes, checkpoints,
        wrecks, round over) as they happen: the control center's console
        shows them, and so does the terminal.
        """
        if world is not self._logged_world:
            self._logged_world, self._logged = world, 0
            seed = world.resource(Rng).seed
            print(f"--- new round (seed {seed}) ---", flush=True)
        events = world.resource(EventLog).events
        sps = world.resource(SimConfig).steps_per_second
        for event in events[self._logged :]:
            time = panels.format_time(event.step / sps)
            print(f"{time}  {event.text}", flush=True)
        self._logged = len(events)

    # A replay's trail: bright for the last seconds, fading to gray.

    TRAIL_RECENT = 120  # points (at 60 per second): 2 s stay bright
    TRAIL_FADE = 1200  # then fade to gray over the next 20 s
    TRAIL_CHUNK = 8  # points drawn per line, in one color

    def _draw_trail(self, trail) -> None:
        count = len(trail)
        to_screen = self.camera.to_screen
        for start in range(0, count - 1, self.TRAIL_CHUNK):
            chunk = trail[start : start + self.TRAIL_CHUNK + 1]
            if len(chunk) < 2:
                break
            age = count - 1 - (start + len(chunk) - 1)  # its newest point
            fresh = 1.0 - max(age - self.TRAIL_RECENT, 0) / self.TRAIL_FADE
            fresh = max(fresh, 0.0)
            color = tuple(
                round(old + (new - old) * fresh)
                for old, new in zip(theme.TRAIL_OLD, theme.TRAIL_RECENT)
            )
            pygame.draw.lines(
                self.display,
                color,
                False,
                [to_screen(x, y) for x, y in chunk],
                2 if age < self.TRAIL_RECENT else 1,
            )

    # Playback: a video-player-style bar along the bottom of the field.

    FLASH_MS = 700  # how long a speed change shows big in the field

    def _draw_playback(self, playback: panels.PlaybackInfo) -> None:
        now = pygame.time.get_ticks()
        state = (playback.speed, playback.paused)
        if state != self._speed:  # a new speed, a pause, or a resume
            if self._speed is not None:
                self._speed_changed = now
            self._speed = state
        view = self.layout.field_view
        if self.layout.playback_bar:  # its own box, under the field
            box = self.layout.playback_bar
            pygame.draw.rect(self.display, theme.PANEL_BORDER, box, 1)
            bar = box.inflate(-8, -10)
        else:  # no room reserved: over the bottom of the field
            bar = Rect(view.x + 10, view.bottom - 10 - 34, view.w - 20, 34)
            self._draw_backdrop(bar)

        # Play or pause, drawn (not a font glyph, so it always shows).
        icon = Rect(bar.x + 14, bar.centery - 7, 14, 14)
        if playback.paused:
            for x in (icon.x + 1, icon.x + 9):
                pygame.draw.rect(
                    self.display, theme.WARN, Rect(x, icon.y, 4, 14)
                )
        else:
            pygame.draw.polygon(
                self.display,
                theme.GOOD,
                [icon.topleft, icon.bottomleft, (icon.right, icon.centery)],
            )
        clock = (
            f"{_clock(playback.position)} / {_clock(playback.length)}"
        )
        time_rect = draw_text(
            self.display,
            clock,
            (icon.right + 12, bar.centery),
            theme.TEXT_SIZE,
            theme.TEXT,
            anchor="midleft",
        )

        # The speeds, the current one lit, at the right.
        font = get_font(theme.TEXT_SIZE, True)
        right = bar.right - 8
        boxes = []
        for speed in reversed(playback.speeds):
            label = f"{speed:g}×"
            box = Rect(0, bar.y + 5, font.size(label)[0] + 18, bar.h - 10)
            box.right = right
            boxes.append((box, label, speed == playback.speed))
            right = box.left - 4
        for box, label, current in boxes:
            if current:
                pygame.draw.rect(self.display, (20, 60, 95), box)
                pygame.draw.rect(self.display, theme.ACCENT, box, 1)
            draw_text(
                self.display,
                label,
                box.center,
                theme.TEXT_SIZE,
                theme.TEXT if current else theme.TEXT_DIM,
                bold=current,
                anchor="center",
            )

        # Progress, between the time and the speeds.
        left = time_rect.right + 16
        line = Rect(left, bar.centery - 2, right - 16 - left, 4)
        pygame.draw.rect(self.display, theme.BAR_EMPTY, line)
        share = min(max(playback.position / (playback.length or 1), 0), 1)
        done = Rect(line.x, line.y, int(line.w * share), line.h)
        pygame.draw.rect(self.display, theme.ACCENT, done)
        pygame.draw.circle(
            self.display, theme.TEXT, (done.right, line.centery), 6
        )

        # A speed change, big in the middle of the field for a moment.
        age = now - self._speed_changed
        if 0 <= age < self.FLASH_MS:
            fade = 1 - age / self.FLASH_MS
            text = get_font(48, True).render(
                "PAUSED" if playback.paused else f"{playback.speed:g}×",
                True,
                theme.ACCENT,
            )
            text.set_alpha(int(255 * fade))
            self.display.blit(text, text.get_rect(center=view.center))

    def _draw_shortcuts(self, mode: panels.ModeInfo | None) -> None:
        """Every key of the current mode, in a box over the field: keys
        right-aligned in one column, what they do in the next.
        """
        shortcuts = list(mode.shortcuts if mode else panels.LIVE_SHORTCUTS)
        if all(key != "O" for key, _ in shortcuts):  # every mode has it
            at = next(
                (i for i, (key, _) in enumerate(shortcuts) if key == "?"),
                len(shortcuts),
            )
            shortcuts.insert(at, ("O", "settings"))
        # Keys are drawn bold, so they're measured bold.
        key_font = get_font(theme.TEXT_SIZE, True)
        keys = max(key_font.size(key)[0] for key, _ in shortcuts)
        font = get_font(theme.TEXT_SIZE)
        actions = max(font.size(action)[0] for _, action in shortcuts)
        title = get_font(theme.BIG_SIZE, True)
        pad = 24
        width = max(keys + 16 + actions, title.size("SHORTCUTS")[0]) + 2 * pad
        rows = len(shortcuts) + 2  # the title, and the closing hint
        backdrop = pygame.Rect(0, 0, width, 26 * rows + 16)
        backdrop.center = self.layout.field_view.center
        self._draw_backdrop(backdrop)
        y = backdrop.y + 8 + 13
        draw_text(
            self.display,
            "SHORTCUTS",
            (backdrop.centerx, y),
            theme.BIG_SIZE,
            theme.ACCENT,
            bold=True,
            anchor="center",
        )
        key_right = backdrop.x + pad + keys
        for key, action in shortcuts:
            y += 26
            draw_text(
                self.display,
                key,
                (key_right, y),
                theme.TEXT_SIZE,
                theme.ACCENT,
                bold=True,
                anchor="midright",
            )
            draw_text(
                self.display,
                action,
                (key_right + 16, y),
                theme.TEXT_SIZE,
                theme.TEXT,
                anchor="midleft",
            )
        draw_text(
            self.display,
            "? closes",
            (backdrop.centerx, y + 26),
            theme.TEXT_SIZE,
            theme.TEXT_DIM,
            anchor="center",
        )

    SETTINGS_HINT = (
        "Up/Down pick · Left/Right change · saved as you go · Esc closes"
    )

    def _draw_settings(self) -> None:
        """Your display settings in a box over the field: a row each
        (label, value), the picked one lit.
        """
        font, bold = get_font(theme.TEXT_SIZE), get_font(theme.TEXT_SIZE, True)
        labels = max(font.size(o.label)[0] for o in OPTIONS)
        values = max(
            bold.size(text)[0] for o in OPTIONS for _, text in o.choices
        )
        pad = 24
        width = max(labels + 32 + values, font.size(self.SETTINGS_HINT)[0])
        backdrop = pygame.Rect(0, 0, width + 2 * pad, 26 * (len(OPTIONS) + 3))
        backdrop.center = self.layout.field_view.center
        self._draw_backdrop(backdrop)
        y = backdrop.y + 8 + 13
        draw_text(
            self.display,
            "SETTINGS",
            (backdrop.centerx, y),
            theme.BIG_SIZE,
            theme.ACCENT,
            bold=True,
            anchor="center",
        )
        y += 8
        value_x = backdrop.x + pad + labels + 32
        for i, option in enumerate(OPTIONS):
            y += 26
            picked = i == self.setting
            if picked:
                row = pygame.Rect(backdrop.x + 8, y - 12, backdrop.w - 16, 24)
                pygame.draw.rect(self.display, theme.PANEL_BORDER, row)
            draw_text(
                self.display,
                option.label,
                (backdrop.x + pad, y),
                theme.TEXT_SIZE,
                theme.TEXT if picked else theme.TEXT_DIM,
                anchor="midleft",
            )
            draw_text(
                self.display,
                self.settings.shown(option.key),
                (value_x, y),
                theme.TEXT_SIZE,
                theme.ACCENT if picked else theme.TEXT,
                bold=picked,
                anchor="midleft",
            )
        draw_text(
            self.display,
            self.SETTINGS_HINT,
            (backdrop.centerx, y + 34),
            theme.TEXT_SIZE,
            theme.TEXT_DIM,
            anchor="center",
        )

    def _draw_backdrop(self, rect: pygame.Rect) -> None:
        shade = Surface(rect.size, pygame.SRCALPHA)
        shade.fill((*theme.BACKGROUND, 225))
        self.display.blit(shade, rect)
        pygame.draw.rect(self.display, theme.PANEL_BORDER, rect, width=1)

    def _draw_centered_lines(self, lines: list[tuple]) -> None:
        center_x, center_y = self.layout.field_view.center
        # Line centers 26 px apart, the block centered on the field.
        y = center_y - 13 * (len(lines) - 1)
        # A dark backdrop, so the text stays readable over rays and cars,
        # with the same padding above and below the text.
        width = max(
            get_font(size, bold).size(text)[0]
            for text, size, _, bold in lines
        )
        backdrop = pygame.Rect(0, 0, width + 32, 26 * len(lines) + 16)
        backdrop.center = (center_x, center_y)
        self._draw_backdrop(backdrop)
        for text, size, color, bold in lines:
            draw_text(
                self.display,
                text,
                (center_x, y),
                size,
                color,
                bold=bold,
                anchor="center",
            )
            y += 26

    def _car_surface(
        self, width: int, height: int, color: ColorValue
    ) -> Surface:
        key = (width, height, color)
        if key not in self._car_surfaces:
            surface = Surface((width, height), pygame.SRCALPHA, 32)
            surface.fill(color)
            pygame.draw.polygon(
                surface=surface,
                color=Colors.WHITE,
                points=get_triangle_coordinates_from_rect(surface.get_rect()),
            )
            self._car_surfaces[key] = surface
        return self._car_surfaces[key]

    def _draw_car(
        self,
        transform: Transform,
        hitbox: Hitbox,
        sensors: Sensors,
        color: ColorValue,
        previous: PreviousPose,
        alpha: float,
        ray_levels: dict[str, int],
    ) -> tuple[float, float]:
        """Draws the car (and its lines); returns its center on screen."""
        # Interpolated pose between the previous and current step.
        center_x = lerp(previous.center_x, transform.x, alpha)
        center_y = lerp(previous.center_y, transform.y, alpha)
        angle = lerp_angle(previous.angle, transform.angle, alpha)

        cam = self.camera
        scale = cam.scale
        surface = self._car_surface(hitbox.width, hitbox.height, color)
        if scale == 1.0:
            rotated = pygame.transform.rotate(surface, angle)
        else:  # rotated and scaled together, smoothly
            rotated = pygame.transform.rotozoom(surface, angle, scale)
        screen_center = cam.to_screen(center_x, center_y)
        if self.show_lines:
            # Guide to the checkpoint, under the car.
            for _, (spot, _) in self._checkpoints:
                pygame.draw.line(
                    self.display,
                    theme.GUIDE,
                    screen_center,
                    cam.to_screen(spot.x, spot.y),
                )
        self.display.blit(rotated, rotated.get_rect(center=screen_center))

        if not self.show_lines:
            return screen_center
        if self.config.show_bounds:
            corners = car_corners(
                screen_center[0],
                screen_center[1],
                angle,
                hitbox.width * scale,
                hitbox.height * scale,
            )
            pygame.draw.polygon(self.display, theme.HITBOX, corners, width=1)
        if self.config.show_collision_distance:
            # Rays are cast at the current step. Shift them with the car.
            dx = center_x - transform.x
            dy = center_y - transform.y
            # Muted by default. Warning rays are drawn last, on top.
            for ray in sorted(sensors.rays, key=lambda r: ray_levels[r.name]):
                pygame.draw.line(
                    surface=self.display,
                    color=warnings.ray_color(ray_levels[ray.name]),
                    start_pos=cam.to_screen(
                        ray.start.x + dx, ray.start.y + dy
                    ),
                    end_pos=cam.to_screen(ray.end.x + dx, ray.end.y + dy),
                )
        return screen_center

    # The car's health (7c4): a thin bar above it, level on screen, so it
    # never turns with the car or covers it. Fuel joins under it (step 9).
    HEALTH_BAR_HEIGHT = 3  # px
    HEALTH_BAR_GAP = 5  # px between the car's farthest corner and the bar
    HEALTH_BAR_MIN_WIDTH = 12  # px, when a big stage is shown small

    def _draw_health_bar(self, center, hitbox: Hitbox, share: float) -> None:
        """Above the car (or below it: your settings), clear of its
        farthest corner at any heading; not drawn at full health if your
        settings say only when damaged.
        """
        if self.settings["bars_shown"] == "damaged" and share >= 1.0:
            return
        scale = self.camera.scale
        width = max(round(hitbox.width * scale), self.HEALTH_BAR_MIN_WIDTH)
        reach = math.hypot(hitbox.width, hitbox.height) / 2 * scale
        bar = pygame.Rect(0, 0, width, self.HEALTH_BAR_HEIGHT)
        gap = self.HEALTH_BAR_GAP
        if self.settings["bars"] == "below":
            bar.midtop = (round(center[0]), round(center[1] + reach) + gap)
        else:
            bar.midbottom = (round(center[0]), round(center[1] - reach) - gap)
        pygame.draw.rect(self.display, theme.BAR_EMPTY, bar)
        filled = round(width * max(min(share, 1.0), 0.0))
        if filled:
            pygame.draw.rect(
                self.display,
                panels.health_color(share),
                pygame.Rect(bar.x, bar.y, filled, bar.height),
            )


def offscreen_marker(start, point, view, inset: float):
    """Where a marker for `point` (screen px) goes when it's outside the
    view: ((x, y) on the view's edge, inset px in, on the line from
    `start`), and the unit direction it points. None when it's in view.
    """
    if view.collidepoint(point):
        return None
    dx, dy = point[0] - start[0], point[1] - start[1]
    length = math.hypot(dx, dy)
    if length == 0:
        return None
    ux, uy = dx / length, dy / length
    left, right = view.left + inset, view.right - inset
    top, bottom = view.top + inset, view.bottom - inset
    x0 = min(max(start[0], left), right)  # the car can be at the edge
    y0 = min(max(start[1], top), bottom)
    t = math.inf
    if ux > 1e-12:
        t = min(t, (right - x0) / ux)
    elif ux < -1e-12:
        t = min(t, (left - x0) / ux)
    if uy > 1e-12:
        t = min(t, (bottom - y0) / uy)
    elif uy < -1e-12:
        t = min(t, (top - y0) / uy)
    return (x0 + ux * t, y0 + uy * t), (ux, uy)


def _clock(seconds: float) -> str:
    minutes, seconds = divmod(int(seconds), 60)
    return f"{minutes}:{seconds:02d}"
