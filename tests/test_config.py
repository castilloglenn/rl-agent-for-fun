import json

from src.config import (
    GAME_KEYS,
    PRESENTATION_KEYS,
    game_config,
    get_maze_car_config,
)


def test_every_top_level_key_is_classified():
    """A new key must be added to GAME_KEYS or PRESENTATION_KEYS."""
    keys = set(get_maze_car_config().keys())
    assert keys == set(GAME_KEYS) | set(PRESENTATION_KEYS)
    assert not set(GAME_KEYS) & set(PRESENTATION_KEYS)


def test_game_config_has_only_game_defining_keys():
    data = game_config(get_maze_car_config())
    assert set(data) == set(GAME_KEYS)
    assert json.loads(json.dumps(data)) == data  # plain, JSON-ready data


def test_presentation_changes_leave_game_config_unchanged():
    config = get_maze_car_config()
    before = game_config(config)
    config.hud.near_caution = 99.0
    config.show_gui = False
    config.display.max_fps = 30
    assert game_config(config) == before


def test_game_changes_show_up_in_game_config():
    config = get_maze_car_config()
    before = game_config(config)
    config.car.max_speed = 250.0
    assert game_config(config) != before


def test_config_with_game_skips_keys_that_no_longer_exist():
    """Old replays hold removed keys; the flags' config is locked."""
    from src.config import config_with_game

    base = get_maze_car_config()
    base.lock()
    old = {"round": {"seconds": 30.0}, "car": {"max_speed": 250.0, "gone": 1}}
    config = config_with_game(old, base)
    assert config.car.max_speed == 250.0
    assert "round" not in config
