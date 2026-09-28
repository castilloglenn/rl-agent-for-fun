"""Roadmap step 7b: the camera and the map card. Drawing only. A stage
that fits shows 1:1 in the box-sized view. A bigger one is followed at
1:1 (or fitted with F), with a MAP card at the top right, and the view
grows as tall as the card.
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

from src.config import get_maze_car_config  # noqa: E402
from src.render import camera  # noqa: E402
from src.render.camera import FIT, FOLLOW, Camera  # noqa: E402
from src.sim.stage import load_stage  # noqa: E402

VIEW = pygame.Rect(282, 76, 855, 480)


def test_the_view_is_always_the_box():
    for size in ((855, 480), (1200, 1200), (2200, 600)):
        assert camera.view_size(*size) == (855, 480)
    assert camera.fit_scale(855, 480) == 1.0
    assert camera.fit_scale(1200, 1200) == pytest.approx(0.4)


def _arena():
    return Camera.for_stage(1200, 1200, VIEW)


def test_a_big_stage_follows_by_default():
    cam = _arena()
    assert cam.zoomable and cam.mode == FOLLOW and cam.scale == 1.0
    assert cam.label() == "follow"


def test_follow_centers_and_stops_at_the_edges():
    cam = _arena()
    cam.follow(600, 600)
    assert cam.to_screen(600, 600) == pytest.approx(VIEW.center, abs=1)
    cam.follow(10, 10)
    assert cam.origin == (0.0, 0.0)
    cam.follow(1190, 1190)
    assert cam.origin == (1200 - 855, 1200 - 480)


def test_fit_is_the_overview():
    cam = _arena()
    cam.toggle()
    assert cam.mode == FIT and cam.label() == "fit 40%"
    left = VIEW.x + (855 - 1200 * 0.4) / 2  # centered
    assert cam.to_screen(0, 0) == pytest.approx((left, VIEW.y))
    assert cam.to_screen(1200, 1200) == pytest.approx((left + 480, 556))


def test_screen_to_world_and_back():
    cam = _arena()
    for mode in (FOLLOW, FIT):
        cam.mode = mode
        cam.follow(700, 500)
        point = (123.5, 987.25)
        assert cam.to_world(*cam.to_screen(*point)) == pytest.approx(point)


def test_a_stage_that_fits_never_switches():
    cam = Camera.for_stage(855, 480, pygame.Rect(0, 0, 855, 480))
    cam.toggle()
    assert cam.mode == FIT and cam.scale == 1.0 and cam.label() == "1:1"
    assert cam.to_screen(10, 20) == (10, 20)


# In the window


def _renderer(stage):
    from src.render.renderer import Renderer

    return Renderer(get_maze_car_config(), load_stage(stage))


def test_a_small_stage_keeps_its_window():
    box = _renderer("box")
    assert box.layout.map_box is None
    assert box.layout.field_view.size == (855, 480)
    assert box.offset == box.layout.field_view.topleft  # unchanged


def test_a_big_stage_gets_a_map_card_at_the_top_right():
    box, arena = _renderer("box"), _renderer("arena")
    card, right = arena.layout.map_box, arena.layout.right_panel
    assert arena.map_size == (200, 200)  # the arena is square
    assert card.topright == (arena.layout.window.right - 16, 16)
    assert right.top == card.bottom + 16  # the cards under it
    grow = card.h + 16
    assert arena.layout.field_view.size == (855, 480 + grow)
    assert arena.layout.window.w == box.layout.window.w
    assert arena.layout.window.h == box.layout.window.h + grow
    assert right.bottom == arena.layout.left_panel.bottom


def test_key_f_and_clicks(capsys):
    renderer = _renderer("arena")
    renderer._key(pygame.K_f, False, set())
    assert renderer.camera.mode == FIT
    x, y = renderer.camera.to_screen(100, 200)
    pygame.event.post(
        pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(x, y))
    )
    renderer.poll_events()
    assert "click at world (100, 200)" in capsys.readouterr().out


def _frame_rects(stage):
    """Every rect drawn in one frame of `stage`."""
    from src.envs.maze_car.env import MazeCarEnv

    env = MazeCarEnv(get_maze_car_config(), stage=load_stage(stage))
    env.reset(seed=1)
    rects = []
    real = pygame.draw.rect

    def spy(surface, color, rect, *args, **kwargs):
        rects.append(pygame.Rect(rect))
        return real(surface, color, rect, *args, **kwargs)

    pygame.draw.rect = spy
    try:
        env.renderer.draw(env.world, 1.0, env.reward_status(), None)
    finally:
        pygame.draw.rect = real
    return env.renderer, rects


def test_the_map_card_draws_the_stage_and_the_view_area():
    renderer, rects = _frame_rects("arena")
    card = renderer.layout.map_box
    inside = [r for r in rects if card.contains(r) and r != card]
    assert any(r.size == (200, 200) for r in inside)  # the stage
    walls = len(load_stage("arena").walls)
    assert len(inside) >= walls + 2  # walls, the stage, the view area


# The map intro


def test_the_intro_holds_the_whole_map_then_zooms_in():
    from src.render.camera import INTRO_HOLD, INTRO_ZOOM

    cam = _arena()
    cam.follow(600, 1100)
    target = cam.to_screen(600, 1100)
    cam.start_intro()
    assert cam.in_intro and cam.holding and cam.label() == "overview"
    fit = camera.fit_scale(1200, 1200, VIEW.size)
    assert cam.scale == pytest.approx(fit)
    cam.update(INTRO_HOLD + INTRO_ZOOM / 2)  # halfway through the zoom
    assert not cam.holding and fit < cam.scale < 1.0
    point = (321.0, 654.0)
    assert cam.to_world(*cam.to_screen(*point)) == pytest.approx(point)
    cam.update(INTRO_ZOOM)  # done
    assert not cam.in_intro and cam.scale == 1.0 and cam.mode == FOLLOW
    assert cam.to_screen(600, 1100) == pytest.approx(target)


def test_no_intro_on_a_stage_that_fits():
    cam = Camera.for_stage(855, 480, pygame.Rect(0, 0, 855, 480))
    cam.start_intro()
    assert not cam.in_intro


def _game(stage, map_intro=True):
    from src.envs.maze_car.env import MazeCarEnv

    config = get_maze_car_config()
    config.window.map_intro = map_intro
    env = MazeCarEnv(config, stage=load_stage(stage))
    env.reset(seed=1)
    return env


def test_each_new_round_starts_the_intro():
    env = _game("arena")
    renderer = env.renderer
    renderer.draw(env.world, 1.0, env.reward_status(), None)
    assert renderer.camera.in_intro
    renderer.camera.skip_intro()
    renderer.draw(env.world, 1.0, env.reward_status(), None)
    assert not renderer.camera.in_intro  # the same round: no new intro
    env.reset(seed=2)  # a new round (restart)
    renderer.draw(env.world, 1.0, env.reward_status(), None)
    assert renderer.camera.in_intro


def test_the_intro_can_be_turned_off():
    env = _game("arena", map_intro=False)
    env.renderer.draw(env.world, 1.0, env.reward_status(), None)
    assert not env.renderer.camera.in_intro


def test_a_key_cuts_the_overview_short_but_never_the_zoom():
    from src.render.camera import INTRO_HOLD, INTRO_ZOOM

    env = _game("arena")
    renderer = env.renderer
    renderer.draw(env.world, 1.0, env.reward_status(), None)
    assert renderer.modal_open  # the game waits for the intro
    for key in (pygame.K_w, pygame.K_f, pygame.K_p):
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key))
    renderer.poll_events()
    cam = renderer.camera
    assert cam.in_intro and not cam.holding  # on to the zoom
    assert cam.intro == INTRO_HOLD
    assert renderer.keys_pressed == []  # ignored, F included
    assert cam.mode == FOLLOW
    cam.update(INTRO_ZOOM)
    assert not cam.in_intro and not renderer.modal_open  # keys count again


def test_live_play_waits_for_the_intro():
    from src.envs.maze_car.demo import MazeCarDemo
    from src.sim.resources import SimClock

    config = get_maze_car_config()
    config.stage = "arena"
    demo = MazeCarDemo(
        config, driver="heuristic", autorun=False, record=False
    )
    demo.frame(0.0)  # draws: the intro starts
    assert demo.env.renderer.camera.in_intro
    demo.frame(1.0)  # a heuristic would drive at once, but it waits
    assert demo.env.world.resource(SimClock).step == 0


# Markers for checkpoints outside the view


def test_a_marker_sits_on_the_edge_toward_the_checkpoint():
    from src.render.renderer import offscreen_marker

    view = pygame.Rect(0, 0, 800, 400)
    start = (400, 200)
    assert offscreen_marker(start, (500, 300), view, 16) is None  # in view
    (x, y), (dx, dy) = offscreen_marker(start, (1400, 200), view, 16)
    assert (x, y) == pytest.approx((784, 200)) and (dx, dy) == (1.0, 0.0)
    (x, y), _ = offscreen_marker(start, (400, -300), view, 16)
    assert (x, y) == pytest.approx((400, 16))  # the top edge
    (x, y), (dx, dy) = offscreen_marker(start, (1400, 1200), view, 16)
    assert y == pytest.approx(384) and dx > 0 and dy > 0  # a corner-ish way


def test_the_frame_draws_a_marker_only_when_the_checkpoint_is_away():
    env = _game("arena", map_intro=False)
    renderer = env.renderer
    polygons = []
    real = pygame.draw.polygon

    def spy(surface, color, points, *args, **kwargs):
        polygons.append((color, points))
        return real(surface, color, points, *args, **kwargs)

    from src.render import theme
    from src.sim.components import Checkpoint, Transform

    (spot,) = [t for _, (t, _) in env.world.query(Transform, Checkpoint)]
    car = env.world.component(env.car, Transform)
    pygame.draw.polygon = spy
    try:
        spot.x, spot.y = car.x + 100, car.y - 100  # in view
        renderer.draw(env.world, 1.0, env.reward_status(), None)
        seen = [p for c, p in polygons if c == theme.CHECKPOINT]
        spot.x, spot.y = 20.0, 20.0  # the far top left: out of view
        polygons.clear()
        renderer.draw(env.world, 1.0, env.reward_status(), None)
        away = [p for c, p in polygons if c == theme.CHECKPOINT]
    finally:
        pygame.draw.polygon = real
    assert not seen and len(away) == 1

