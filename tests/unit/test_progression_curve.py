import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.balance_tables import (
    FIRST_HUNT_REWARD_MONEY,
    FIRST_HUNT_REWARD_XP,
    monster_kill_gold,
    monster_kill_xp,
)


class ProgressionCurveTests(unittest.TestCase):
    def test_mid_game_reward_curve_has_no_dead_progression(self) -> None:
        levels = [1, 2, 3, 4, 5, 6]
        encounters_per_level = 3

        total_xp = FIRST_HUNT_REWARD_XP
        total_money = FIRST_HUNT_REWARD_MONEY
        per_level_xp_gain: list[int] = []
        per_level_money_gain: list[int] = []

        for level in levels:
            level_xp = 0
            level_money = 0
            for _ in range(encounters_per_level):
                level_xp += monster_kill_xp(level)
                level_money += monster_kill_gold(level)

            per_level_xp_gain.append(level_xp)
            per_level_money_gain.append(level_money)
            total_xp += level_xp
            total_money += level_money

        self.assertTrue(all(gain > 0 for gain in per_level_xp_gain))
        self.assertTrue(all(gain > 0 for gain in per_level_money_gain))

        self.assertGreater(per_level_xp_gain[3], per_level_xp_gain[0])
        self.assertGreater(per_level_money_gain[3], per_level_money_gain[0])

        self.assertGreater(total_xp, FIRST_HUNT_REWARD_XP)
        self.assertGreater(total_money, FIRST_HUNT_REWARD_MONEY)


if __name__ == "__main__":
    unittest.main()
