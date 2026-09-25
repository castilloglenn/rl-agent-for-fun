import pygame
from ml_collections import ConfigDict
from pygame import Surface

from src.ecs import World
from src.sim.components import (
    CarSpec,
    Hitbox,
    Motion,
    Renderable,
    Sensors,
    Transform,
)
from src.sim.resources import Field
from src.utils.common import get_triangle_coordinates_from_rect
from src.utils.types import Colors, ColorValue
from src.utils.ui import draw_texts, get_window_constants


class Renderer:
    """Draws a World in a pygame window. Only reads components, so
    turning it on or off never changes the simulation.
    """

    def __init__(self, config: ConfigDict) -> None:
        self.config = config
        self.window = get_window_constants(config=config)

        pygame.init()
        pygame.display.set_caption(self.window.title)
        self.display = pygame.display.set_mode(
            (self.window.width, self.window.height)
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
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    print(f"left click at {event.pos}")
        return quit_requested

    def draw(self, world: World) -> None:
        self.display.fill(Colors.BLACK)
        self._draw_hud(world)
        pygame.draw.rect(
            self.display, Colors.WHITE, world.resource(Field).rect, 1
        )
        for _, (transform, hitbox, sensors, renderable) in world.query(
            Transform, Hitbox, Sensors, Renderable
        ):
            self._draw_car(transform, hitbox, sensors, renderable)

    def present(self) -> None:
        pygame.display.update()
        self.clock.tick(self.config.display.fps)

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
        self.display.blit(rotated, hitbox.rect)

        if self.config.show_bounds:
            pygame.draw.rect(self.display, Colors.WHITE, hitbox.rect, width=1)
        if self.config.show_collision_distance:
            for ray in sensors.rays:
                pygame.draw.line(
                    surface=self.display,
                    color=Colors.WHITE,
                    start_pos=ray.start,
                    end_pos=ray.end,
                )

    def _draw_hud(self, world: World) -> None:
        cars = world.query(Transform, Motion, CarSpec, Hitbox, Sensors)
        if not cars:
            return
        # Debug overlay for the first car.
        _, (transform, motion, spec, hitbox, sensors) = cars[0]
        rays = {ray.name: ray.distance for ray in sensors.rays}

        mf = self.config.display.fps
        a = motion.acceleration_rate / self.config.car.acceleration_max
        s = spec.base_speed * motion.speed
        car = hitbox.rect
        wh = f"({car.width:3,.0f}, {car.height:3,.0f})"
        cn = f"({car.centerx:3,.0f}, {car.centery:3,.0f})"

        sep = " " * 3
        spd = f"SPD: {s:8,.2f}"
        acc = f"ACC: {a * 100:7,.0f}%"
        agl = f"AGL: {transform.angle:7.0f}°"
        fps = f"FPS: {self.clock.get_fps():5.0f}/{mf}"
        dim = f"DIM: {wh:>10s}"
        dim_s = len(dim) * " " + (sep * 2)
        cen = f"CEN: {cn:>10s}"
        cll = f"LSC: {rays['left']:>6.2f}"
        clb = f"BSC: {rays['back']:>6.2f}"
        clf = f"FSC: {rays['front']:>6.2f}"
        clr = f"RSC: {rays['right']:>6.2f}"

        draw_texts(
            surface=self.display,
            texts=[
                spd + sep + cen + sep + cll,
                acc + sep + dim + sep + clf,
                agl + dim_s + clr,
                fps + dim_s + clb,
            ],
            size=12,
            x=self.window.width * 0.025,
            y=self.window.half_height * 0.075,
        )
