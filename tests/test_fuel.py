"""Fuel (roadmap 9a2): a tank every throttle and turn burns, fuels that
refill it, up to 3 on the map at once, and a car that runs dry coasting
to a stop and out.
"""

import math
from dataclasses import replace

import pytest

from src.config import get_maze_car_config
from src.drivers.registry import make_driver
from src.envs.maze_car.env import MazeCarEnv
from src.replay.recorder import ReplayRecorder, human_driver
from src.replay.replayer import Replayer
from src.sim.components import (
    ActionInput,
    Eliminated,
    Fuel,
    Motion,
    Score,
    Tank,
    Transform,
)
from src.sim.factories import create_game
from src.sim.resources import EventLog
from src.sim.rules import Rules, load_rules
from src.sim.stage import Stage, load_stage

STEPS = 120  # a second


def _game(stage="box", rules=None, seed=0):
    stage = load_stage(stage) if isinstance(stage, str) else stage
    return create_game(
        get_maze_car_config(), seed=seed, stage=stage, rules=rules
    )


def _hold(world, car, action: ActionInput, steps: int) -> None:
    for _ in range(steps):
        world.add_component(car, action)
        world.step()


def _park_fuels(world, x=40.0, y=40.0) -> None:
    """Every fuel to a corner, out of the car's way."""
    for i, (_, (spot, _)) in enumerate(world.query(Transform, Fuel)):
        spot.x, spot.y = x + 30 * i, y


# The tank


@pytest.mark.parametrize(
    "action, left",
    [
        (ActionInput(), 99.0),  # idle: 1/s
        (ActionInput(brake=True), 99.0),  # braking burns nothing more
        (ActionInput(gas=True), 95.0),  # throttle: +4/s
        (ActionInput(reverse=True), 95.0),
        (ActionInput(gas=True, turn_left=True), 93.5),  # steering: +1.5/s
    ],
)
def test_every_throttle_and_turn_burns_fuel(action, left):
    world, car = _game()
    _park_fuels(world)
    _hold(world, car, action, STEPS)
    assert world.component(car, Tank).level == pytest.approx(left)


def test_a_fuel_refills_up_to_the_full_tank():
    world, car = _game()
    tank = world.component(car, Tank)
    car_at = world.component(car, Transform)
    (_, (spot, _)), *_ = world.query(Transform, Fuel)
    for level in (90.0, 20.0):  # a fuel puts back 25
        tank.level = level
        spot.x, spot.y = car_at.x, car_at.y  # under the car
        world.step()  # the idle burn, then the refill
        assert tank.level == pytest.approx(min(level - 1 / STEPS + 25, 100))


def test_running_dry_kills_the_engine_then_the_car_coasts_out():
    world, car = _game()
    _park_fuels(world)
    _hold(world, car, ActionInput(gas=True), STEPS)  # up to speed
    world.component(car, Tank).level = 0.01
    _hold(world, car, ActionInput(gas=True), 1)  # its last drop
    assert world.component(car, Tank).empty
    motion = world.component(car, Motion)
    speed_before = motion.speed
    _hold(world, car, ActionInput(gas=True), 1)
    assert 0 < motion.speed < speed_before  # gas does nothing: coasting
    for _ in range(10 * STEPS):
        if world.try_component(car, Eliminated):
            break
        _hold(world, car, ActionInput(gas=True, turn_left=True), 1)
    out = world.component(car, Eliminated)
    assert out.reason == "out_of_fuel"
    log = [event.text for event in world.resource(EventLog).events]
    assert any("Out of fuel" in text for text in log)
    assert any("ran out of fuel" in text for text in log)


def test_coasting_into_a_fuel_restarts_the_engine():
    world, car = _game()
    _park_fuels(world)
    _hold(world, car, ActionInput(gas=True), STEPS)
    tank = world.component(car, Tank)
    tank.level = 0.0
    car_at = world.component(car, Transform)
    (_, (spot, _)), *_ = world.query(Transform, Fuel)
    spot.x, spot.y = car_at.x + 30, car_at.y  # just ahead
    _hold(world, car, ActionInput(), 30)
    assert tank.level > 20 and not world.try_component(car, Eliminated)


def test_the_env_ends_on_out_of_fuel():
    config = get_maze_car_config()
    config.show_gui = False
    env = MazeCarEnv(config)
    env.reset(seed=0)
    env.world.component(env.car, Tank).level = 0.0
    for _ in range(STEPS):
        *_, terminated, truncated, info = env.step((False,) * 5)
        if terminated:
            break
    assert terminated and info["eliminated"] == "out_of_fuel"


def test_rules_without_a_tank_burn_nothing():
    standard = load_rules("standard").to_dict()
    del standard["tank"]
    world, car = _game(rules=Rules.from_dict({**standard, "name": "free"}))
    assert world.try_component(car, Tank) is None
    _hold(world, car, ActionInput(gas=True), STEPS)
    assert not world.try_component(car, Eliminated)


# Up to 3 fuels at once


def test_three_fuels_apart_from_each_other_and_the_car():
    world, car = _game("arena")
    spots = [(s.x, s.y) for _, (s, _) in world.query(Transform, Fuel)]
    assert len(spots) == 3
    car_at = world.component(car, Transform)
    distance = world.resource(Stage).fuel.min_car_distance
    for i, a in enumerate(spots):
        assert math.dist(a, (car_at.x, car_at.y)) >= distance
        for b in spots[i + 1:]:
            assert math.dist(a, b) >= distance


def test_the_skill_test_maps_keep_one_fuel():
    for name in ("skill_gaps", "skill_detour", "skill_long", "skill_pillars",
                 "skill_corridor"):
        world, _ = _game(name)
        assert len(world.query(Transform, Fuel)) == 1, name


def test_scripted_fuels_are_a_sliding_window():
    """The next 3 in order; taking any brings in the next."""
    stage = load_stage("course_small")  # seeded: from the first point here
    stage = replace(stage, fuel=replace(stage.fuel, start="first"))
    points = [tuple(p) for p in stage.fuel.points]
    world, car = _game(stage)
    out = sorted((s.x, s.y) for _, (s, _) in world.query(Transform, Fuel))
    assert out == sorted(points[:3])
    middle = next(
        s for _, (s, _) in world.query(Transform, Fuel)
        if (s.x, s.y) == points[1]
    )
    car_at = world.component(car, Transform)
    car_at.x, car_at.y = middle.x, middle.y  # take the second
    world.step()
    out = sorted((s.x, s.y) for _, (s, _) in world.query(Transform, Fuel))
    assert out == sorted([points[0], points[2], points[3]])


def test_a_short_sequence_never_shows_a_point_twice():
    stage = load_stage("skill_detour").with_at_once(3)  # 2 points
    world, _ = _game(stage)
    assert len(world.query(Transform, Fuel)) == 2


# Scoring


def test_points_come_from_fuel_only():
    world, car = _game()
    _park_fuels(world)
    _hold(world, car, ActionInput(gas=True), STEPS)
    score = world.component(car, Score)
    assert score.total == 0 and score.distance_points == 0
    car_at = world.component(car, Transform)
    (_, (spot, _)), *_ = world.query(Transform, Fuel)
    spot.x, spot.y = car_at.x, car_at.y
    world.step()
    assert score.total == 100 and score.fuels == 1


def test_rounds_with_fuel_replay_exactly():
    config = get_maze_car_config()
    config.show_gui = False
    recorder = ReplayRecorder({"1": human_driver("zen")})
    env = MazeCarEnv(config, stage=load_stage("arena"), recorder=recorder)
    observation, _ = env.reset(seed=3)
    driver = make_driver("heuristic")
    taken = 0
    while True:
        observation, _, terminated, truncated, info = env.step(
            driver.act(observation)
        )
        if terminated or truncated:
            break
    taken = info["fuels"]
    env.finish_recording()
    assert taken > 0  # it refueled along the way
    assert Replayer(recorder.replay).run().ok


# The agent's reward (9c)


def _env(stage="box"):
    config = get_maze_car_config()
    config.show_gui = False
    env = MazeCarEnv(config, stage=load_stage(stage))
    env.reset(seed=0)
    return env


def test_burning_fuel_costs_reward():
    env = _env()
    _park_fuels(env.world)
    env.step((False, False, True, False, False))  # gas: 5/s
    burned = env.world.component(env.car, Tank).burned
    assert burned == pytest.approx(5 / STEPS)
    assert env.round_terms["fuel_burned"] == pytest.approx(-5 * burned)


def test_running_dry_is_out_of_fuel_not_a_wreck():
    env = _env()
    env.world.component(env.car, Tank).level = 0.0
    for _ in range(STEPS):
        *_, terminated, _, info = env.step((False,) * 5)
        if terminated:
            break
    assert info["eliminated"] == "out_of_fuel"
    assert env.round_terms["out_of_fuel"] == -3000
    assert env.round_terms["wrecked"] == 0


def test_progress_is_toward_the_nearest_fuel_by_route():
    from src.sim import route

    env = _env("skill_detour")  # a fuel behind a wall: the route is long
    sense = route.sense(env.world, env.car)
    goal = sense.goal
    assert env._goal() == goal  # the first fuel it senses
