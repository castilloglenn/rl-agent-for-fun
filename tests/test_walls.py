"""Roadmap step 7a: walls inside the field. The same physics as the
border: the car stops at the surface, slides along it, loses health by
impact speed, and rays stop there.
"""

import math

import pytest

from src.config import get_maze_car_config
from src.sim.components import (
    ActionInput,
    Eliminated,
    Health,
    Motion,
    Sensors,
    Transform,
)
from src.sim.factories import create_car, create_world
from src.sim.geometry import car_corners
from src.sim.resources import Walls
from src.sim.spawning import CANDIDATES_PER_SLOT, SpawnSchedule
from src.sim.stage import CheckpointRules, Stage, StageError, load_stage
from src.sim.walls import Box, overlaps, ray_to_walls, wall_contact
from src.utils.types import Colors

SIZE = [855, 480]


def _stage(walls, spawn=(100, 240), checkpoints=None):
    return Stage.from_dict(
        {
            "format": 1,
            "name": "test",
            "size": SIZE,
            "walls": walls,
            "spawns": [{"x": spawn[0], "y": spawn[1], "angle": 0}],
            "checkpoints": checkpoints or {"mode": "random"},
        }
    )


def _car(walls, x, y, angle=0.0, speed=0.0):
    config = get_maze_car_config()
    world = create_world(config, stage=_stage(walls))
    car = create_car(
        world,
        x,
        y,
        config.car.width,
        config.car.height,
        Colors.SKY_BLUE,
        angle=angle,
    )
    world.component(car, Motion).speed = speed
    return world, car


def _drive(world, car, action, steps):
    world.add_component(car, action)
    for _ in range(steps):
        world.step()


def _corners(world, car):
    t = world.component(car, Transform)
    return car_corners(t.x, t.y, t.angle, 24, 16)


# The geometry


def test_a_corner_meets_a_face():
    wall = Box(100, 0, 120, 200)
    corners = car_corners(80, 100, 0, 24, 16)  # front at x = 92
    contact = wall_contact(corners, 10, 0, (wall,))
    assert contact.fraction == pytest.approx(0.8)
    assert contact.normal == (-1.0, 0.0)


def test_touching_a_wall_isnt_being_inside_it():
    wall = Box(100, 0, 120, 200)
    corners = car_corners(88, 100, 0, 24, 16)  # front exactly on it
    assert wall_contact(corners, 0, 5, (wall,)) is None  # along it
    assert wall_contact(corners, -5, 0, (wall,)) is None  # away
    assert wall_contact(corners, 3, 0, (wall,)).fraction == 0  # into it


def test_a_wall_corner_meets_the_car_side():
    # A thin bar at the car's mid height: no car corner reaches it, the
    # bar's corners meet the car's front edge.
    bar = Box(100, 98, 140, 102)
    corners = car_corners(80, 100, 0, 24, 16)  # y from 92 to 108
    contact = wall_contact(corners, 10, 0, (bar,))
    assert contact.fraction == pytest.approx(0.8)
    assert contact.normal == pytest.approx((-1.0, 0.0))


def test_overlap_and_rays():
    wall = Box(210, 300, 260, 400)
    assert not overlaps(car_corners(200, 292, 0, 24, 16), wall)  # touching
    assert overlaps(car_corners(215, 295, 0, 24, 16), wall)
    assert ray_to_walls(50, 350, 1, 0, (wall,)) == pytest.approx(160)
    assert ray_to_walls(50, 350, -1, 0, (wall,)) == math.inf


# The car against walls


def test_head_on_into_a_wall_stops_at_its_surface():
    world, car = _car([[300, 200, 40, 80]], 200, 240, speed=2.0)  # 240/s
    _drive(world, car, ActionInput(gas=True), 120)
    assert max(x for x, _ in _corners(world, car)) == pytest.approx(300)
    health = world.component(car, Health)
    assert health.contacts >= 1
    assert world.try_component(car, Eliminated)  # 240 px/s: lethal


def test_a_slow_touch_is_a_bump():
    # 0.5 px per step is 60 px/s: the safe speed.
    world, car = _car([[300, 200, 40, 80]], 286, 240, speed=0.5)
    _drive(world, car, ActionInput(), 30)  # coasting into it
    assert max(x for x, _ in _corners(world, car)) == pytest.approx(300)
    health = world.component(car, Health)
    assert health.contacts == 1 and health.current == health.maximum


def test_an_angled_hit_slides_along_the_wall():
    wall = [[300, 0, 40, 480]]
    world, car = _car(wall, 260, 240, angle=30, speed=1.0)
    start_y = world.component(car, Transform).y
    _drive(world, car, ActionInput(gas=True), 60)
    transform = world.component(car, Transform)
    assert max(x for x, _ in _corners(world, car)) <= 300 + 1e-6
    assert transform.y < start_y - 10  # it slid up along the wall
    assert not world.try_component(car, Eliminated)


def test_turning_into_a_wall_is_blocked():
    # The car's nose touches a wall ahead; turning would swing a corner
    # into it.
    world, car = _car([[300, 0, 40, 480]], 288, 240, speed=0.5)
    world.add_component(car, ActionInput(turn_left=True, brake=True))
    world.step()
    assert world.component(car, Transform).angle == 0
    assert not any(
        overlaps(_corners(world, car), box)
        for box in world.resource(Walls).boxes
    )


def test_rays_stop_at_walls():
    world, car = _car([[400, 0, 40, 480]], 200, 240)
    world.step()
    front = next(
        r for r in world.component(car, Sensors).rays if r.name == "front"
    )
    assert front.distance == pytest.approx(400 - 212)  # from the nose


def test_a_car_never_ends_inside_a_wall():
    walls = [[255, 130, 60, 60], [540, 290, 60, 60]]
    world, car = _car(walls, 150, 240, angle=10, speed=1.5)
    boxes = world.resource(Walls).boxes
    for step in range(600):
        left = (step // 40) % 2 == 0
        action = ActionInput(gas=True, turn_left=left, turn_right=not left)
        _drive(world, car, action, 1)
        corners = _corners(world, car)
        assert not any(overlaps(corners, box) for box in boxes), step
        if world.try_component(car, Eliminated):
            break


# Checkpoints and stages


def test_checkpoints_keep_clear_of_walls():
    wall = Box(0, 0, 855, 300)  # only the bottom is free
    rules = CheckpointRules(border_margin=40)
    schedule = SpawnSchedule(
        "checkpoints", 7, rules, 855, 480, walls=(wall,)
    )
    for _ in range(20):
        x, y = schedule.next_spot([])
        assert wall.distance(x, y) >= 40


def test_no_walls_draw_exactly_the_same_spots():
    rules = CheckpointRules()
    plain = SpawnSchedule("checkpoints", 3, rules, 855, 480)
    assert len(plain.candidates(0)) == CANDIDATES_PER_SLOT
    walled = SpawnSchedule(
        "checkpoints", 3, rules, 855, 480, walls=(Box(0, 0, 1, 1),)
    )
    far = [p for p in plain.candidates(0) if p[0] > 41 or p[1] > 41]
    assert walled.candidates(0) == far  # the same draws, filtered


@pytest.mark.parametrize(
    "walls, message",
    [
        ([[800, 0, 100, 10]], "outside the stage"),
        ([[10, 10, 0, 10]], "size must be positive"),
        ([[90, 230, 20, 20]], "next to a wall"),
        ([[1, 2, 3]], "x, y, width, height"),
    ],
)
def test_stage_validation(walls, message):
    with pytest.raises(StageError, match=message):
        _stage(walls)


def test_a_scripted_checkpoint_cant_touch_a_wall():
    with pytest.raises(StageError, match="touches a wall"):
        _stage(
            [[400, 0, 20, 480]],
            checkpoints={"mode": "scripted", "points": [[410, 100]]},
        )


def test_the_sample_stages_load_and_round_trip():
    for name in ("pillars", "s_curve"):
        stage = load_stage(name)
        assert stage.walls
        assert Stage.from_dict(stage.to_dict()) == stage  # replays embed it


def test_a_replay_on_a_walled_stage_verifies(tmp_path):
    from src.drivers.random_driver import RandomDriver
    from src.experiments.runner import run_experiment
    from src.replay.format import read_replay
    from src.replay.replayer import Replayer
    from src.sim.rules import load_rules

    config = get_maze_car_config()
    config.stage = "pillars"
    summary = run_experiment(
        "walls",
        RandomDriver(),
        config,
        episodes=3,
        rules=load_rules("standard").with_round_seconds(3),
        runs_dir=tmp_path,
    )
    for path in (summary.folder / "replays").glob("*.jsonl.gz"):
        replay = read_replay(path)
        assert replay.header["stage"]["walls"]
        assert Replayer(replay).run().ok
