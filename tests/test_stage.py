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
