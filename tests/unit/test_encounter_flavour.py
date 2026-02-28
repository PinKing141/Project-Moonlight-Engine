import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.encounter_flavour import random_intro
from rpg.domain.models.entity import Entity


class EncounterFlavourTests(unittest.TestCase):
    def test_random_intro_with_seed_is_deterministic(self) -> None:
        enemy = Entity(id=7, name="Ghoul", level=2, kind="undead")
        intro_a = random_intro(enemy, seed=12345)
        intro_b = random_intro(enemy, seed=12345)
        self.assertEqual(intro_a, intro_b)

    def test_random_intro_uses_enemy_name(self) -> None:
        enemy = Entity(id=3, name="Bandit", level=1, kind="humanoid")
        intro = random_intro(enemy, seed=99)
        self.assertIn("Bandit", intro)


if __name__ == "__main__":
    unittest.main()
