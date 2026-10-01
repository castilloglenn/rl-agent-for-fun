import json

import pytest

from src.config import get_maze_car_config
from src.sim.components import Transform
from src.sim.factories import create_game
from src.sim.resources import Field
from src.sim.stage import STAGES_DIR, Stage, StageError, load_stage


def _box_data() -> dict:
    return json.loads((STAGES_DIR / "box.json").read_text())


def test_box_stage():
    stage = load_stage("box")
    assert (stage.name, stage.width, stage.height) == ("box", 855, 480)
    assert stage.spawns[0].x == 213.75 and stage.spawns[0].y == 240
    assert stage.checkpoints.mode == "random"
    assert stage.walls == ()


def test_round_trip_matches_the_file():
    stage = load_stage("box")
    assert stage.to_dict() == _box_data()
    assert Stage.from_dict(stage.to_dict()) == stage


def test_load_by_path():
    assert load_stage(str(STAGES_DIR / "box.json")) == load_stage("box")


@pytest.mark.parametrize(
    "change, message",
    [
        ({"format": 2}, "unsupported stage format"),
        ({"size": [0, 480]}, "size must be positive"),
        ({"spawns": []}, "at least one spawn"),
        ({"spawns": [{"x": 9999, "y": 10}]}, "outside the stage"),
        ({"checkpoints": {"mode": "zigzag"}}, "unknown checkpoint mode"),
        ({"checkpoints": {"start": "middle"}}, "unknown checkpoint start"),
        ({"checkpoints": {"mode": "scripted"}}, "need points"),
        ({"checkpoints": {"border_margin": 300}}, "leaves no room"),
    ],
)
def test_invalid_stages_are_rejected(change, message):
    data = {**_box_data(), **change}
    with pytest.raises(StageError, match=message):
        Stage.from_dict(data)


def test_world_is_built_from_the_stage():
    world, car = create_game(get_maze_car_config())
    field = world.resource(Field).rect
    assert (field.x, field.y, field.width, field.height) == (0, 0, 855, 480)
    transform = world.component(car, Transform)
    assert (transform.x, transform.y, transform.angle) == (213.75, 240, 0)
    assert world.resource(Stage) == load_stage("box")


def test_a_custom_stage_changes_the_world():
    data = {
        **_box_data(),
        "name": "wide",
        "size": [1200, 400],
        "spawns": [{"x": 100, "y": 200, "angle": 90}],
    }
    world, car = create_game(get_maze_car_config(), stage=Stage.from_dict(data))
    assert world.resource(Field).rect.size == (1200, 400)
    assert world.component(car, Transform).angle == 90


def test_a_seeded_start_round_trips_and_the_default_stays_out():
    data = json.loads((STAGES_DIR / "skill_gaps.json").read_text())
    assert "start" not in load_stage("skill_gaps").to_dict()["checkpoints"]
    data["checkpoints"]["start"] = "seeded"
    stage = Stage.from_dict(data)
    assert stage.checkpoints.start == "seeded"
    assert stage.to_dict()["checkpoints"]["start"] == "seeded"
    assert Stage.from_dict(stage.to_dict()) == stage


def test_every_scripted_checkpoint_can_be_reached():
    """Each built-in scripted stage (the courses of 7d5b too): every
    checkpoint has a drivable path from the spawn and from the one
    before it (a seeded start can begin anywhere in the loop).
    """
    import math

    from src.sim.paths import PathField

    for path in sorted(STAGES_DIR.glob("*.json")):
        stage = load_stage(path.stem)
        if stage.checkpoints.mode != "scripted":
            continue
        rect = (0, 0, stage.width, stage.height)
        boxes = [(x, y, x + w, y + h) for x, y, w, h in stage.walls]
        points = stage.checkpoints.points
        spawn = (stage.spawns[0].x, stage.spawns[0].y)
        for i, goal in enumerate(points):
            field = PathField(rect, boxes, goal)
            for start in (spawn, points[i - 1]):
                assert not math.isinf(field.distance(*start)), (
                    path.stem,
                    goal,
                )


def test_the_courses_start_anywhere():
    for name in ("course_small", "course_large"):
        assert load_stage(name).checkpoints.start == "seeded"


def test_the_easy_course_keeps_each_next_checkpoint_in_sight():
    """7f2: on course_small_easy every leg is a straight line with room
    for the car (at least 24 px from any wall), and the heuristic, which
    only steers at the checkpoint, drives most of a loop in 60 s.
    """
    from src.config import get_maze_car_config
    from src.drivers.episode import run_episode
    from src.drivers.registry import make_driver
    from src.envs.maze_car.env import MazeCarEnv
    from src.sim.walls import Box

    stage = load_stage("course_small_easy")
    boxes = [Box.from_list(wall) for wall in stage.walls]
    points = stage.checkpoints.points
    for i, (bx, by) in enumerate(points):
        ax, ay = points[i - 1]
        n = int(max(abs(bx - ax), abs(by - ay)) // 2) + 1
        for k in range(n + 1):
            x, y = ax + (bx - ax) * k / n, ay + (by - ay) * k / n
            assert min(b.distance(x, y) for b in boxes) >= 24, (i, x, y)
    config = get_maze_car_config()
    config.show_gui = False
    env = MazeCarEnv(config, stage=stage)
    result = run_episode(env, make_driver("heuristic"), 50_000)
    assert result.checkpoints >= 20  # most of the loop's 28 in 60 s
