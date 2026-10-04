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


def test_the_fuel_angle_is_relative_and_left_positive():
    from src.render.panels import CarInfo, nearest_fuel
    from src.sim.components import ActionInput, Fuel, Score, Transform
    from src.ecs import World

    world = World()
    spot = world.create_entity()
    world.add_component(spot, Transform(100.0, 0.0))  # straight up
    world.add_component(spot, Fuel())
    car = CarInfo(
        "c", 0.0, "Idle", 0.0, 0.0, (100.0, 100.0), ActionInput(), [],
        False, Score(), 1.0,
    )  # heading 0: facing east, so "up" is to its left
    distance, relative = nearest_fuel(world, car)
    assert distance == 100.0 and round(relative) == 90


def test_the_mind_card_draws_stopped_and_moving():
    """MIND (7f10): a grid of the 12 actions on the right, with the
    picked one outlined and the blocked ones crossed when stopped.
    """
    from src.config import get_maze_car_config
    from src.render import panels, theme
    from src.render.panels import MindInfo, ModeInfo, car_infos
    from src.sim.factories import create_game

    pygame.init()
    config = get_maze_car_config()
    world, _ = create_game(config, seed=1)
    surface = pygame.Surface((260, 600))
    readouts = Readouts()
    drawn = []
    real = panels.draw_text

    def spy(surface, text, *args, **kwargs):
        drawn.append(text)
        return real(surface, text, *args, **kwargs)

    panels.draw_text = spy
    try:
        for stopped in (True, False):
            odds = (
                tuple([0.0, 0.5, 0.25, 0.0] * 3) if stopped
                else (1 / 12,) * 12
            )
            mind = MindInfo(odds, -0.3, stopped, choice=5)
            mode = ModeInfo("Live play", theme.TEXT, (), mind=mind)
            panels.draw_car_panel(
                surface, surface.get_rect(), world, car_infos(world),
                config.hud, mode=mode, readouts=readouts,
            )
    finally:
        panels.draw_text = real
    assert "MIND · stopped: gas or reverse" in drawn and "MIND" in drawn
    for label in ("left", "straight", "right", "gas", "coast", "rev"):
        assert label in drawn


def test_smoothing_glides_toward_new_values():
    readouts = Readouts()
    assert readouts.smooth("k", [0.0], now=0) == [0.0]  # first: as given
    halfway = readouts.smooth("k", [1.0], now=208)[0]  # about 0.69 tau
    assert 0.4 < halfway < 0.6
    assert readouts.smooth("k", [1.0], now=3000)[0] > 0.99
