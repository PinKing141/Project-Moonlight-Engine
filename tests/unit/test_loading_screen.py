import io
import os
import unittest
from unittest import mock

from rpg.presentation.loading_screen import startup_loading_screen


class LoadingScreenTests(unittest.TestCase):
    def test_non_tty_prints_start_and_ready_lines(self) -> None:
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf), mock.patch.dict(os.environ, {"RPG_LOADING_SCREEN_ENABLED": "1"}, clear=False):
            with startup_loading_screen("Booting..."):
                pass

        text = buf.getvalue()
        self.assertIn("Booting...", text)
        self.assertIn("Ready in", text)

    def test_disabled_loading_screen_suppresses_output(self) -> None:
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf), mock.patch.dict(os.environ, {"RPG_LOADING_SCREEN_ENABLED": "0"}, clear=False):
            with startup_loading_screen("Booting..."):
                pass

        self.assertEqual("", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
