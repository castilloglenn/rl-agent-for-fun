import pygame
from ml_collections import ConfigDict
from pygame import Surface

from src.ecs import World
from src.render import panels, theme
from src.render.layout import Layout
from src.sim.components import (
    Hitbox,
    PreviousPose,
    Renderable,
    Sensors,
    Transform,
)
from src.sim.geometry import car_corners
from src.sim.resources import Field
from src.utils.common import (
    get_triangle_coordinates_from_rect,
    lerp,
    lerp_angle,
)
from src.utils.types import Colors, ColorValue


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

    def __init__(self, config: ConfigDict) -> None:
        self.config = config
        field_rect = Field.from_config(config).rect
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

    def poll_events(self) -> bool:
        """Handles window events. Returns True when the user quits."""
        quit_requested = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                quit_requested = True
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    quit_requested = True
                elif event.key == pygame.K_h:
                    self.show_lines = not self.show_lines
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    x = event.pos[0] - self.offset[0]
                    y = event.pos[1] - self.offset[1]
                    print(f"left click at world ({x}, {y})")
        return quit_requested

    def draw(self, world: World, alpha: float = 1.0) -> None:
        """alpha: how far between the previous and current step to draw
        the cars (1.0 = exactly the current step).
        """
        self.display.fill(theme.BACKGROUND)
        self._draw_field(world, alpha)
        cars = panels.car_infos(world)
        panels.draw_top_bar(
            self.display, self.layout.top_bar, cars[0] if cars else None
        )
        panels.draw_side_panel(self.display, self.layout.panel, world, cars)
        panels.draw_bottom_bar(
            self.display,
            self.layout.bottom_bar,
            world,
            self.clock.get_fps(),
            self.frame_rate,
            self.vsync,
        )

    def present(self) -> float:
        """Shows the frame. Returns the real seconds since the last one."""
        pygame.display.flip()
        return self.clock.tick(self.frame_rate) / 1000

    def _draw_field(self, world: World, alpha: float) -> None:
        field_rect = world.resource(Field).rect.move(self.offset)
        # pygame draws a 1 px outline inside the rect's right and bottom
        # edges. One extra pixel puts the line exactly on the physics
        # boundary, where car corners stop.
        border = pygame.Rect(
            field_rect.x, field_rect.y, field_rect.w + 1, field_rect.h + 1
        )
        pygame.draw.rect(self.display, theme.FIELD_BORDER, border, 1)
        for _, (transform, hitbox, sensors, renderable, previous) in (
            world.query(Transform, Hitbox, Sensors, Renderable, PreviousPose)
        ):
            self._draw_car(
                transform, hitbox, sensors, renderable, previous, alpha
            )

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
            for ray in sensors.rays:
                pygame.draw.line(
                    surface=self.display,
                    color=theme.RAY,
                    start_pos=(ray.start.x + dx, ray.start.y + dy),
                    end_pos=(ray.end.x + dx, ray.end.y + dy),
                )
