import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.seed_policy import derive_rng, derive_seed


class SeedPolicyTests(unittest.TestCase):
    def test_same_context_same_seed(self) -> None:
        context = {
            "world_turn": 9,
            "player_id": 1,
            "enemy_id": 2,
            "scene": {"distance": "mid", "terrain": "open"},
        }
        self.assertEqual(derive_seed("combat.resolve", context), derive_seed("combat.resolve", context))

    def test_context_key_order_does_not_change_seed(self) -> None:
        context_a = {"a": 1, "b": {"x": 2, "y": 3}}
        context_b = {"b": {"y": 3, "x": 2}, "a": 1}
        self.assertEqual(derive_seed("encounter.plan", context_a), derive_seed("encounter.plan", context_b))

    def test_namespace_changes_seed(self) -> None:
        context = {"value": 10}
        self.assertNotEqual(derive_seed("encounter.plan", context), derive_seed("combat.resolve", context))

    def test_unordered_set_values_produce_stable_seed(self) -> None:
        context_a = {"flags": {"night", "storm", "wardens"}}
        context_b = {"flags": {"wardens", "night", "storm"}}
        self.assertEqual(derive_seed("world.tick", context_a), derive_seed("world.tick", context_b))

    def test_non_finite_float_in_context_raises(self) -> None:
        with self.assertRaises(ValueError):
            derive_seed("world.tick", {"threat": float("nan")})

    def test_derive_rng_is_deterministic_for_same_context(self) -> None:
        context = {"world_turn": 12, "enemy_id": 4, "character_id": 9}
        rng_a = derive_rng("encounter.intro", context)
        rng_b = derive_rng("encounter.intro", context)
        self.assertEqual(rng_a.randint(1, 1000), rng_b.randint(1, 1000))

    def test_derive_rng_changes_with_namespace(self) -> None:
        context = {"world_turn": 12, "enemy_id": 4, "character_id": 9}
        rng_a = derive_rng("encounter.intro", context)
        rng_b = derive_rng("encounter.loot", context)
        self.assertNotEqual(rng_a.randint(1, 1000), rng_b.randint(1, 1000))


if __name__ == "__main__":
    unittest.main()
