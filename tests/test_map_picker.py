"""The game window's MAPS box: M picks the map to play while watching a
driver, with a preview of the highlighted one. Nothing here writes a
file (the settings stay in memory: the test config has no settings file).
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

from src.config import get_maze_car_config  # noqa: E402
from src.envs.maze_car.demo import MazeCarDemo  # noqa: E402
from src.render.map_picker import describe, visible  # noqa: E402
from src.utils import named_files  # noqa: E402


def _key(demo, key):
    demo.env.renderer._key(key, False, set())


def _watch(**kwargs):
    return MazeCarDemo(
        get_maze_car_config(),
        driver="heuristic",
        autorun=False,
        record=False,
        **kwargs,
    )


def test_watching_offers_every_map_and_marks_this_one():
    demo = _watch()
    renderer = demo.env.renderer
    names = named_files.ordered("stages")
    assert demo.maps == names
    assert len(renderer.map_choices) == len(names)
    assert renderer.map_current == names.index("box")
    _key(demo, pygame.K_m)
    assert renderer.show_maps and renderer.modal_open
    assert renderer.map_row == names.index("box")  # starts on this one
    _key(demo, pygame.K_m)  # M again closes it
    assert not renderer.show_maps


def test_picking_a_map_plays_a_fresh_round_there():
    demo = _watch()
    renderer = demo.env.renderer
    target = demo.maps.index("pillars")
    _key(demo, pygame.K_m)
    while renderer.map_row != target:
        _key(demo, pygame.K_DOWN)
    _key(demo, pygame.K_RETURN)
    assert not renderer.show_maps
    demo.frame(0.0)  # the window takes the pick
    assert demo.env.stage.name == "pillars"
    assert demo.env.renderer is not renderer  # a window for its size
    assert demo.env.renderer.map_current == target
    assert demo.world is demo.env.world and demo.trail  # a fresh round
    demo.frame(0.05)  # and it plays


def test_esc_closes_the_box_without_switching():
    demo = _watch()
    _key(demo, pygame.K_m)
    _key(demo, pygame.K_DOWN)
    _key(demo, pygame.K_ESCAPE)
    assert not demo.env.renderer.show_maps
    assert demo.env.renderer.take_map_pick() is None
    assert not demo.env.renderer.confirm_quit  # Esc was the box's


def test_no_maps_while_you_drive_or_test_drive():
    for demo in (
        MazeCarDemo(get_maze_car_config(), autorun=False, record=False),
        _watch(test_drive="saved"),
    ):
        renderer = demo.env.renderer
        assert renderer.map_choices == [] and demo.maps == []
        _key(demo, pygame.K_m)
        assert not renderer.show_maps  # M is just a key there


def test_the_box_draws_with_its_preview():
    demo = _watch()
    _key(demo, pygame.K_m)
    demo.frame(0.0)  # draws the box over the field


def test_the_caption_and_the_scrolling_list():
    stage = {
        "size": [1300, 700],
        "walls": [[0, 0, 10, 10]] * 3,
        "fuel": {
            "mode": "scripted",
            "points": [[1, 1]] * 9,
            "start": "seeded",
        },
    }
    text = describe(stage)
    assert text == (
        "1300 × 700 · 3 walls · scripted, 9 fuels, any start"
    )
    assert "random fuel" in describe({"size": [855, 480]})
    assert visible(5, 2, 10) == range(5)  # all fit
    assert visible(30, 0, 10) == range(0, 10)
    assert 25 in visible(30, 25, 10) and visible(30, 29, 10)[-1] == 29
