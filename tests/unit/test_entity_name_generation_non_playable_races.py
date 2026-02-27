import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.infrastructure.name_generation import DnDCorpusNameGenerator


class EntityNameGenerationNonPlayableRaceTests(unittest.TestCase):
    def test_generate_entity_name_uses_non_playable_race_pool_from_default_name(self) -> None:
        generator = DnDCorpusNameGenerator()

        generated = generator.generate_entity_name(
            default_name="Goblin",
            kind="humanoid",
            faction_id="raiders",
            entity_id=11,
            level=1,
        )

        self.assertTrue(bool(generated))
        self.assertNotEqual("Goblin", generated)

    def test_generate_entity_name_uses_kind_mapping_for_enemy_archetypes(self) -> None:
        generator = DnDCorpusNameGenerator()

        generated = generator.generate_entity_name(
            default_name="Ogre",
            kind="giant",
            faction_id="mountain_clan",
            entity_id=42,
            level=6,
        )

        self.assertTrue(bool(generated))
        self.assertNotEqual("Ogre", generated)

    def test_generate_entity_name_keeps_default_for_unmapped_kind(self) -> None:
        generator = DnDCorpusNameGenerator()

        generated = generator.generate_entity_name(
            default_name="Dire Wolf",
            kind="beast",
            faction_id="wilds",
            entity_id=5,
            level=2,
        )

        self.assertEqual("Dire Wolf", generated)


if __name__ == "__main__":
    unittest.main()
