import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.domain.models.entity import Entity


class EntityModelTests(unittest.TestCase):
    def test_entity_accepts_tags_and_resistances(self) -> None:
        entity = Entity(
            id=7,
            name="Ash Wraith",
            level=4,
            hp=22,
            armour_class=14,
            attack_bonus=5,
            damage_die="1d8+2",
            tags=["undead", "spirit"],
            resistances=["fire", "poison"],
        )

        self.assertEqual(["undead", "spirit"], entity.tags)
        self.assertEqual(["fire", "poison"], entity.resistances)

    def test_entity_combat_fields_unchanged_with_tags(self) -> None:
        entity = Entity(
            id=8,
            name="Cave Stalker",
            level=3,
            hp=18,
            attack_min=2,
            attack_max=5,
            armor=1,
            armour_class=13,
            attack_bonus=4,
            damage_die="1d8+1",
            tags=["beast", "ambusher"],
            resistances=["cold"],
        )

        stats = entity.combat_stats

        self.assertEqual(18, stats.hp)
        self.assertEqual(2, stats.attack_min)
        self.assertEqual(5, stats.attack_max)
        self.assertEqual(1, stats.armor)
        self.assertEqual(13, stats.armour_class)
        self.assertEqual(4, stats.attack_bonus)
        self.assertEqual("1d8+1", stats.damage_die)
        self.assertEqual(["beast", "ambusher"], stats.tags)


if __name__ == "__main__":
    unittest.main()
