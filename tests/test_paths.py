"""Path distance around walls (roadmap 7e, decision 041)."""

import math

from src.sim.paths import PathField

FIELD = (0, 0, 200, 100)


def test_an_open_field_is_the_straight_line():
    path = PathField(FIELD, [], (150, 20))
    assert path.distance(50, 20) == 100
    assert path.distance(150, 60) == 40


def test_a_wall_makes_it_go_around():
    wall = [(95, 0, 105, 70)]  # from the top down to y 70
    path = PathField(FIELD, wall, (150, 20))
    around = path.distance(50, 20)
    # Down past the wall's end (70, plus the car's clearance) and back up:
    # at least twice the drop from 20 to 78.
    assert around > 2 * math.hypot(45, 58)
    assert around < 200
    no_wall = PathField(FIELD, [], (150, 20)).distance(50, 20)
    assert around > no_wall + 50


def test_a_gap_narrower_than_the_car_is_closed():
    # A wall across the field with a 10 px gap (the car is 16 px wide).
    walls = [(95, 0, 105, 45), (95, 55, 105, 100)]
    path = PathField((0, 0, 200, 100), walls, (150, 50))
    assert math.isinf(path.distance(50, 50))  # no way through at all
    wide = [(95, 0, 105, 30), (95, 70, 105, 100)]  # a 40 px gap
    assert PathField(FIELD, wide, (150, 50)).distance(50, 50) < 110


def test_closer_along_the_path_is_smaller():
    wall = [(95, 0, 105, 70)]
    path = PathField(FIELD, wall, (150, 20))
    route = [(50, 20), (70, 60), (100, 85), (130, 60), (150, 30)]
    distances = [path.distance(x, y) for x, y in route]
    assert distances == sorted(distances, reverse=True)
    # At the goal: within one cell's diagonal (the grid's precision; a
    # checkpoint's radius is 15 px, so it's reached before that matters).
    assert path.distance(150, 20) <= 10 * math.sqrt(2) + 1e-9


def test_it_is_deterministic():
    wall = [(95, 0, 105, 70)]
    one = PathField(FIELD, wall, (150, 20)).dist
    two = PathField(FIELD, wall, (150, 20)).dist
    assert one == two
