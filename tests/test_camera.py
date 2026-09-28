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
