"""A sense of direction and of being stuck (7f7): a remembered waypoint
along the drivable route, its distance, and a stuck timer.
"""

import math

import pytest

from src.config import get_maze_car_config
from src.envs.maze_car.env import MazeCarEnv
from src.sim import route
from src.sim.components import Transform
from src.sim.observation import OBSERVATION_NAMES
from src.sim.resources import Walls
from src.sim.stage import load_stage

NONE = (False,) * 5


def _env(stage="skill_detour"):
    config = get_maze_car_config()
    config.show_gui = False
    env = MazeCarEnv(config, stage=load_stage(stage))
    env.reset(seed=0)
    return env


def _value(env, name):
    return float(env.last_observation[OBSERVATION_NAMES.index(name)])


def test_in_plain_sight_the_waypoint_is_the_checkpoint():
    env = _env("box")
    sense = route.sense(env.world, env.car)
    assert sense.waypoint == sense.goal
    assert _value(env, "route_sin") == pytest.approx(
        _value(env, "checkpoint_sin"), abs=1e-6
    )


def test_a_wall_in_between_points_the_way_around():
    """skill_detour: the checkpoint sits inside a U whose back wall faces
    the car. The compass points through it; the route goes around.
    """
    env = _env()
    sense = route.sense(env.world, env.car)
    car = env.world.component(env.car, Transform)
    assert sense.goal == (540, 240)
    assert sense.waypoint != sense.goal
    boxes = env.world.resource(Walls).boxes
    assert route._clear((car.x, car.y), sense.waypoint, boxes)  # in sight
    # Around an arm of the U (above 120 or below 360), not through it.
    assert sense.waypoint[1] < 120 or sense.waypoint[1] > 360
    straight = math.dist((car.x, car.y), sense.goal)
    assert sense.distance > straight + 100  # the route is longer
    assert abs(_value(env, "route_sin")) > 0.3  # it points to a side
    assert _value(env, "checkpoint_cos") > 0.99  # the compass: dead ahead


def test_the_stuck_timer_counts_and_resets_with_progress():
    env = _env("box")
    for _ in range(3 * 120):  # 3 s without moving
        env.step(NONE)
    stuck = 3 / route.STUCK_CAP
    assert _value(env, "stuck") == pytest.approx(stuck, abs=0.02)
    from src.drivers.registry import make_driver

    driver = make_driver("heuristic")  # then drive at the checkpoint
    for _ in range(120):
        env.step(driver.act(env.last_observation))
    assert _value(env, "stuck") < 0.05  # it got closer: reset


def test_the_waypoint_is_held_then_refreshed():
    env = _env()
    sense = route.sense(env.world, env.car)
    first = sense.refreshed
    env.step(NONE)
    assert route.sense(env.world, env.car).refreshed == first  # held
    for _ in range(int(route.REFRESH_SECONDS * 120)):
        env.step(NONE)
    assert route.sense(env.world, env.car).refreshed > first  # 2 s on


def test_the_reward_and_the_sense_share_one_route_field():
    """The exact field (the reward and the route distance) is shared;
    the waypoint uses a padded one (30 px from walls) as well.
    """
    env = _env()
    env.step((False, False, True, False, False))
    fields = route.route_fields(env.world).fields
    kept = {(goal, clearance) for _, _, goal, clearance in fields}
    assert kept == {((540, 240), None), ((540, 240), route.PADDING)}


def test_an_env_keeps_its_route_fields_across_games():
    """A course meets the same checkpoints every round: built once."""
    env = _env()
    first = route.route_fields(env.world).field(env.world, (540, 240))
    env.reset(seed=1)
    again = route.route_fields(env.world).field(env.world, (540, 240))
    assert again is first
    env.stage = load_stage("box")  # another map: its own fields
    env.reset(seed=1)
    other = route.route_fields(env.world).field(env.world, (540, 240))
    assert other is not first


def test_the_driving_route_keeps_its_distance_from_walls():
    env = _env("route_spiral")
    boxes = env.world.resource(Walls).boxes
    points = route.route_points(env.world, (500, 75), (500, 500))
    inner = points[3:-3]  # away from the start and the goal
    near = min(min(b.distance(x, y) for b in boxes) for x, y in inner)
    assert near >= route.PADDING - 10  # the grid's cells: within 10 px


def test_a_gap_too_narrow_for_the_padding_uses_the_exact_route():
    """skill_gaps: 40 px gaps. Padding would close them: the exact route."""
    env = _env("skill_gaps")
    sense = route.sense(env.world, env.car)
    assert sense.waypoint is not None
    car = env.world.component(env.car, Transform)
    points = route.route_points(env.world, (car.x, car.y), sense.goal)
    assert math.dist(points[-2], sense.goal) <= route.STEP + 1


# Seeing it (7f8): the waypoint, the remembered route,
# and an agent's MIND.


def test_the_route_runs_from_a_point_to_the_checkpoint():
    env = _env()
    sense = route.sense(env.world, env.car)
    points = route.route_points(env.world, sense.waypoint, sense.goal)
    assert points[0] == sense.waypoint and points[-1] == sense.goal
    field = route.route_fields(env.world).field(env.world, sense.goal)
    left = [field.distance(*p) for p in points[:-1]]
    assert left == sorted(left, reverse=True)  # always closer


def test_the_window_draws_the_remembered_route():
    import os

    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    from src.envs.maze_car.demo import MazeCarDemo

    demo = MazeCarDemo(
        get_maze_car_config(),
        driver="heuristic",
        autorun=False,
        record=False,
        stage=load_stage("skill_detour"),
    )
    renderer = demo.env.renderer
    assert renderer.settings["route"]  # on by default
    for _ in range(60):
        demo.frame(1 / 60)
    sense = route.sense(demo.env.world, demo.env.car)
    assert renderer._route_points[0] == sense.waypoint
    assert renderer._route_points[-1] == sense.goal


def test_an_agents_mind_comes_from_its_latest_decision():
    from src.render.panels import MindInfo, mind_of

    class Agent:
        probabilities = [1 / 12] * 12
        value = 0.5
        observation = [0.0] * len(OBSERVATION_NAMES)  # speed 0: stopped

    mind = mind_of(Agent())
    assert isinstance(mind, MindInfo)
    assert mind.stopped and mind.value == 0.5
    assert mind_of(object()) is None  # the heuristic, the keyboard


def test_a_training_replay_has_no_mind():
    from src.replay.viewer import _mind_driver

    header = {"slots": {"1": {"type": "agent", "id": "a", "checkpoint": None,
                              "training": {"run": "r", "decisions": 1}}}}
    assert _mind_driver(header) is None
    assert _mind_driver({"slots": {"1": {"type": "human"}}}) is None


def test_the_route_never_cuts_through_a_wall():
    """Next to a thin wall, the far side reads a shorter distance: the
    walk used to step through the spiral's corner. Now no step of it
    comes within WALK_CLEAR of a wall, and it still reaches the goal.
    """
    env = _env("route_spiral")
    boxes = env.world.resource(Walls).boxes
    for start in ((500, 75), (800, 75), (900, 300), (75, 600)):
        points = route.route_points(env.world, start, (500, 500))
        assert math.dist(points[-2], (500, 500)) <= route.STEP + 1
        for x, y in points[1:-1]:
            near = min(box.distance(x, y) for box in boxes)
            assert near >= route.WALK_CLEAR - 1e-6, (start, x, y)
        sense_point = route.waypoint(
            route.route_fields(env.world).field(env.world, (500, 500)),
            start, (500, 500), env.world,
        )
        assert min(b.distance(*sense_point) for b in boxes) >= 5


def test_a_passed_waypoint_is_dropped_at_once():
    """7f15: swept past the waypoint wider than REACH, the car would turn
    back for it until the 2 s refresh. Now it takes the next one.
    """
    env = _env("route_spiral")
    sense = route.sense(env.world, env.car)
    first, goal = sense.waypoint, sense.goal
    path = route.route_fields(env.world).field(env.world, goal)
    # A spot further along the route than the waypoint, out of its reach.
    ahead = next(
        p for p in route.route_points(env.world, first, goal)
        if path.distance(*p) < path.distance(*first) - 80
        and math.dist(p, first) > route.REACH + 20
    )
    car = env.world.component(env.car, Transform)
    car.x, car.y = ahead
    env.step(NONE)  # within the 2 s: only the overshoot can refresh it
    sense = route.sense(env.world, env.car)
    assert sense.waypoint != first
    assert path.distance(*sense.waypoint) < path.distance(*ahead)


def test_a_waypoint_chosen_close_is_held():
    """8a fix: a waypoint chosen inside REACH counted as reached at once,
    and was chosen again almost every step (course_small: 2,811 times in
    one round). Now it's reached at half its distance when chosen.
    """
    env = _env("course_small")
    world = env.world
    boxes = world.resource(Walls).boxes
    goal = route.sense(world, env.car).goal
    fields = route.route_fields(world)
    spot = next(  # a tight spot: its waypoint is chosen inside REACH
        (x, y)
        for x in range(20, 860, 10)
        for y in range(20, 480, 10)
        if min(b.distance(x, y) for b in boxes) > 15
        and 5 < math.dist(
            (x, y),
            route.waypoint(fields.driving(world, goal, (x, y)), (x, y),
                           goal, world),
        ) < route.REACH / 2
    )
    car = world.component(env.car, Transform)
    car.x, car.y = spot
    world.remove_component(env.car, route.RouteSense)  # sensed afresh here
    env.step(NONE)
    sense = route.sense(world, env.car)
    assert sense.chosen < route.REACH  # chosen close
    first = sense.refreshed
    for _ in range(10):
        env.step(NONE)  # sitting still: not reached, not passed
    assert route.sense(world, env.car).refreshed == first
