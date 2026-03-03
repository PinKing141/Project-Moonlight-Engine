import io
import os
import unittest
from unittest import mock

from rpg.presentation.sound_effects import SoundEffects


class SoundEffectsTests(unittest.TestCase):
    def test_from_env_defaults_disabled(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            sfx = SoundEffects.from_env()
        self.assertFalse(sfx.enabled)

    def test_play_writes_terminal_bell_when_enabled(self) -> None:
        sfx = SoundEffects(enabled=True, min_interval_s=0.0)
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            sfx.play("game_start")
        self.assertEqual("\a\a", buf.getvalue())

    def test_play_is_throttled(self) -> None:
        sfx = SoundEffects(enabled=True, min_interval_s=999.0)
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            sfx.play("menu_select")
            sfx.play("menu_select")
        self.assertEqual("\a", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
