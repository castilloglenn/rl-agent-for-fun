"""Spawn schedules: stage + seed decide every spawn (decision 009)."""

import math

from src.sim.spawning import SpawnSchedule
from src.sim.stage import CheckpointRules

RULES = CheckpointRules(radius=15, border_margin=40, min_car_distance=100)


def _schedule(seed=0, name="checkpoints", rules=RULES):
    return SpawnSchedule(name, seed, rules, width=855, height=480)


def _far_from(spot):
    """A car position far from `spot`."""
    return (855 - spot[0], 480 - spot[1])


def test_the_driving_does_not_change_the_sequence():
    """Two drivers in different places get the same spots."""
    first, second = _schedule(seed=5), _schedule(seed=5)
    reference = [first.candidates(slot)[0] for slot in range(20)]
    for slot in range(20):
        # Driver A and B are in different places, both far from the spot.
        car_a = _far_from(reference[slot])
        car_b = (car_a[0] * 0.9 + 20, car_a[1] * 0.9 + 20)
        if math.dist(car_b, reference[slot]) < 100:
            car_b = car_a
        assert first.next_spot([car_a]) == reference[slot]
        assert second.next_spot([car_b]) == reference[slot]


def test_backup_candidate_when_a_car_is_on_the_spot():
    schedule = _schedule(seed=5)
    first_choice = schedule.candidates(0)[0]
    spot = schedule.next_spot([first_choice])  # a car right on it
    assert spot != first_choice
    assert math.dist(spot, first_choice) >= 100
    # Later slots don't depend on that: slot 1 is unaffected.
    assert schedule.next_spot([]) == _schedule(seed=5).candidates(1)[0]


def test_spots_respect_the_border_margin():
    schedule = _schedule(seed=9)
    for _ in range(200):
        x, y = schedule.next_spot([])
        assert 40 <= x <= 855 - 40 and 40 <= y <= 480 - 40


def test_seeds_and_spawners_have_their_own_streams():
    base = [_schedule(seed=1).next_spot([]) for _ in range(1)]
    assert base != [_schedule(seed=2).next_spot([])]
    assert base != [_schedule(seed=1, name="fuel").next_spot([])]
    # Same seed and name: identical, no matter what else exists.
    assert base == [_schedule(seed=1).next_spot([])]


def test_scripted_points_in_order_then_loop():
    rules = CheckpointRules(mode="scripted", points=((100, 100), (700, 400)))
    schedule = _schedule(rules=rules)
    spots = [schedule.next_spot([(100, 100)]) for _ in range(5)]
    assert spots == [(100, 100), (700, 400), (100, 100), (700, 400), (100, 100)]


def test_crowded_stage_picks_the_least_crowded_candidate():
    schedule = _schedule(seed=3)
    candidates = schedule.candidates(0)
    cars = [(427, 240)]  # everything within 100 px only if the stage is tiny
    tiny = SpawnSchedule(
        "checkpoints",
        3,
        CheckpointRules(border_margin=40, min_car_distance=10_000),
        width=855,
        height=480,
    )
    spot = tiny.next_spot(cars)
    assert spot == max(candidates, key=lambda c: math.dist(c, cars[0]))
