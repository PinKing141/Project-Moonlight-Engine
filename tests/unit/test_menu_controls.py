import sys
from pathlib import Path
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.presentation import menu_controls


class MenuControlTests(unittest.TestCase):
    def test_normalize_menu_key_maps_common_fallback_keys(self) -> None:
        self.assertEqual("UP", menu_controls.normalize_menu_key("w"))
        self.assertEqual("DOWN", menu_controls.normalize_menu_key("s"))
        self.assertEqual("ENTER", menu_controls.normalize_menu_key(""))
        self.assertEqual("ESC", menu_controls.normalize_menu_key("q"))

    def test_arrow_menu_accepts_w_s_navigation_in_fallback_mode(self) -> None:
        with mock.patch.object(menu_controls, "msvcrt", None), mock.patch.object(
            menu_controls, "clear_screen", return_value=None
        ), mock.patch.object(
            menu_controls,
            "read_key",
            side_effect=["s", ""],
        ):
            idx = menu_controls.arrow_menu("Title", ["One", "Two", "Three"])
        self.assertEqual(1, idx)

    def test_arrow_menu_accepts_q_as_escape(self) -> None:
        with mock.patch.object(menu_controls, "msvcrt", None), mock.patch.object(
            menu_controls, "clear_screen", return_value=None
        ), mock.patch.object(
            menu_controls,
            "read_key",
            side_effect=["q"],
        ):
            idx = menu_controls.arrow_menu("Title", ["One", "Two"])
        self.assertEqual(-1, idx)

    def test_arrow_menu_flushes_windows_stale_keys_before_read(self) -> None:
        fake_msvcrt = mock.Mock()
        fake_msvcrt.kbhit.side_effect = [True, True, False]
        fake_msvcrt.getch.side_effect = [b"x", b"y"]

        with mock.patch.object(menu_controls, "msvcrt", fake_msvcrt), mock.patch.object(
            menu_controls, "clear_screen", return_value=None
        ), mock.patch.object(menu_controls, "read_key", side_effect=["ENTER"]), mock.patch.object(
            menu_controls.time, "monotonic", side_effect=[1.0, 1.3, 1.5]
        ):
            idx = menu_controls.arrow_menu("Title", ["One", "Two"])

        self.assertEqual(0, idx)
        self.assertEqual(2, fake_msvcrt.getch.call_count)

    def test_arrow_menu_debounces_rapid_repeat_navigation(self) -> None:
        with mock.patch.object(menu_controls, "_CONSOLE", None), mock.patch.object(
            menu_controls, "Live", None
        ), mock.patch.object(menu_controls, "clear_screen", return_value=None), mock.patch.object(
            menu_controls, "read_key", side_effect=["s", "s", ""]
        ), mock.patch.object(menu_controls.time, "monotonic", side_effect=[1.00, 1.03, 1.06, 1.40]):
            idx = menu_controls.arrow_menu("Title", ["One", "Two", "Three"])

        self.assertEqual(1, idx)

    def test_arrow_menu_ignores_initial_carried_enter(self) -> None:
        fake_msvcrt = mock.Mock()
        fake_msvcrt.kbhit.return_value = False

        with mock.patch.object(menu_controls, "msvcrt", fake_msvcrt), mock.patch.object(
            menu_controls, "_CONSOLE", None
        ), mock.patch.object(menu_controls, "Live", None), mock.patch.object(
            menu_controls, "clear_screen", return_value=None
        ), mock.patch.object(menu_controls, "read_key", side_effect=["ENTER", "ENTER", "ENTER"]), mock.patch.object(
            menu_controls.time, "monotonic", side_effect=[1.00, 1.05, 1.10, 1.30]
        ):
            idx = menu_controls.arrow_menu("Title", ["One", "Two"])

        self.assertEqual(0, idx)

    def test_arrow_menu_ignores_enter_immediately_after_navigation(self) -> None:
        fake_msvcrt = mock.Mock()
        fake_msvcrt.kbhit.return_value = False

        with mock.patch.object(menu_controls, "msvcrt", fake_msvcrt), mock.patch.object(
            menu_controls, "_CONSOLE", None
        ), mock.patch.object(menu_controls, "Live", None), mock.patch.object(
            menu_controls, "clear_screen", return_value=None
        ), mock.patch.object(menu_controls, "read_key", side_effect=["s", "ENTER", "ENTER"]), mock.patch.object(
            menu_controls.time, "monotonic", side_effect=[1.00, 1.10, 1.20, 1.45]
        ):
            idx = menu_controls.arrow_menu("Title", ["One", "Two", "Three"])

        self.assertEqual(1, idx)


if __name__ == "__main__":
    unittest.main()
