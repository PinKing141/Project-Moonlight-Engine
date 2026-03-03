import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.balance_tables import (
    difficulty_reward_multiplier,
    normalize_hardcore_toggles,
    resolve_difficulty_tier,
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

    def test_difficulty_aliases_resolve_to_five_tier_policy(self) -> None:
        self.assertEqual("normal", resolve_difficulty_tier("normal"))
        self.assertEqual("easy", resolve_difficulty_tier("easy"))
        self.assertEqual("hard", resolve_difficulty_tier("hard"))
        self.assertEqual("deadly", resolve_difficulty_tier("deadly"))
        self.assertEqual("nightmare", resolve_difficulty_tier("nightmare"))
        self.assertEqual("easy", resolve_difficulty_tier("story"))
        self.assertEqual("hard", resolve_difficulty_tier("hardcore"))
        self.assertEqual("normal", resolve_difficulty_tier("medium"))

    def test_reward_multiplier_tracks_risk_with_guardrails(self) -> None:
        easy_mult = difficulty_reward_multiplier("easy")
        normal_mult = difficulty_reward_multiplier("normal")
        hard_mult = difficulty_reward_multiplier("hard")
        nightmare_mult = difficulty_reward_multiplier("nightmare")

        self.assertLess(easy_mult, normal_mult)
        self.assertLess(normal_mult, hard_mult)
        self.assertLess(hard_mult, nightmare_mult)
        self.assertLessEqual(nightmare_mult, 1.30)

    def test_monster_rewards_apply_difficulty_scaling(self) -> None:
        self.assertLess(monster_kill_xp(2, difficulty_slug="easy"), monster_kill_xp(2, difficulty_slug="normal"))
        self.assertGreater(monster_kill_gold(5, difficulty_slug="hard"), monster_kill_gold(5, difficulty_slug="normal"))

    def test_hardcore_toggle_normalization_uses_defaults_and_aliases(self) -> None:
        normalized = normalize_hardcore_toggles({"max_monster_hp": 1, "rest_restrictions": True, "unknown_toggle": True})

        self.assertTrue(normalized["max_monster_hp"])
        self.assertTrue(normalized["rest_lock_on_failed_saves"])
        self.assertFalse(normalized["deadlier_death_saves"])

    def test_xp_required_for_level_scales_linearly(self) -> None:
        self.assertEqual(0, xp_required_for_level(1))
        self.assertEqual(25, xp_required_for_level(2))
        self.assertEqual(50, xp_required_for_level(3))


if __name__ == "__main__":
    unittest.main()
