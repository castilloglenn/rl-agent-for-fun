"""Roadmap step 7c1: the map editor. Every stage here is in tmp_path;
the repo's stages are only read.
"""

import json
import os
import shutil

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

from src.editor.model import (  # noqa: E402
    EditorModel,
    dump_stage,
    new_stage,
    snap,
)
from src.sim.stage import STAGES_DIR, Stage, StageError  # noqa: E402


@pytest.fixture
def root(tmp_path):
    shutil.copytree(STAGES_DIR, tmp_path / "stages")
    return tmp_path


# The file and the grid


def test_every_stage_file_round_trips_exactly():
    for path in sorted(STAGES_DIR.glob("*.json")):
        text = path.read_text()
        assert dump_stage(json.loads(text)) == text, path.name


def test_snapping():
    assert snap(574) == 570 and snap(575) == 580 and snap(3) == 0
    assert snap(574.26, on=False) == 574.3


def test_a_new_stage_is_the_box_and_valid(root):
    model = EditorModel("fresh", root=root)
    assert model.is_new and model.dirty
    assert model.stage == new_stage("fresh")
    assert model.problem() is None
    model.save()
    saved = json.loads((root / "user/stages/fresh.json").read_text())
    assert Stage.from_dict(saved).name == "fresh"
    assert not model.dirty


# Walls


def test_draw_move_resize_and_delete_a_wall(root):
    model = EditorModel("box", root=root)
    assert model.add_wall(504, 96, 411, 213)  # any corner order, snapped
    assert model.walls == [[410, 100, 90, 110]]
    assert not model.add_wall(100, 100, 102, 300)  # snaps to no width
    model.move_wall(0, 803, 12)  # stays inside the stage
    assert model.walls[0] == [765, 10, 90, 110]
    model.resize_wall(0, 2, 900, 500)  # the bottom right corner, clamped
    assert model.walls[0] == [765, 10, 90, 470]
    model.resize_wall(0, 0, 700, 40)  # the top left corner
    assert model.walls[0] == [700, 40, 155, 440]
    assert model.selection == ("wall", 0)
    assert model.delete() and model.walls == []


def test_picking_prefers_small_things(root):
    model = EditorModel("box", root=root)
    model.add_wall(100, 100, 400, 400)
    model.add_checkpoint(200, 200)
    model.spawn.update(x=300, y=300)
    assert model.pick(201, 199) == ("checkpoint", 0)
    assert model.pick(302, 301) == ("spawn", 0)
    assert model.pick(150, 350) == ("wall", 0)
    assert model.pick(600, 50) is None
    model.selection = ("wall", 0)
    assert model.corner_at(399, 101, 6) == 1  # the top right corner


# The spawn and checkpoints


def test_the_spawn_moves_and_turns(root):
    model = EditorModel("box", root=root)
    model.move_spawn(123, 456)
    assert (model.spawn["x"], model.spawn["y"]) == (120, 460)
    model.turn_spawn(-15)
    assert model.spawn["angle"] == 345


def test_checkpoints_in_order_and_back_to_random(root):
    model = EditorModel("box", root=root)
    model.add_checkpoint(100, 100)
    model.add_checkpoint(700, 400)
    assert model.checkpoints["mode"] == "scripted"
    assert model.points == [[100, 100], [700, 400]]
    model.move_checkpoint(1, 648, 352)
    assert model.points[1] == [650, 350]
    model.toggle_checkpoint_mode()
    assert model.checkpoints["mode"] == "random"
    model.toggle_checkpoint_mode()  # the points come back
    assert model.points == [[100, 100], [650, 350]]


# Undo, validation, saving


def test_undo_and_redo(root):
    model = EditorModel("box", root=root)
    model.add_wall(100, 100, 200, 200)
    model.commit()
    model.move_wall(0, 300, 300)
    model.commit()
    assert model.undo() and model.walls == [[100, 100, 100, 100]]
    assert model.undo() and model.walls == []
    assert not model.undo()
    assert model.redo() and model.redo()
    assert model.walls == [[300, 300, 100, 100]]
    assert not model.redo()


def test_a_problem_blocks_saving(root):
    model = EditorModel("box", root=root)
    model.add_wall(200, 220, 230, 260)  # onto the spawn (213.75, 240)
    assert "next to a wall" in model.problem()
    with pytest.raises(StageError):
        model.save()
    assert json.loads((root / "stages/box.json").read_text())["walls"] == []


def _yours(root, name="my_pillars", like="pillars"):
    """A map of yours: a copy of a built-in in user/stages."""
    data = json.loads((root / "stages" / f"{like}.json").read_text())
    folder = root / "user" / "stages"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.json").write_text(json.dumps({**data, "name": name}))
    return name


def test_save_and_reopen(root):
    name = _yours(root)
    model = EditorModel(name, root=root)
    model.add_wall(700, 20, 760, 60)
    model.commit()
    model.save()
    again = EditorModel(name, root=root)
    assert again.walls[-1] == [700, 20, 60, 40] and not again.dirty
    assert Stage.from_dict(again.stage)


def test_a_built_in_map_only_saves_as_a_new_name(root):
    model = EditorModel("pillars", root=root)
    assert model.built_in
    model.add_wall(700, 20, 760, 60)
    model.commit()
    before = (root / "stages" / "pillars.json").read_text()
    with pytest.raises(StageError, match="built-in"):
        model.save()
    with pytest.raises(StageError, match="already exists"):
        model.save_as("box")
    with pytest.raises(StageError, match="letters, digits"):
        model.save_as("my map")
    model.save_as("my_pillars")
    assert (root / "stages" / "pillars.json").read_text() == before
    saved = json.loads((root / "user/stages/my_pillars.json").read_text())
    assert saved["name"] == "my_pillars" and saved["walls"][-1][0] == 700
    assert not model.built_in and not model.dirty
    assert not model.undo()  # undo starts over on the new map
    model.add_wall(20, 400, 60, 440)
    model.commit()
    model.save()  # now it's yours: saves in place
    assert EditorModel("my_pillars", root=root).walls[-1][0] == 20


# The window


def _window(root, name="box"):
    from src.editor.window import EditorWindow

    return EditorWindow(EditorModel(name, root=root))


def _mouse(window, kind, world, button=1):
    pos = window.camera.to_screen(*world)
    event = pygame.event.Event(kind, button=button, pos=pos, rel=(0, 0))
    window.handle(event)


def test_drawing_a_wall_with_the_mouse(root):
    window = _window(root)
    window.key(pygame.K_w)
    _mouse(window, pygame.MOUSEBUTTONDOWN, (400, 100))
    _mouse(window, pygame.MOUSEMOTION, (500, 200))
    window.draw()  # the preview
    _mouse(window, pygame.MOUSEBUTTONUP, (500, 200))
    assert window.model.walls == [[400, 100, 100, 100]]
    window.key(pygame.K_z, pygame.KMOD_CTRL)
    assert window.model.walls == []


def test_dragging_a_wall_moves_it(root):
    window = _window(root, "pillars")
    first = list(window.model.walls[0])  # [255, 130, 60, 60]
    _mouse(window, pygame.MOUSEBUTTONDOWN, (first[0] + 10, first[1] + 10))
    assert window.model.selection == ("wall", 0)
    _mouse(window, pygame.MOUSEMOTION, (first[0] + 50, first[1] + 30))
    _mouse(window, pygame.MOUSEBUTTONUP, (first[0] + 50, first[1] + 30))
    # 255 + 40 lands on the grid at 300 (a moved wall snaps to it).
    assert window.model.walls[0][:2] == [300, first[1] + 20]


def test_saving_and_quitting(root):
    window = _window(root)
    window.key(pygame.K_c)
    _mouse(window, pygame.MOUSEBUTTONDOWN, (600, 300))
    _mouse(window, pygame.MOUSEBUTTONUP, (600, 300))
    window.key(pygame.K_ESCAPE)  # unsaved: asks
    assert window.confirm_quit and window.running
    window.draw()
    window.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    assert not window.confirm_quit
    window.key(pygame.K_s, pygame.KMOD_META)  # Cmd+S on a Mac
    assert window.save_as == "my_box"  # box is built-in: SAVE AS
    window.draw()
    _type(window, pygame.K_BACKSPACE, "")
    for char in "2":
        _type(window, ord(char), char)
    _type(window, pygame.K_SPACE, " ")  # not a name character: ignored
    assert window.save_as == "my_bo2"
    _type(window, pygame.K_RETURN, "\r")
    assert window.save_as is None and window.message[0].startswith("Saved")
    assert (root / "user" / "stages" / "my_bo2.json").exists()
    window.key(pygame.K_ESCAPE)  # saved: quits at once
    assert not window.running


def _type(window, key, char):
    window.handle(pygame.event.Event(pygame.KEYDOWN, key=key, unicode=char))


def test_esc_closes_save_as_without_saving(root):
    window = _window(root)
    window.key(pygame.K_s, pygame.KMOD_META)
    _type(window, pygame.K_ESCAPE, "")
    assert window.save_as is None and window.running
    assert not (root / "user" / "stages" / "my_box.json").exists()


def test_a_big_stage_opens_whole_and_f_goes_1_to_1(root):
    from src.render.camera import FIT, FOLLOW

    window = _window(root, "arena")
    assert window.camera.mode == FIT and window.camera.scale < 1
    window.key(pygame.K_f)
    window.key(pygame.K_RIGHT)
    window.draw()
    assert window.camera.mode == FOLLOW and window.camera.scale == 1


# The stage's size (7c2)


def test_resizing_the_stage(root):
    model = EditorModel("box", root=root)
    assert model.stage_edge_at(855, 480, 6) == "corner"
    assert model.stage_edge_at(853, 200, 6) == "right"
    assert model.stage_edge_at(400, 482, 6) == "bottom"
    assert model.stage_edge_at(400, 200, 6) is None
    model.resize_stage("corner", 1203, 597)
    assert model.size == (1200, 600)
    model.resize_stage("right", 50, 0)  # the spawn (213.75) stops it
    assert model.size == (229.75, 600)
    model.move_spawn(60, 60)
    model.resize_stage("corner", 10, 10)  # never under 200 x 200
    assert model.size == (200, 200)
    model.commit()
    assert model.undo() and model.size == (855, 480)


def test_walls_and_checkpoints_limit_shrinking(root):
    model = EditorModel("s_curve", root=root)
    model.resize_stage("corner", 300, 300)
    # The last checkpoint (720, 80) + its radius, and a wall to y 480.
    assert model.size == (735, 480)


def test_dragging_the_stage_corner_refits_the_camera(root):
    window = _window(root)
    _mouse(window, pygame.MOUSEBUTTONDOWN, (855, 480))
    assert window.drag == ("stage", "corner")
    _mouse(window, pygame.MOUSEMOTION, (1200, 900))
    _mouse(window, pygame.MOUSEBUTTONUP, (1200, 900))
    assert window.model.size == (1200, 900)
    assert window.camera.zoomable and window.camera.scale < 1
    window.draw()


# Test drive (7c2)


def test_an_invalid_map_cant_be_test_driven(root):
    window = _window(root)
    window.model.add_wall(200, 220, 230, 260)  # onto the spawn
    played = []
    window.play = played.append
    window.key(pygame.K_t)
    assert played == [] and window.message[0].startswith("Can't test")


def test_test_drive_plays_the_map_and_comes_back(root):
    window = _window(root, "s_curve")
    window.model.add_wall(700, 300, 760, 340)  # unsaved
    before = json.dumps(window.model.stage)
    seen = {}

    def play(demo):
        seen["demo"] = demo
        demo.frame(0.1)
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_t))
        demo.frame(0.1)  # the window reads the key
        demo.frame(0.1)  # the game sees T: back to the editor
        seen["running"] = demo.env.running

    window.play = play
    window.key(pygame.K_t)
    demo = seen["demo"]
    assert demo.test_drive == "unsaved" and demo.recorder is None
    assert list(map(list, demo.env.stage.walls))[-1] == [700, 300, 60, 40]
    assert demo.mode().label == "TEST DRIVE · unsaved"
    assert seen["running"] is False
    assert json.dumps(window.model.stage) == before  # the editor as it was
    assert window.screen.get_size() == window.layout.window.size


def test_shift_t_watches_the_heuristic(root):
    window = _window(root)
    seen = []
    window.play = seen.append
    window.key(pygame.K_t, pygame.KMOD_SHIFT)
    assert seen[0].driver.label == "heuristic (baseline)"
