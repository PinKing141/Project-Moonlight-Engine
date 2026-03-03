from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from rpg.presentation.windowing.contracts import DisplayMode


@dataclass
class WindowSettings:
    display_mode: DisplayMode = DisplayMode.WINDOWED
    font_scale: float = 1.0


DEFAULT_SETTINGS_PATH = Path.home() / ".moonlight_window_settings.json"


def load_window_settings(path: Path = DEFAULT_SETTINGS_PATH) -> WindowSettings:
    if not path.exists():
        return WindowSettings()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return WindowSettings()
    mode_value = str(payload.get("display_mode", DisplayMode.WINDOWED.value))
    mode = DisplayMode(mode_value) if mode_value in {m.value for m in DisplayMode} else DisplayMode.WINDOWED
    scale = float(payload.get("font_scale", 1.0) or 1.0)
    return WindowSettings(display_mode=mode, font_scale=max(0.5, min(2.5, scale)))


def save_window_settings(settings: WindowSettings, path: Path = DEFAULT_SETTINGS_PATH) -> None:
    serializable = asdict(settings)
    serializable["display_mode"] = settings.display_mode.value
    path.write_text(json.dumps(serializable, indent=2), encoding="utf-8")
