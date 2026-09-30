"""The Settings tab (roadmap 7c6). Its file is a scratch one: yours is
never read or written here.
"""

import json
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402
import pygame_gui  # noqa: E402
import pytest  # noqa: E402

from src.utils.settings import OPTIONS, Settings  # noqa: E402


@pytest.fixture
def window(tmp_path):
    from src.control.window import ControlCenter

    path = tmp_path / "user" / "settings.json"
    center = ControlCenter(settings_file=path)
    center.open_tab("Settings")
    center.settings_path = path
    yield center
    center.jobs.stop_all()


def _pick(window, key, shown):
    """Picks a dropdown choice the way pygame_gui reports it."""
    tab = window.settings_tab
    option = next(o for o in OPTIONS if o.key == key)
    index = [text for _, text in option.choices].index(shown)
    menu = tab.menus[key]
    menu.selected_option = (shown, str(index))
    window.handle(
        pygame.event.Event(
            pygame_gui.UI_DROP_DOWN_MENU_CHANGED,
            ui_element=menu,
            text=shown,
        )
    )


def test_the_tab_opens_with_every_setting(window):
    tab = window.settings_tab
    assert window.tab == "Settings"
    assert set(tab.menus) == {o.key for o in OPTIONS}
    assert all(menu.visible for menu in tab.menus.values())
    window.draw()
    window.open_tab("Training")
    assert not any(menu.visible for menu in tab.menus.values())


def test_a_pick_saves_at_once(window):
    _pick(window, "bars", "below")
    _pick(window, "fps_cap", "30")
    saved = json.loads(window.settings_path.read_text())
    assert saved["bars"] == "below" and saved["fps_cap"] == 30
    assert window.settings_tab.message[0].startswith("Saved: FPS cap is 30")


def test_a_change_made_in_a_game_window_shows_up(window):
    # A game window's O box saves the same file.
    Settings.load(window.settings_path).step("lines")  # on -> off
    window.settings_tab.refresh(force=True)
    menu = window.settings_tab.menus["lines"]
    assert menu.selected_option[0] == "off"


def test_without_a_file_it_stays_in_memory(tmp_path):
    from src.control.settings_tab import SettingsTab

    gui = pygame_gui.UIManager((800, 600))
    tab = SettingsTab(gui, pygame.Rect(0, 0, 800, 600))
    tab.pick("bars", 1)
    assert tab.settings["bars"] == "below" and tab.path is None
