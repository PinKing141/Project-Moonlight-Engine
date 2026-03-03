import sys
from pathlib import Path
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.check_resolution_service import CheckResolutionService


class V18CheckResolutionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = CheckResolutionService()

    def test_deterministic_for_identical_namespace_and_context(self) -> None:
        first = self.service.resolve(
            namespace="v18.test",
            context={"character_id": 11, "turn": 4, "action": "scout"},
            dc=13,
            modifier=2,
        )
        second = self.service.resolve(
            namespace="v18.test",
            context={"character_id": 11, "turn": 4, "action": "scout"},
            dc=13,
            modifier=2,
        )

        self.assertEqual(first.seed, second.seed)
        self.assertEqual(first.selected_roll, second.selected_roll)
        self.assertEqual(first.total, second.total)
        self.assertEqual(first.margin, second.margin)

    def test_seed_changes_for_different_context(self) -> None:
        first = self.service.resolve(namespace="v18.test", context={"character_id": 11, "turn": 4}, dc=13)
        second = self.service.resolve(namespace="v18.test", context={"character_id": 12, "turn": 4}, dc=13)
        self.assertNotEqual(first.seed, second.seed)

    def test_normal_mode_uses_single_roll(self) -> None:
        with mock.patch("random.Random.randint", return_value=14):
            outcome = self.service.resolve(namespace="v18.test", context={"k": "v"}, dc=12, modifier=1)
        self.assertEqual("normal", outcome.roll_mode)
        self.assertEqual((14,), outcome.rolls)
        self.assertEqual(15, outcome.total)

    def test_advantage_uses_higher_of_two_rolls(self) -> None:
        with mock.patch("random.Random.randint", side_effect=[4, 17]):
            outcome = self.service.resolve(namespace="v18.test", context={"k": "v"}, dc=12, advantage=True)
        self.assertEqual("advantage", outcome.roll_mode)
        self.assertEqual((4, 17), outcome.rolls)
        self.assertEqual(17, outcome.selected_roll)

    def test_disadvantage_uses_lower_of_two_rolls(self) -> None:
        with mock.patch("random.Random.randint", side_effect=[4, 17]):
            outcome = self.service.resolve(namespace="v18.test", context={"k": "v"}, dc=12, disadvantage=True)
        self.assertEqual("disadvantage", outcome.roll_mode)
        self.assertEqual((4, 17), outcome.rolls)
        self.assertEqual(4, outcome.selected_roll)

    def test_advantage_and_disadvantage_cancel_to_normal(self) -> None:
        with mock.patch("random.Random.randint", return_value=10) as mocked_randint:
            outcome = self.service.resolve(
                namespace="v18.test",
                context={"k": "v"},
                dc=12,
                advantage=True,
                disadvantage=True,
            )
        self.assertEqual("normal", outcome.roll_mode)
        self.assertEqual(1, mocked_randint.call_count)
        self.assertEqual((10,), outcome.rolls)

    def test_dc_clamps_to_minimum(self) -> None:
        outcome = self.service.resolve(namespace="v18.test", context={"k": "v"}, dc=1, min_dc=8, max_dc=20)
        self.assertEqual(8, outcome.dc)

    def test_dc_clamps_to_maximum(self) -> None:
        outcome = self.service.resolve(namespace="v18.test", context={"k": "v"}, dc=99, min_dc=8, max_dc=20)
        self.assertEqual(20, outcome.dc)

    def test_consequence_tag_strong_success_when_margin_high(self) -> None:
        with mock.patch("random.Random.randint", return_value=19):
            outcome = self.service.resolve(namespace="v18.test", context={"k": "v"}, dc=10, modifier=0)
        self.assertEqual("strong_success", outcome.consequence_tag)

    def test_consequence_tag_near_miss_when_margin_negative_one(self) -> None:
        with mock.patch("random.Random.randint", return_value=10):
            outcome = self.service.resolve(namespace="v18.test", context={"k": "v"}, dc=11, modifier=0)
        self.assertEqual("near_miss", outcome.consequence_tag)

    def test_consequence_tag_major_failure_when_margin_below_minus_five(self) -> None:
        with mock.patch("random.Random.randint", return_value=4):
            outcome = self.service.resolve(namespace="v18.test", context={"k": "v"}, dc=12, modifier=0)
        self.assertEqual("major_failure", outcome.consequence_tag)

    def test_difficulty_tier_mapping_uses_dc_band(self) -> None:
        trivial = self.service.resolve(namespace="v18.test", context={"i": 1}, dc=8)
        easy = self.service.resolve(namespace="v18.test", context={"i": 2}, dc=11)
        moderate = self.service.resolve(namespace="v18.test", context={"i": 3}, dc=14)
        hard = self.service.resolve(namespace="v18.test", context={"i": 4}, dc=17)
        very_hard = self.service.resolve(namespace="v18.test", context={"i": 5}, dc=20)
        extreme = self.service.resolve(namespace="v18.test", context={"i": 6}, dc=25)

        self.assertEqual("trivial", trivial.difficulty_tier)
        self.assertEqual("easy", easy.difficulty_tier)
        self.assertEqual("moderate", moderate.difficulty_tier)
        self.assertEqual("hard", hard.difficulty_tier)
        self.assertEqual("very_hard", very_hard.difficulty_tier)
        self.assertEqual("extreme", extreme.difficulty_tier)


if __name__ == "__main__":
    unittest.main()
