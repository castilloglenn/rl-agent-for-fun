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


def test_renderer_draws_with_and_without_lines():
    config = get_maze_car_config()
    renderer = Renderer(config)
    world = create_world(config)
    car = create_start_car(world, label="Tester")
    world.add_component(car, ActionInput(gas=True, turn_left=True))
    world.step()

    renderer.draw(world)
    with_lines = pygame.image.tobytes(renderer.display, "RGB")

    renderer.show_lines = False
    renderer.draw(world)
    without_lines = pygame.image.tobytes(renderer.display, "RGB")

    assert renderer.display.get_size() == renderer.layout.window.size
    assert with_lines != without_lines

    # Only the field view changes: the panels look the same either way.
    field_view = renderer.layout.field_view
    panel_area = renderer.layout.panel
    assert _crop(with_lines, renderer, panel_area) == _crop(
        without_lines, renderer, panel_area
    )
    assert _crop(with_lines, renderer, field_view) != _crop(
        without_lines, renderer, field_view
    )


def test_interpolated_drawing_lands_between_steps():
    config = get_maze_car_config()
    renderer = Renderer(config)
    world = create_world(config)
    car = create_start_car(world)
    for _ in range(60):
        world.add_component(car, ActionInput(gas=True))
        world.step()

    frames = []
    for alpha in (0.0, 0.5, 1.0):
        renderer.draw(world, alpha)
        frames.append(pygame.image.tobytes(renderer.display, "RGB"))
    assert len(set(frames)) == 3  # the car is drawn in three places


def _crop(image: bytes, renderer, rect) -> bytes:
    surface = pygame.image.frombytes(image, renderer.display.get_size(), "RGB")
    return pygame.image.tobytes(surface.subsurface(rect), "RGB")


def _field_colors(renderer) -> set:
    """Every color in the field view (1 px lines included)."""
    field = renderer.display.subsurface(renderer.layout.field_view)
    data = pygame.image.tobytes(field, "RGB")
    return {tuple(data[i : i + 3]) for i in range(0, len(data), 3)}


def test_rays_are_muted_when_safe():
    from src.render import theme

    config = get_maze_car_config()
    renderer = Renderer(config)
    world = create_world(config)
    create_start_car(world)
    world.step()
    renderer.draw(world)

    colors = _field_colors(renderer)
    assert theme.RAY in colors
    assert theme.WARN not in colors and theme.BAD not in colors


def test_rays_turn_red_when_the_wall_ahead_is_too_close():
    from src.render import theme
    from src.sim.components import Sensors

    config = get_maze_car_config()
    renderer = Renderer(config)
    world = create_world(config)
    car = create_start_car(world)
    while True:
        world.add_component(car, ActionInput(gas=True))
        world.step()
        rays = world.component(car, Sensors).rays
        if next(r for r in rays if r.name == "front").distance < 130:
            break
    renderer.draw(world)

    colors = _field_colors(renderer)
    assert theme.BAD in colors  # front ray: closer than the 150 px stop
    assert theme.WARN in colors  # front diagonals: within 2x stop
