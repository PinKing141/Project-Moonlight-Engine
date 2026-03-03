import unittest
from unittest import mock

from rpg.presentation.load_menu import choose_existing_character


class _Character:
    def __init__(self, cid, name="Asha", level=1, alive=True):
        self.id = cid
        self.name = name
        self.level = level
        self.alive = alive


class _Service:
    def __init__(self, characters):
        self._characters = characters

    def list_character_summaries(self):
        return list(self._characters)


class LoadMenuTests(unittest.TestCase):
    def test_choose_existing_character_filters_invalid_ids(self) -> None:
        service = _Service([_Character(0, name="Ghost"), _Character(4, name="Asha")])
        with mock.patch("rpg.presentation.load_menu.arrow_menu", return_value=0):
            chosen = choose_existing_character(service)
        self.assertEqual(4, chosen)

    def test_choose_existing_character_ignores_non_numeric_ids(self) -> None:
        service = _Service([_Character("abc", name="Ghost"), _Character(7, name="Asha")])
        with mock.patch("rpg.presentation.load_menu.arrow_menu", return_value=0):
            chosen = choose_existing_character(service)
        self.assertEqual(7, chosen)

    def test_choose_existing_character_returns_none_when_only_invalid_ids_exist(self) -> None:
        service = _Service([_Character(0), _Character(None)])
        with mock.patch("rpg.presentation.load_menu.clear_screen"), mock.patch("builtins.input", return_value=""):
            chosen = choose_existing_character(service)
        self.assertIsNone(chosen)


if __name__ == "__main__":
    unittest.main()
