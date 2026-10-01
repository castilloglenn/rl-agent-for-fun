"""The side panel's instruments (7f3): steady numbers, and shapes for
what changes every frame.
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

from src.render.instruments import (  # noqa: E402
    REFRESH_MS,
    Readouts,
    draw_radar,
    ray_label,
)


def test_a_number_shows_its_mean_and_holds_between_refreshes():
    readouts = Readouts()
    fmt = "{:.0f}".format
    assert readouts.text("v", 10, fmt, now=0) == "10"  # first: at once
    assert readouts.text("v", 20, fmt, now=100) == "10"  # held
    assert readouts.text("v", 40, fmt, now=200) == "10"
    # Due again: the mean of what came since (20, 40, 60).
    assert readouts.text("v", 60, fmt, now=REFRESH_MS) == "40"


def test_an_angle_holds_its_latest_value_not_a_mean():
    readouts = Readouts()
    fmt = "{:.0f}".format
    readouts.text("a", 359, fmt, now=0, mean=False)
    readouts.text("a", 358, fmt, now=100, mean=False)
    assert readouts.text("a", 1, fmt, now=REFRESH_MS, mean=False) == "1"


def test_ray_labels():
    assert ray_label("front") == "front"
    assert ray_label("front_left_15") == "front-left 15°"
    assert ray_label("back_right") == "back-right"


def test_the_radar_finds_the_closest_ray():
    from src.sim.components import Ray

    pygame.init()
    surface = pygame.Surface((200, 200))
    rays = [
        Ray("front", 0, 0), Ray("left", 90, 0), Ray("front_left_15", 15, 0)
    ]
    for ray, distance in zip(rays, (400.0, 42.0, 120.0)):
        ray.distance = distance
    closest = draw_radar(surface, (100, 100), 50, rays, {}, 100.0, 60.0)
    assert closest == ("left", 42.0)


def test_the_checkpoint_angle_is_relative_and_left_positive():
    from src.render.panels import CarInfo, nearest_checkpoint
    from src.sim.components import ActionInput, Checkpoint, Score, Transform
    from src.ecs import World

    world = World()
    spot = world.create_entity()
    world.add_component(spot, Transform(100.0, 0.0))  # straight up
    world.add_component(spot, Checkpoint())
    car = CarInfo(
        "c", 0.0, "Idle", 0.0, 0.0, (100.0, 100.0), ActionInput(), [],
        False, Score(), 1.0,
    )  # heading 0: facing east, so "up" is to its left
    distance, relative = nearest_checkpoint(world, car)
    assert distance == 100.0 and round(relative) == 90


def test_the_mind_card_draws_stopped_and_moving():
    from src.config import get_maze_car_config
    from src.render import theme
    from src.render.panels import (
        MindInfo,
        ModeInfo,
        car_infos,
        draw_game_panel,
    )
    from src.sim.factories import create_game

    pygame.init()
    world, _ = create_game(get_maze_car_config(), seed=1)
    surface = pygame.Surface((260, 600))
    readouts = Readouts()
    for stopped in (True, False):
        odds = tuple([0.0, 0.5, 0.25, 0.0] * 3) if stopped else (1 / 12,) * 12
        mode = ModeInfo(
            "Live play", theme.TEXT, (), mind=MindInfo(odds, -0.3, stopped)
        )
        draw_game_panel(
            surface, surface.get_rect(), world, car_infos(world),
            mode=mode, readouts=readouts,
        )
