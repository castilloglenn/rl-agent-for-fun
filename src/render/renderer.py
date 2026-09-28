import pygame
from ml_collections import ConfigDict
from pygame import Rect, Surface

from src.ecs import World
from src.render import camera, panels, theme, warnings
from src.render.camera import FOLLOW
from src.render.layout import Layout
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
        # The field view is the box's size on every stage (step 7b).
        view_w, view_h = camera.view_size(field_rect.width, field_rect.height)
        self.layout = Layout.for_field(
            view_w, view_h, playback=config.window.playback_bar
        )
        self.camera = camera.Camera.for_stage(
            field_rect.width, field_rect.height, self.layout.field_view
        )
        self.show_minimap = True  # M: on stages bigger than the view
        self.minimap_side = "right"  # moves off the car's top quarter
        # Debug lines (rays, hitbox, and future distance or boundary
        # lines). H toggles them; the config flags pick which kinds exist.
        self.show_lines = True
        self.show_shortcuts = False  # "?" toggles the shortcuts box
        self.show_trail = False  # T toggles a replay's trail
        self._logged_world = None  # the game whose events were printed
        self._logged = 0  # how many of its events
        self.confirm_quit = False  # Esc asks first, Enter confirms
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

    @property
    def offset(self) -> tuple[float, float]:
        """Where the stage's (0, 0) is on screen (1:1 stages)."""
        return self.camera.to_screen(0.0, 0.0)

    @property
    def modal_open(self) -> bool:
        """A box that pauses the game is open (shortcuts, quit prompt)."""
        return self.show_shortcuts or self.confirm_quit

    def poll_events(self, game_over: bool = False) -> set[str]:
        """Handles window events. Returns the commands asked for.

        Esc closes an open box first. Otherwise it asks before quitting
        (Enter quits, Esc goes back), except when the game is over: then
        it quits at once. Closing the window always quits.
        """
        commands = set()
        # Keys pressed this frame, for modes with their own controls. Keys
        # pressed while a box is open are for the box, not the mode.
        self.keys_pressed: list[int] = []
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                commands.add(Command.QUIT)
            elif event.type == pygame.KEYDOWN:
                self._key(event.key, game_over, commands)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    x, y = self.camera.to_world(*event.pos)
                    print(f"click at world ({x:g}, {y:g})", flush=True)
        return commands

    def _key(self, key: int, game_over: bool, commands: set) -> None:
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
        elif key == pygame.K_h:
            self.show_lines = not self.show_lines
        elif key == pygame.K_t:
            self.show_trail = not self.show_trail
        elif key == pygame.K_f:
            self.camera.toggle()
        elif key == pygame.K_m:
            self.show_minimap = not self.show_minimap
        elif self.show_shortcuts:
            return
        else:
            self.keys_pressed.append(key)
            if key == pygame.K_r:
                commands.add(Command.RESTART)

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
                    ("QUIT?", theme.BIG_SIZE, theme.WARN, True),
                    (
                        "Enter quits  ·  Esc goes back",
                        theme.TEXT_SIZE,
                        theme.TEXT,
                        False,
                    ),
                ]
            )
        elif self.show_shortcuts:
            self._draw_shortcuts(mode)
        else:
            self._draw_round_over(world, mode)

    def present(self) -> float:
        """Shows the frame. Returns the real seconds since the last one."""
        pygame.display.flip()
        return self.clock.tick(self.frame_rate) / 1000

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
            self._draw_car(
                transform,
                hitbox,
                sensors,
                self._car_color(world, car, renderable, step, sim),
                previous,
                alpha,
                ray_levels,
            )
        self._draw_minimap(world, alpha)
        self.display.set_clip(None)

    MINIMAP = 150  # px: the mini map's long side
    MINIMAP_INSET = 10  # px from the view's edges

    def _draw_minimap(self, world: World, alpha: float) -> None:
        """Follow mode on a big stage: the whole stage, small, in a top
        corner of the view: walls, the checkpoint, the car, and the area
        the view shows. It starts top right, moves to the top left when
        the car heads up and to the right, and back when it heads up and
        to the left.
        """
        cam = self.camera
        if not (self.show_minimap and cam.zoomable and cam.mode == FOLLOW):
            return
        s = self.MINIMAP / max(cam.stage_width, cam.stage_height)
        size = (round(cam.stage_width * s), round(cam.stage_height * s))
        view, inset = cam.view, self.MINIMAP_INSET
        car = self._first_car(world, alpha)
        self.minimap_side = minimap_side(
            self.minimap_side, self._travel(world)
        )
        box = pygame.Rect(0, 0, *size)
        if self.minimap_side == "right":
            box.topright = (view.right - inset, view.top + inset)
        else:
            box.topleft = (view.left + inset, view.top + inset)
        shade = pygame.Surface(size, pygame.SRCALPHA)
        shade.fill((*theme.BACKGROUND, 235))
        self.display.blit(shade, box)

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
        ox, oy = cam.origin
        seen = pygame.Rect(
            round(box.x + ox * s),
            round(box.y + oy * s),
            round(view.w * s),
            round(view.h * s),
        )
        pygame.draw.rect(self.display, theme.PANEL_BORDER, seen, 1)
        for _, (spot, _) in self._checkpoints:
            pygame.draw.circle(
                self.display, theme.CHECKPOINT, at(spot.x, spot.y), 3
            )
        if car:
            x, y, angle = car
            dx, dy = direction(angle)
            head = at(x, y)
            pygame.draw.line(
                self.display,
                theme.TRAIL_RECENT,
                head,
                (head[0] + dx * 7, head[1] + dy * 7),
                2,
            )
            pygame.draw.circle(self.display, theme.TRAIL_RECENT, head, 3)
        pygame.draw.rect(self.display, theme.PANEL_BORDER, box, 1)

    def _travel(self, world: World) -> tuple[float, float] | None:
        """The first car's direction of travel on screen (its heading,
        or the opposite while reversing), or None while it stands still.
        """
        for _, (transform, motion) in world.query(Transform, Motion):
            if motion.speed == 0:
                return None
            dx, dy = direction(transform.angle)
            sign = 1.0 if motion.speed > 0 else -1.0
            return dx * sign, dy * sign
        return None

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
        shortcuts = mode.shortcuts if mode else panels.LIVE_SHORTCUTS
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
    ) -> None:
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
            return
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


def minimap_side(side: str, travel: tuple[float, float] | None) -> str:
    """The mini map's corner: it leaves its side when the car travels
    toward it (up and to the right for the top right corner, up and to
    the left for the top left), and stays put otherwise.
    """
    if travel is None:
        return side
    dx, dy = travel
    if dy >= 0:  # not heading up (screen y grows downward)
        return side
    if side == "right" and dx > 0:
        return "left"
    if side == "left" and dx < 0:
        return "right"
    return side


def _clock(seconds: float) -> str:
    minutes, seconds = divmod(int(seconds), 60)
    return f"{minutes}:{seconds:02d}"
