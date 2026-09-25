"""Round timer and crash = game over (roadmap step 3f)."""

from src.config import get_maze_car_config
from src.envs.maze_car.env import MazeCarEnv
from src.sim.components import ActionInput, Eliminated, Transform
from src.sim.factories import create_start_car, create_world
from src.sim.resources import EventLog, RoundState, SimClock
from src.sim.rules import load_rules

GAS = ActionInput(gas=True)


def _config():
    config = get_maze_car_config()
    config.show_gui = False
    return config


def _short_rules(seconds: float = 1):
    return load_rules("standard").with_round_seconds(seconds)


def test_round_is_60_seconds_of_steps():
    world = create_world(get_maze_car_config())
    assert world.resource(RoundState).steps_left == 60 * 120


def test_time_up_ends_the_round_and_freezes_the_world():
    world = create_world(_config(), rules=_short_rules(1))
    car = create_start_car(world)
    world.add_component(car, ActionInput(gas=True, turn_left=True))
    for _ in range(120):
        world.step()

    state = world.resource(RoundState)
    assert state.over and state.reason == "time" and state.steps_left == 0
    assert world.resource(EventLog).events[-1].text == "Round over: time up"

    transform = world.component(car, Transform)
    frozen = (transform.x, transform.y, transform.angle)
    step = world.resource(SimClock).step
    for _ in range(50):
        world.step()
    assert (transform.x, transform.y, transform.angle) == frozen
    assert world.resource(SimClock).step == step


def test_crash_eliminates_the_car_and_ends_the_round():
    world = create_world(get_maze_car_config())
    car = create_start_car(world, label="Tester")
    world.add_component(car, GAS)
    for _ in range(600):
        world.step()

    eliminated = world.component(car, Eliminated)
    assert eliminated.reason == "wall"
    state = world.resource(RoundState)
    assert state.over and state.reason == "all_out"

    texts = [event.text for event in world.resource(EventLog).events]
    assert texts == [
        "Tester crashed into the wall",
        "Round over: every car is out",
    ]
    assert world.resource(EventLog).events[0].step == eliminated.step


def test_env_reports_game_over_and_stops_stepping():
    env = MazeCarEnv(_config(), rules=_short_rules(1))
    results = [env.game_step((False, False, True, False, False))]
    while not results[-1][1]:
        results.append(env.game_step((False, False, True, False, False)))
    assert len(results) == 120
    assert env.is_game_over

    step = env.world.resource(SimClock).step
    assert env.game_step((False, False, True, False, False))[1] is True
    assert env.world.resource(SimClock).step == step


def test_reset_starts_a_fresh_round():
    env = MazeCarEnv(_config(), rules=_short_rules(1))
    for _ in range(200):
        env.game_step((False, False, True, False, False))
    assert env.is_game_over

    env.reset()
    assert not env.is_game_over
    assert env.world.resource(RoundState).steps_left == 120
    assert env.world.resource(EventLog).events == []
