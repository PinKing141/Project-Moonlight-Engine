from pathlib import Path

from rpg.presentation.windowing.contracts import DisplayMode
from rpg.presentation.windowing.window_menu import _character_options, _display_mode_label, _next_display_mode


class _Char:
    def __init__(self, id, name, level, alive=True):
        self.id = id
        self.name = name
        self.level = level
        self.alive = alive


class _Service:
    def list_character_summaries(self):
        return [
            _Char(1, "Ari", 3, True),
            _Char(0, "Invalid", 1, True),
            _Char(2, "Bex", 4, False),
        ]


def test_next_display_mode_cycles():
    assert _next_display_mode(DisplayMode.WINDOWED) == DisplayMode.MAXIMIZED
    assert _next_display_mode(DisplayMode.MAXIMIZED) == DisplayMode.FULLSCREEN
    assert _next_display_mode(DisplayMode.FULLSCREEN) == DisplayMode.WINDOWED


def test_display_mode_label_values():
    assert _display_mode_label(DisplayMode.WINDOWED) == "Windowed"
    assert _display_mode_label(DisplayMode.MAXIMIZED) == "Maximised"
    assert _display_mode_label(DisplayMode.FULLSCREEN) == "Fullscreen"


def test_character_options_filters_invalid_ids_and_marks_dead():
    rows = _character_options(_Service())
    assert rows == [
        ("Ari (Level 3)", 1),
        ("Bex (Level 4) [DEAD]", 2),
    ]
