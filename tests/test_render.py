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
    panels = (layout.left_panel, layout.right_panel)
    for rect in (layout.top_bar, *panels):
        assert layout.window.contains(rect)
    for panel in panels:
        assert not layout.field_view.colliderect(panel)
        assert not layout.top_bar.colliderect(panel)
    assert layout.left_panel.right < layout.field_view.left
    assert layout.right_panel.left > layout.field_view.right
    assert layout.window.width <= 1470  # the laptop screen
    assert not layout.field_view.colliderect(layout.top_bar)


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
    for panel_area in (renderer.layout.left_panel, renderer.layout.right_panel):
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
    for _ in range(150):  # fast enough to move > 2 px per step
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


def test_top_bar_shows_the_stage_and_seed():
    from src.render.panels import round_details
    from src.sim.factories import create_game

    world, _ = create_game(get_maze_car_config(), seed=42)
    assert round_details(world) == [
        ("STAGE", "box 855×480"),
        ("RULES", "standard"),
        ("SPAWNS", "random"),
        ("SEED", "42"),
    ]


def test_top_bar_shows_the_reward_profile():
    from src.render.panels import RewardStatus, round_details
    from src.sim.factories import create_game

    world, _ = create_game(get_maze_car_config(), seed=42)
    status = RewardStatus(profile="cautious", last=0.0, total=0.0)
    assert round_details(world, status)[-1] == ("REWARD", "cautious")


def test_side_panel_content_fits_inside_the_panel():
    """The last line must end above each panel's bottom border."""
    config = get_maze_car_config()
    renderer = Renderer(config)
    world = create_world(config)
    create_start_car(world)
    renderer.draw(world)
    from src.render import theme

    for panel in (renderer.layout.left_panel, renderer.layout.right_panel):
        bottom_rows = renderer.display.subsurface(
            (panel.x + 2, panel.bottom - 4, panel.width - 4, 3)
        )
        data = pygame.image.tobytes(bottom_rows, "RGB")
        colors = {tuple(data[i : i + 3]) for i in range(0, len(data), 3)}
        assert colors == {theme.BACKGROUND}  # no text touching the border


def test_panels_fit_long_names():
    """Long names are shortened with "…", never drawn past the edge."""
    from src.render import theme
    from src.render.panels import RewardStatus
    from src.sim.rules import load_rules

    config = get_maze_car_config()
    renderer = Renderer(config)
    world = create_world(
        config, rules=load_rules("standard").with_round_seconds(1234.5)
    )
    create_start_car(world, label="A very long player name (keyboard)")
    status = RewardStatus(profile="an-extremely-long-profile", last=0, total=0)
    renderer.draw(world, 1.0, status)
    for bar in (renderer.layout.top_bar, renderer.layout.left_panel):
        edge = renderer.display.subsurface(
            (bar.right - 8, bar.y + 2, 6, bar.h - 4)
        )
        data = pygame.image.tobytes(edge, "RGB")
        colors = {tuple(data[i : i + 3]) for i in range(0, len(data), 3)}
        # No text: only the background, and section separator lines.
        assert colors <= {theme.BACKGROUND, theme.PANEL_BORDER}


def test_question_mark_toggles_the_shortcuts_box():
    from src.render import panels, theme

    config = get_maze_car_config()
    renderer = Renderer(config)
    world = create_world(config)
    create_start_car(world)
    for expected in (True, False):
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SLASH)
        pygame.event.post(event)
        renderer.poll_events()
        assert renderer.show_shortcuts is expected
    renderer.show_shortcuts = True
    renderer.draw(world)  # live play: its own shortcuts
    mode = panels.ModeInfo("REPLAY", theme.GOOD, (("SPACE", "pause"),))
    renderer.draw(world, 1.0, None, mode)
    assert ("?", "these shortcuts") in panels.LIVE_SHORTCUTS


def test_every_mode_lists_its_shortcuts():
    from src.envs.maze_car.demo import RECORDING_SHORTCUTS
    from src.experiments.showcase import SHORTCUTS as SHOWCASE
    from src.replay.viewer import SHORTCUTS as REPLAY

    for shortcuts in (RECORDING_SHORTCUTS, REPLAY, SHOWCASE):
        keys = [key for key, _ in shortcuts]
        assert "?" in keys and "Esc" in keys
    assert "K" in [key for key, _ in RECORDING_SHORTCUTS]
    assert "<- ->" in [key for key, _ in SHOWCASE]


def test_the_top_bar_doesnt_move_when_the_status_changes():
    from src.sim.components import Motion

    config = get_maze_car_config()
    renderer = Renderer(config)
    world = create_world(config)
    car = create_start_car(world)
    bar = renderer.layout.top_bar
    left_part = (bar.x, bar.y, bar.w - 110, bar.h)  # all but the status
    images = []
    for speed in (0.0, 1.0, -0.5):  # STOPPED, DRIVING, REVERSING
        world.component(car, Motion).speed = speed
        renderer.draw(world)
        images.append(
            pygame.image.tobytes(renderer.display.subsurface(left_part), "RGB")
        )
    assert images[0] == images[1] == images[2]


def test_the_playback_bar_and_the_speed_flash():
    from src.render import panels, theme

    config = get_maze_car_config()
    renderer = Renderer(config)
    world = create_world(config)
    create_start_car(world)

    def playback(speed, paused=False):
        speeds = (0.5, 1.0, 2.0, 4.0)
        info = panels.PlaybackInfo(speed, speeds, paused, 12, 60)
        return panels.ModeInfo("REPLAY", theme.GOOD, (), (), info)

    view = renderer.layout.field_view
    renderer.draw(world, 1.0, None, playback(1.0))
    assert renderer._speed == (1.0, False)
    assert renderer._speed_changed < 0  # nothing changed yet: no flash
    bar = renderer.display.subsurface((view.x, view.bottom - 44, view.w, 34))
    data = pygame.image.tobytes(bar, "RGB")
    colors = {tuple(data[i : i + 3]) for i in range(0, len(data), 3)}
    assert theme.ACCENT in colors  # the lit speed and the progress
    renderer.draw(world, 1.0, None, playback(4.0))
    assert renderer._speed_changed >= 0  # a new speed: it flashes
    renderer._speed_changed = -10_000
    renderer.draw(world, 1.0, None, playback(4.0, paused=True))
    assert renderer._speed_changed >= 0  # pausing flashes too


def test_replays_get_a_playback_box_under_the_field():
    live = Layout.for_field(855, 480)
    replay = Layout.for_field(855, 480, playback=True)
    assert live.playback_bar is None
    bar = replay.playback_bar
    assert bar.top > replay.field_view.bottom and bar.w == 855
    assert bar.x == replay.field_view.x
    assert replay.window.h == live.window.h + 60
    assert replay.left_panel.bottom == bar.bottom  # the panels match
    assert replay.window.contains(bar)

