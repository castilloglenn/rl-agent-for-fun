"""Rewards and checkpoints (roadmap step 3g)."""

import math

import pytest

from src.config import get_maze_car_config
from src.envs.maze_car.env import MazeCarEnv
from src.sim.components import (
    ActionInput,
    Checkpoint,
    Motion,
    Score,
    Sensors,
    Transform,
)
from src.sim.factories import create_game
from src.sim.geometry import circle_touches_car
from src.sim.resources import EventLog, Field

GAS = ActionInput(gas=True)


def _game(seed=0):
    return create_game(get_maze_car_config(), label="Tester", seed=seed)


def _checkpoint(world):
    return world.query(Transform, Checkpoint)[0]


def _park_checkpoint_far(world):
    """Moves the checkpoint out of the way, to test distance points."""
    _, (spot, _) = _checkpoint(world)
    field = world.resource(Field).rect
    spot.x, spot.y = field.left + 40, field.top + 40


def test_one_point_per_10_px_forward():
    world, car = _game()
    _park_checkpoint_far(world)
    driven = 0.0
    for _ in range(150):
        world.add_component(car, GAS)
        world.step()
        driven += world.component(car, Motion).moved
    score = world.component(car, Score)
    assert score.distance_points == math.floor(driven / 10)
    assert score.total == score.distance_points


def test_reversing_and_standing_still_earn_nothing():
    world, car = _game()
    _park_checkpoint_far(world)
    for action in [ActionInput(reverse=True)] * 120 + [ActionInput()] * 60:
        world.add_component(car, action)
        world.step()
    assert world.component(car, Score).total == 0


def test_last_step_counts_this_steps_points():
    world, car = _game()
    _park_checkpoint_far(world)
    total = 0.0
    for _ in range(200):
        world.add_component(car, GAS)
        world.step()
        total += world.component(car, Score).last_step
    assert total == world.component(car, Score).total


def test_checkpoint_gives_100_and_respawns():
    world, car = _game()
    transform = world.component(car, Transform)
    checkpoint, (spot, _) = _checkpoint(world)
    spot.x, spot.y = transform.x + 60, transform.y  # straight ahead

    for _ in range(120):
        world.add_component(car, GAS)
        world.step()
        if world.component(car, Score).checkpoints:
            break

    score = world.component(car, Score)
    assert score.checkpoints == 1
    assert score.checkpoint_points == 100
    events = world.resource(EventLog).of_kind("checkpoint")
    assert events[-1].text == "Tester reached a checkpoint +100"

    # Respawned: away from the car and the border.
    field = world.resource(Field).rect
    assert math.dist((spot.x, spot.y), (transform.x, transform.y)) >= 100
    assert field.left + 40 <= spot.x <= field.right - 40
    assert field.top + 40 <= spot.y <= field.bottom - 40
    assert world.entity_exists(checkpoint)  # same entity, moved


@pytest.mark.parametrize("seed", [0, 1, 42])
def test_spawns_repeat_with_the_same_seed(seed):
    spots = []
    for _ in range(2):
        world, _ = _game(seed)
        _, (spot, _) = _checkpoint(world)
        spots.append((spot.x, spot.y))
    assert spots[0] == spots[1]


def test_different_seeds_give_different_spawns():
    spots = set()
    for seed in range(5):
        world, _ = _game(seed)
        _, (spot, _) = _checkpoint(world)
        spots.add((round(spot.x, 3), round(spot.y, 3)))
    assert len(spots) == 5


def test_first_checkpoint_respects_the_spawn_rules():
    for seed in range(20):
        world, car = _game(seed)
        _, (spot, _) = _checkpoint(world)
        transform = world.component(car, Transform)
        field = world.resource(Field).rect
        assert math.dist((spot.x, spot.y), (transform.x, transform.y)) >= 100
        assert field.left + 40 <= spot.x <= field.right - 40
        assert field.top + 40 <= spot.y <= field.bottom - 40


def test_circle_touches_rotated_car():
    # Car at the origin, 24 x 16, facing right: front edge at x = 12.
    assert circle_touches_car(12 + 15, 0, 15, 0, 0, 0, 24, 16)  # just touching
    assert not circle_touches_car(12 + 15.1, 0, 15, 0, 0, 0, 24, 16)
    # Rotated 90°, the front edge is at y = -12 (screen up).
    assert circle_touches_car(0, -12 - 15, 15, 0, 0, 90, 24, 16)
    assert not circle_touches_car(12 + 15, 0, 15, 0, 0, 90, 24, 16)


def test_rays_ignore_checkpoints():
    world, car = _game()
    transform = world.component(car, Transform)
    before = {r.name: r.distance for r in world.component(car, Sensors).rays}
    _, (spot, _) = _checkpoint(world)
    spot.x, spot.y = transform.x + 100, transform.y  # in the front ray's path
    world.step()
    after = {r.name: r.distance for r in world.component(car, Sensors).rays}
    assert after == before


def test_env_returns_step_rewards_and_the_score():
    config = get_maze_car_config()
    config.show_gui = False
    env = MazeCarEnv(config)
    rewards = [env.game_step((False, False, True, False, False))[0]]
    for _ in range(199):
        rewards.append(env.game_step((False, False, True, False, False))[0])
    assert sum(rewards) == env.score > 0


def test_demo_resets_pick_fresh_seeds():
    from src.sim.resources import Rng

    config = get_maze_car_config()
    config.show_gui = False
    env = MazeCarEnv(config, random_seeds=True)
    seeds = set()
    for _ in range(5):
        env.reset()
        seeds.add(env.world.resource(Rng).seed)
    assert len(seeds) > 1

    fixed = MazeCarEnv(config)
    fixed.reset()
    assert fixed.world.resource(Rng).seed == config.game.seed
