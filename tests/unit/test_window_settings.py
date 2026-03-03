from pathlib import Path

from rpg.presentation.windowing.contracts import DisplayMode
from rpg.presentation.windowing.settings import WindowSettings, load_window_settings, save_window_settings


def test_load_window_settings_defaults_when_missing(tmp_path: Path) -> None:
    path = tmp_path / "missing.json"
    settings = load_window_settings(path)
    assert settings.display_mode == DisplayMode.WINDOWED
    assert settings.font_scale == 1.0


def test_save_and_load_window_settings_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "window_settings.json"
    save_window_settings(WindowSettings(display_mode=DisplayMode.FULLSCREEN, font_scale=1.25), path)
    loaded = load_window_settings(path)
    assert loaded.display_mode == DisplayMode.FULLSCREEN
    assert loaded.font_scale == 1.25
