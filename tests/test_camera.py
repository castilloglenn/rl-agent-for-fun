"""Roadmap step 7b: the camera and the mini map. Drawing only. The field
view is the box's size on every stage: a stage that fits shows 1:1, a
bigger one is followed at 1:1 (or fitted with F), with a mini map (M).
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


def test_every_stage_gets_the_same_window():
    box, arena = _renderer("box"), _renderer("arena")
    assert arena.layout.window.size == box.layout.window.size
    assert box.offset == box.layout.field_view.topleft  # unchanged


def test_keys_f_and_m(capsys):
    renderer = _renderer("arena")
    renderer._key(pygame.K_m, False, set())
    assert not renderer.show_minimap
    renderer._key(pygame.K_f, False, set())
    assert renderer.camera.mode == FIT
    x, y = renderer.camera.to_screen(100, 200)
    pygame.event.post(
        pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(x, y))
    )
    renderer.poll_events()
    assert "click at world (100, 200)" in capsys.readouterr().out


def _drawn_frame(stage, car_at=None):
    from src.envs.maze_car.env import MazeCarEnv
    from src.sim.components import PreviousPose, Transform

    config = get_maze_car_config()
    env = MazeCarEnv(config, stage=load_stage(stage))
    env.reset(seed=1)
    if car_at:
        transform = env.world.component(env.car, Transform)
        transform.x, transform.y = car_at
        previous = env.world.component(env.car, PreviousPose)
        previous.center_x, previous.center_y = car_at
    boxes = []
    real = pygame.draw.rect

    def spy(surface, color, rect, *args, **kwargs):
        boxes.append(pygame.Rect(rect))
        return real(surface, color, rect, *args, **kwargs)

    pygame.draw.rect = spy
    try:
        env.renderer.draw(env.world, 1.0, env.reward_status(), None)
    finally:
        pygame.draw.rect = real
    return env.renderer, boxes


def _minimap(renderer, boxes):
    view = renderer.camera.view
    side = renderer.MINIMAP
    return [
        b for b in boxes
        if max(b.w, b.h) == side and view.contains(b) and b.w != view.w
    ]


def test_the_mini_map_starts_top_right():
    renderer, boxes = _drawn_frame("arena")
    (mini,) = _minimap(renderer, boxes)
    view = renderer.camera.view
    assert mini.topright == (view.right - 10, view.top + 10)


def test_the_mini_map_moves_away_from_where_the_car_heads():
    from src.render.renderer import minimap_side

    up_right, up_left = (0.7, -0.7), (-0.7, -0.7)
    down_right, straight_up = (0.7, 0.7), (0.0, -1.0)
    assert minimap_side("right", up_right) == "left"
    assert minimap_side("left", up_right) == "left"  # stays
    assert minimap_side("left", down_right) == "left"
    assert minimap_side("left", straight_up) == "left"
    assert minimap_side("left", up_left) == "right"
    assert minimap_side("right", up_left) == "right"
    assert minimap_side("right", None) == "right"  # standing still


def test_reversing_travels_backward():
    from src.envs.maze_car.env import MazeCarEnv
    from src.sim.components import Motion, Transform

    env = MazeCarEnv(get_maze_car_config(), stage=load_stage("arena"))
    env.reset(seed=1)
    world = env.world
    world.component(env.car, Transform).angle = 225  # facing down, left
    world.component(env.car, Motion).speed = -1.0  # rolling up and right
    dx, dy = env.renderer._travel(world)
    assert dx > 0 and dy < 0
    world.component(env.car, Motion).speed = 0.0
    assert env.renderer._travel(world) is None


def test_no_mini_map_on_a_small_stage():
    renderer, boxes = _drawn_frame("box")
    assert not _minimap(renderer, boxes)
