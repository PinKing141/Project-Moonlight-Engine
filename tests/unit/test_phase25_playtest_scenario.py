import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.infrastructure.playtest.phase25_scenario import Phase25LoopSelector


class Phase25LoopSelectorTests(unittest.TestCase):
    def test_selector_counts_travel_action_from_root_sequence(self) -> None:
        selector = Phase25LoopSelector()

        first = selector.choose("Anywhere — Actions", ["Act", "Travel", "Rest", "Character", "Quit"])
        second = selector.choose("Anywhere — Actions", ["Act", "Travel", "Rest", "Character", "Quit"])

        self.assertEqual(0, first)
        self.assertEqual(1, second)
        self.assertEqual(2, int(selector.state["root_actions"]))
        self.assertEqual(1, int(selector.state["travel_actions"]))

    def test_selector_counts_destination_hops_only_when_destination_list_exists(self) -> None:
        selector = Phase25LoopSelector()

        idx_with_destinations = selector.choose("Leave Town", ["Old Ruins", "Back"])
        hops_after_destination_menu = int(selector.state["travel_hops"])
        idx_without_destinations = selector.choose("Return to Town", ["Back"])
        hops_after_back_only_menu = int(selector.state["travel_hops"])

        self.assertEqual(0, idx_with_destinations)
        self.assertEqual(1, hops_after_destination_menu)
        self.assertEqual(0, idx_without_destinations)
        # Destination hops count only for menus with a real destination row.
        self.assertEqual(1, hops_after_back_only_menu)


if __name__ == "__main__":
    unittest.main()
