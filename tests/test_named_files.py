"""Built-in named files and yours (roadmap 7d1a, decision 039). Every test
works in tmp_path; the repo's files are only read.
"""

import json
import os
import shutil

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pytest  # noqa: E402

from src.control import files, maps_data  # noqa: E402
from src.control.trash import Trash, TrashError  # noqa: E402
from src.editor.model import EditorModel  # noqa: E402
from src.utils import named_files  # noqa: E402
from src.utils.named_files import (  # noqa: E402
    find,
    is_built_in,
    names,
    new_file,
    path_of,
)

REPO = named_files.REPO


@pytest.fixture
def root(tmp_path):
    (tmp_path / "stages").mkdir()
    for name in ("box", "pillars"):
        shutil.copy(REPO / "stages" / f"{name}.json", tmp_path / "stages")
    mine = tmp_path / "user" / "stages"
    mine.mkdir(parents=True)
    ruins = json.loads((REPO / "stages" / "pillars.json").read_text())
    (mine / "ruins.json").write_text(json.dumps({**ruins, "name": "ruins"}))
    return tmp_path


def test_names_are_built_in_and_yours(root):
    assert names("stages", root) == ["box", "pillars", "ruins"]
    assert is_built_in("stages", "box", root)
    assert not is_built_in("stages", "ruins", root)
    assert find("stages", "ruins", root) == root / "user/stages/ruins.json"
    assert names("rules", root) == []  # no folder yet: nothing


def test_a_built_in_wins_a_name(root):
    shadow = root / "user" / "stages" / "box.json"
    shadow.write_text("{}")
    assert find("stages", "box", root) == root / "stages" / "box.json"
    assert names("stages", root).count("box") == 1


def test_a_missing_name(root):
    with pytest.raises(FileNotFoundError, match="looked in stages/ and user"):
        find("stages", "nowhere", root)
    # The loaders report it their own way: they get the built-in path.
    assert path_of("stages", "nowhere", root) == root / "stages/nowhere.json"
    assert path_of("stages", "/a/b.json", root).name == "b.json"


def test_new_files_go_to_user_and_never_take_a_name(root):
    path = new_file("rules", "fast", root)
    assert path == root / "user" / "rules" / "fast.json"
    assert path.parent.is_dir()
    with pytest.raises(FileExistsError, match="stages/box.json"):
        new_file("stages", "box", root)
    with pytest.raises(FileExistsError, match="user/stages/ruins.json"):
        new_file("stages", "ruins", root)


def test_the_app_sees_your_maps(root):
    maps = {m.name for m in maps_data.load_maps(root, root / "runs")}
    assert maps == {"box", "pillars", "ruins"}
    assert maps_data.watch_stage("ruins", root) == "ruins"
    copy = maps_data.duplicate(root, "box", "box_copy")
    assert copy == root / "user" / "stages" / "box_copy.json"


def test_the_editor_saves_a_map_where_it_is(root):
    theirs = EditorModel("ruins", root=root)
    assert theirs.path == root / "user" / "stages" / "ruins.json"
    fresh = EditorModel("fresh", root=root)
    fresh.save()
    assert (root / "user" / "stages" / "fresh.json").exists()
    assert not (root / "stages" / "fresh.json").exists()


def test_the_files_tab_saves_where_a_file_is(root):
    (root / "rules").mkdir()
    shutil.copy(REPO / "rules" / "standard.json", root / "rules")
    kind = next(k for k in files.KINDS if k.folder == "rules")
    data = files.load(root, kind, "standard")
    files.save(root, kind, "standard", data)  # a built-in: in place, 7d1a
    assert not (root / "user" / "rules" / "standard.json").exists()
    files.duplicate(root, kind, "standard", "mine_fast")
    assert (root / "user" / "rules" / "mine_fast.json").exists()
    assert "mine_fast" in files.names(root, kind)


def test_the_trash_takes_your_files(root):
    entry = Trash(root).delete_file("stages", "ruins")
    assert not (root / "user" / "stages" / "ruins.json").exists()
    assert entry
    with pytest.raises(TrashError):
        Trash(root).delete_file("stages", "ruins")
