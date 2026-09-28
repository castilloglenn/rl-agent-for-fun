"""Roadmap step 7b: the camera. Drawing only: a stage that fits shows
1:1 as before; a bigger one is fitted to the view, or followed (F).
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

from src.config import get_maze_car_config  # noqa: E402
from src.render import camera  # noqa: E402
from src.render.camera import FIT, FOLLOW, Camera  # noqa: E402
from src.sim.stage import load_stage  # noqa: E402


def test_view_sizes():
    assert camera.view_size(855, 480) == (855, 480)  # the box: 1:1
    assert camera.fit_scale(855, 480) == 1.0
    # The arena (1200 x 1200) fits 640 tall; the view keeps the box's
    # width, so the top bar above it has room.
    assert camera.fit_scale(1200, 1200) == pytest.approx(640 / 1200)
    assert camera.view_size(1200, 1200) == (855, 640)
    assert camera.view_size(2200, 600) == (1100, 480)  # wide: fits 1100


def _arena_camera():
    view = pygame.Rect(282, 76, 855, 640)
    return Camera.for_stage(1200, 1200, view, camera.MAX_FIELD)


def test_fit_centers_the_scaled_stage():
    cam = _arena_camera()
    assert cam.zoomable and cam.mode == FIT
    s = 640 / 1200
    left = 282 + (855 - 1200 * s) / 2
    assert cam.to_screen(0, 0) == pytest.approx((left, 76))
    assert cam.to_screen(1200, 1200) == pytest.approx((left + 640, 716))
    assert cam.label() == "fit 53%"


def test_screen_to_world_and_back():
    cam = _arena_camera()
    for mode in (FIT, FOLLOW):
        cam.mode = mode
        cam.follow(700, 500)
        point = (123.5, 987.25)
        assert cam.to_world(*cam.to_screen(*point)) == pytest.approx(point)


def test_follow_is_1_to_1_and_stops_at_the_edges():
    cam = _arena_camera()
    cam.toggle()
    assert cam.mode == FOLLOW and cam.scale == 1.0
    cam.follow(600, 600)  # the middle: centered on it
    assert cam.to_screen(600, 600) == pytest.approx(cam.view.center, abs=1)
    cam.follow(10, 10)  # near the top left: the stage's corner stays put
    assert cam.origin == (0.0, 0.0)
    cam.follow(1190, 1190)
    assert cam.origin == (1200 - 855, 1200 - 640)
    cam.toggle()
    assert cam.mode == FIT


def test_a_stage_that_fits_never_switches():
    cam = Camera.for_stage(
        855, 480, pygame.Rect(0, 0, 855, 480), camera.MAX_FIELD
    )
    cam.toggle()
    assert cam.mode == FIT and cam.scale == 1.0 and cam.label() == "1:1"
    assert cam.to_screen(10, 20) == (10, 20)


def test_the_window_stays_bounded_for_a_big_stage():
    from src.render.renderer import Renderer

    config = get_maze_car_config()
    box = Renderer(config, load_stage("box"))
    arena = Renderer(config, load_stage("arena"))
    assert arena.layout.field_view.size == (855, 640)
    assert arena.layout.window.w == box.layout.window.w
    assert arena.layout.window.h <= box.layout.window.h + 160
    assert box.offset == box.layout.field_view.topleft  # unchanged


def test_f_switches_the_camera(capsys):
    from src.render.renderer import Renderer

    renderer = Renderer(get_maze_car_config(), load_stage("arena"))
    renderer._key(pygame.K_f, False, set())
    assert renderer.camera.mode == FOLLOW
    x, y = renderer.camera.to_screen(100, 200)
    pygame.event.post(
        pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(x, y))
    )
    renderer.poll_events()
    assert "click at world (100, 200)" in capsys.readouterr().out
