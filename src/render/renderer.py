import pygame
from ml_collections import ConfigDict
from pygame import Surface

from src.ecs import World
from src.render import panels, theme, warnings
from src.render.layout import Layout
from src.sim.components import (
    Checkpoint,
    Hitbox,
    Motion,
    PreviousPose,
    Renderable,
    Sensors,
    Transform,
    Trigger,
)
from src.sim.geometry import car_corners
from src.sim.stage import Stage, load_stage
from src.sim.resources import EventLog, Field, RoundState, SimConfig
from src.utils.common import (
    get_triangle_coordinates_from_rect,
    lerp,
    lerp_angle,
)
from src.utils.types import Colors, ColorValue
from src.utils.ui import draw_text


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
        self.layout = Layout.for_field(field_rect.width, field_rect.height)
        self.offset = (
            self.layout.field_view.x - field_rect.x,
            self.layout.field_view.y - field_rect.y,
        )
        # Debug lines (rays, hitbox, and future distance or boundary
        # lines). H toggles them; the config flags pick which kinds exist.
        self.show_lines = True

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

    def poll_events(self) -> set[str]:
        """Handles window events. Returns the commands asked for."""
        commands = set()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                commands.add(Command.QUIT)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    commands.add(Command.QUIT)
                elif event.key == pygame.K_r:
                    commands.add(Command.RESTART)
                elif event.key == pygame.K_h:
                    self.show_lines = not self.show_lines
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    x = event.pos[0] - self.offset[0]
                    y = event.pos[1] - self.offset[1]
                    print(f"left click at world ({x}, {y})")
        return commands

    def draw(
        self,
        world: World,
        alpha: float = 1.0,
        reward: panels.RewardStatus | None = None,
    ) -> None:
        """alpha: how far between the previous and current step to draw
        the cars (1.0 = exactly the current step). reward: the agent
        reward to show (it comes from the env, not the simulation).
        """
        self.display.fill(theme.BACKGROUND)
        self._draw_field(world, alpha)
        cars = panels.car_infos(world)
        panels.draw_top_bar(
            self.display,
            self.layout.top_bar,
            world,
            cars[0] if cars else None,
            self.config.hud,
            reward,
        )
        panels.draw_side_panel(
            self.display,
            self.layout.panel,
            world,
            cars,
            self.config.hud,
            reward,
        )
        panels.draw_bottom_bar(
            self.display,
            self.layout.bottom_bar,
            world,
            self.clock.get_fps(),
            self.frame_rate,
            self.vsync,
            self.config.hud,
        )
        self._draw_round_over(world)

    def present(self) -> float:
        """Shows the frame. Returns the real seconds since the last one."""
        pygame.display.flip()
        return self.clock.tick(self.frame_rate) / 1000

    def _draw_field(self, world: World, alpha: float) -> None:
        self._checkpoints = world.query(Transform, Checkpoint)
        field_rect = world.resource(Field).rect.move(self.offset)
        # pygame draws a 1 px outline inside the rect's right and bottom
        # edges. One extra pixel puts the line exactly on the physics
        # boundary, where car corners stop.
        border = pygame.Rect(
            field_rect.x, field_rect.y, field_rect.w + 1, field_rect.h + 1
        )
        pygame.draw.rect(self.display, theme.FIELD_BORDER, border, 1)
        for _, (spot, trigger, _) in world.query(
            Transform, Trigger, Checkpoint
        ):
            pygame.draw.circle(
                self.display,
                theme.CHECKPOINT,
                (spot.x + self.offset[0], spot.y + self.offset[1]),
                trigger.radius,
                width=2,
            )
        sim = world.resource(SimConfig)
        for _, (transform, motion, hitbox, sensors, renderable, previous) in (
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
                renderable,
                previous,
                alpha,
                ray_levels,
            )

    def _draw_round_over(self, world: World) -> None:
        state = world.resource(RoundState)
        if not state.over:
            return
        reason = {
            "time": "Time up",
            "all_out": "Every car is out",
        }.get(state.reason, "")
        center_x, center_y = self.layout.field_view.center
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
            ("Press R to restart", theme.TEXT_SIZE, theme.TEXT_DIM, False),
        ]
        y = center_y - 13 * len(lines)
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
        renderable: Renderable,
        previous: PreviousPose,
        alpha: float,
        ray_levels: dict[str, int],
    ) -> None:
        # Interpolated pose between the previous and current step.
        center_x = lerp(previous.center_x, transform.x, alpha)
        center_y = lerp(previous.center_y, transform.y, alpha)
        angle = lerp_angle(previous.angle, transform.angle, alpha)

        surface = self._car_surface(
            hitbox.width, hitbox.height, renderable.color
        )
        rotated = pygame.transform.rotate(surface, angle)
        screen_center = (center_x + self.offset[0], center_y + self.offset[1])
        if self.show_lines:
            # Guide to the checkpoint, under the car.
            for _, (spot, _) in self._checkpoints:
                pygame.draw.line(
                    self.display,
                    theme.GUIDE,
                    screen_center,
                    (spot.x + self.offset[0], spot.y + self.offset[1]),
                )
        self.display.blit(rotated, rotated.get_rect(center=screen_center))

        if not self.show_lines:
            return
        if self.config.show_bounds:
            corners = car_corners(
                screen_center[0],
                screen_center[1],
                angle,
                hitbox.width,
                hitbox.height,
            )
            pygame.draw.polygon(self.display, theme.HITBOX, corners, width=1)
        if self.config.show_collision_distance:
            # Rays are cast at the current step. Shift them with the car.
            dx = self.offset[0] + center_x - transform.x
            dy = self.offset[1] + center_y - transform.y
            # Muted by default. Warning rays are drawn last, on top.
            for ray in sorted(sensors.rays, key=lambda r: ray_levels[r.name]):
                pygame.draw.line(
                    surface=self.display,
                    color=warnings.ray_color(ray_levels[ray.name]),
                    start_pos=(ray.start.x + dx, ray.start.y + dy),
                    end_pos=(ray.end.x + dx, ray.end.y + dy),
                )
