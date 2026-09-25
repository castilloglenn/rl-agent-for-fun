import pygame
from ml_collections import ConfigDict
from pygame import Surface

from src.ecs import World
from src.render import panels, theme
from src.render.layout import Layout
from src.sim.components import Hitbox, Renderable, Sensors, Transform
from src.sim.resources import Field
from src.utils.common import get_triangle_coordinates_from_rect
from src.utils.types import Colors, ColorValue


class Renderer:
    """Draws a World in a pygame window. Only reads components, so
    turning it on or off never changes the simulation.

    World coordinates are drawn shifted by `offset`, so the field lands in
    the layout's field view.
    """

    def __init__(self, config: ConfigDict) -> None:
        self.config = config
        field_rect = Field.from_config(config).rect
        self.layout = Layout.for_field(field_rect.width, field_rect.height)
        self.offset = (
            self.layout.field_view.x - field_rect.x,
            self.layout.field_view.y - field_rect.y,
        )
        self.show_panels = True

        pygame.init()
        pygame.display.set_caption(config.window.title)
        self.display = pygame.display.set_mode(self.layout.window.size)
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
                    self.show_panels = not self.show_panels
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    x = event.pos[0] - self.offset[0]
                    y = event.pos[1] - self.offset[1]
                    print(f"left click at world ({x}, {y})")
        return quit_requested

    def draw(self, world: World) -> None:
        self.display.fill(theme.BACKGROUND)
        self._draw_field(world)
        if self.show_panels:
            cars = panels.car_infos(world)
            panels.draw_top_bar(
                self.display, self.layout.top_bar, cars[0] if cars else None
            )
            panels.draw_side_panel(
                self.display, self.layout.panel, world, cars
            )
            panels.draw_bottom_bar(
                self.display,
                self.layout.bottom_bar,
                world,
                self.clock.get_fps(),
                self.config.display.fps,
            )

    def present(self) -> None:
        pygame.display.update()
        self.clock.tick(self.config.display.fps)

    def _draw_field(self, world: World) -> None:
        field_rect = world.resource(Field).rect.move(self.offset)
        pygame.draw.rect(self.display, theme.FIELD_BORDER, field_rect, 1)
        for _, (transform, hitbox, sensors, renderable) in world.query(
            Transform, Hitbox, Sensors, Renderable
        ):
            self._draw_car(transform, hitbox, sensors, renderable)

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
    ) -> None:
        surface = self._car_surface(
            hitbox.width, hitbox.height, renderable.color
        )
        rotated = pygame.transform.rotate(surface, transform.angle)
        screen_rect = hitbox.rect.move(self.offset)
        self.display.blit(rotated, screen_rect)

        if self.config.show_bounds:
            pygame.draw.rect(self.display, theme.HITBOX, screen_rect, width=1)
        if self.config.show_collision_distance:
            dx, dy = self.offset
            for ray in sensors.rays:
                pygame.draw.line(
                    surface=self.display,
                    color=theme.RAY,
                    start_pos=(ray.start.x + dx, ray.start.y + dy),
                    end_pos=(ray.end.x + dx, ray.end.y + dy),
                )
