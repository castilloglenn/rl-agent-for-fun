"""Your display settings (roadmap 7c5, decision 040). Files live in
tmp_path: the real user/settings.json is never read or written here.
"""

import json
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

from src.config import get_maze_car_config  # noqa: E402
from src.render import theme  # noqa: E402
from src.render.camera import FIT, FOLLOW  # noqa: E402
from src.render.renderer import Renderer  # noqa: E402
from src.sim.components import Health, Transform  # noqa: E402
from src.sim.factories import create_start_car, create_world  # noqa: E402
from src.utils.settings import OPTIONS, Settings  # noqa: E402

# The file


def test_defaults_without_a_file(tmp_path):
    settings = Settings.load(tmp_path / "none.json")
    assert settings["bars"] == "above" and settings["lines"] is True
    assert settings["fps_cap"] == 0 and settings.shown("fps_cap") == (
        "display's rate"
    )
    assert not (tmp_path / "none.json").exists()  # reading writes nothing


def test_a_hand_edited_file_cant_break_it(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps(
            {"bars": "below", "lines": 1, "fps_cap": 45, "shiny": True}
        )
    )
    settings = Settings.load(path)
    assert settings["bars"] == "below"  # a real choice: kept
    assert settings["lines"] is True  # 1 isn't a choice: the default
    assert settings["fps_cap"] == 0
    path.write_text("{not json")
    assert Settings.load(path)["bars"] == "above"


def test_stepping_cycles_and_saves(tmp_path):
    path = tmp_path / "user" / "settings.json"
    settings = Settings.load(path)
    settings.step("fps_cap")
    assert settings["fps_cap"] == 60
    assert json.loads(path.read_text())["fps_cap"] == 60
    settings.step("fps_cap", -1)
    settings.step("fps_cap", -1)
    assert settings["fps_cap"] == 30  # wraps around
    assert Settings.load(path)["fps_cap"] == 30


# The game window


def _renderer(tmp_path, stage="box", **values):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(values))
    config = get_maze_car_config()
    config.stage = stage
    config.window.settings_file = str(path)
    renderer = Renderer(config)
    world = create_world(config)
    car = create_start_car(world)
    world.step()
    return renderer, world, car, path


def _key(renderer, key):
    renderer._key(key, False, set())


def _bar_rows(renderer, world, car):
    """The rows (screen y) holding the health bar's colors, near the car."""
    renderer.draw(world)
    transform = world.component(car, Transform)
    x, y = renderer.camera.to_screen(transform.x, transform.y)
    rows = set()
    for dy in range(-30, 31):
        for dx in range(-12, 12):
            spot = (round(x) + dx, round(y) + dy)
            color = tuple(renderer.display.get_at(spot))[:3]
            if color in (theme.GOOD, theme.BAD, theme.BAR_EMPTY):
                rows.add(dy)
    return rows


def test_o_opens_the_box_and_changes_are_live_and_saved(tmp_path):
    renderer, world, car, path = _renderer(tmp_path)
    _key(renderer, pygame.K_o)
    assert renderer.show_settings and renderer.modal_open
    renderer.draw(world)  # the box draws
    assert OPTIONS[renderer.setting].key == "bars"
    _key(renderer, pygame.K_RIGHT)  # above -> below
    assert renderer.settings["bars"] == "below"
    assert json.loads(path.read_text())["bars"] == "below"
    _key(renderer, pygame.K_r)  # other keys are the box's: nothing
    assert renderer.show_settings
    _key(renderer, pygame.K_ESCAPE)
    assert not renderer.show_settings and not renderer.confirm_quit


def test_the_bars_go_above_or_below_and_can_hide(tmp_path):
    renderer, world, car, _ = _renderer(tmp_path)
    assert all(dy < 0 for dy in _bar_rows(renderer, world, car))
    renderer, world, car, _ = _renderer(tmp_path, bars="below")
    rows = _bar_rows(renderer, world, car)
    assert rows and all(dy > 0 for dy in rows)
    renderer, world, car, _ = _renderer(tmp_path, bars_shown="damaged")
    assert not _bar_rows(renderer, world, car)  # full health: hidden
    health = world.component(car, Health)
    health.current = health.maximum / 2
    assert _bar_rows(renderer, world, car)


def _field_colors(renderer, world):
    renderer.draw(world)
    field = renderer.display.subsurface(renderer.layout.field_view)
    data = pygame.image.tobytes(field, "RGB")
    return {tuple(data[i : i + 3]) for i in range(0, len(data), 3)}


def test_one_lines_setting_hides_rays_and_the_guide(tmp_path):
    renderer, world, _, _ = _renderer(tmp_path, lines=False)
    colors = _field_colors(renderer, world)
    assert theme.RAY not in colors and theme.GUIDE not in colors
    assert not renderer.show_lines


def test_h_t_and_f_keep_your_settings_in_sync(tmp_path):
    renderer, world, _, path = _renderer(tmp_path, stage="arena")
    _key(renderer, pygame.K_h)
    assert not renderer.show_lines and renderer.settings["lines"] is False
    assert json.loads(path.read_text())["lines"] is False
    assert theme.RAY not in _field_colors(renderer, world)
    _key(renderer, pygame.K_t)
    assert renderer.show_trail and renderer.settings["trail"] is True
    _key(renderer, pygame.K_f)
    assert renderer.camera.mode == FIT
    assert json.loads(path.read_text())["big_stage_camera"] == "fit"
    _key(renderer, pygame.K_o)  # the box shows what the keys set
    at = [o.key for o in OPTIONS].index("lines")
    renderer.setting = at
    _key(renderer, pygame.K_RIGHT)  # and the box sets what H shows
    assert renderer.show_lines and renderer.settings["lines"] is True


def test_camera_trail_and_fps_settings(tmp_path):
    renderer, *_ = _renderer(tmp_path, stage="arena")
    assert renderer.camera.mode == FOLLOW and renderer.map_intro
    renderer, *_ = _renderer(
        tmp_path,
        stage="arena",
        big_stage_camera="fit",
        map_intro=False,
        trail=True,
        fps_cap=30,
    )
    assert renderer.camera.mode == FIT and not renderer.map_intro
    assert renderer.show_trail and renderer.frame_rate == 30


def test_every_mode_lists_o(tmp_path, monkeypatch):
    import src.render.renderer as module

    renderer, world, *_ = _renderer(tmp_path)
    drawn = []
    real = module.draw_text

    def spy(surface, text, *args, **kwargs):
        drawn.append(text)
        return real(surface, text, *args, **kwargs)

    monkeypatch.setattr(module, "draw_text", spy)
    renderer.show_shortcuts = True
    renderer.draw(world)
    assert "O" in drawn and "settings" in drawn
