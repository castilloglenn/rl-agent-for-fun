import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

from src.config import get_maze_car_config  # noqa: E402
from src.render.layout import Layout  # noqa: E402
from src.render.renderer import Renderer  # noqa: E402
from src.sim.components import ActionInput  # noqa: E402
from src.sim.factories import create_start_car, create_world  # noqa: E402
from src.sim.resources import Field, SimClock  # noqa: E402


def test_sim_clock_counts_steps():
    world = create_world(get_maze_car_config())
    create_start_car(world)
    for _ in range(5):
        world.step()
    assert world.resource(SimClock).step == 5


def test_layout_fits_field_and_panels():
    layout = Layout.for_field(855, 480)
    assert layout.field_view.size == (855, 480)
    for rect in (layout.top_bar, layout.panel, layout.bottom_bar):
        assert layout.window.contains(rect)
    assert not layout.field_view.colliderect(layout.panel)
    assert not layout.field_view.colliderect(layout.top_bar)
    assert not layout.field_view.colliderect(layout.bottom_bar)


def test_field_drawn_inside_field_view():
    config = get_maze_car_config()
    renderer = Renderer(config)
    world = create_world(config)

    screen_field = world.resource(Field).rect.move(renderer.offset)
    assert screen_field.topleft == renderer.layout.field_view.topleft


def test_renderer_draws_with_and_without_panels():
    config = get_maze_car_config()
    renderer = Renderer(config)
    world = create_world(config)
    car = create_start_car(world, label="Tester")
    world.add_component(car, ActionInput(move_forward=True, turn_left=True))
    world.step()

    renderer.draw(world)
    with_panels = pygame.image.tobytes(renderer.display, "RGB")

    renderer.show_panels = False
    renderer.draw(world)
    without_panels = pygame.image.tobytes(renderer.display, "RGB")

    assert renderer.display.get_size() == renderer.layout.window.size
    assert with_panels != without_panels
