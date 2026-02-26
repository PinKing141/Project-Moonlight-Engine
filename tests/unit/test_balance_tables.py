import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.balance_tables import (
    monster_kill_gold,
    monster_kill_xp,
    rest_heal_amount,
    xp_required_for_level,
)


class BalanceTablesTests(unittest.TestCase):
    def test_rest_heal_amount_has_floor(self) -> None:
        self.assertEqual(4, rest_heal_amount(10))
        self.assertEqual(5, rest_heal_amount(20))

    def test_monster_rewards_scale_with_level_and_minimums(self) -> None:
        self.assertEqual(1, monster_kill_xp(0))
        self.assertEqual(5, monster_kill_xp(1))
        self.assertEqual(2, monster_kill_gold(1))
        self.assertEqual(6, monster_kill_gold(3))

    def test_xp_required_for_level_scales_linearly(self) -> None:
        self.assertEqual(0, xp_required_for_level(1))
        self.assertEqual(25, xp_required_for_level(2))
        self.assertEqual(50, xp_required_for_level(3))


if __name__ == "__main__":
    unittest.main()
