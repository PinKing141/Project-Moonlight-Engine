import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.character_creation_service import CharacterCreationService
from rpg.application.services.balance_tables import DIFFICULTY_PRESET_PROFILES
from rpg.infrastructure.db.inmemory.repos import (
    InMemoryCharacterRepository,
    InMemoryClassRepository,
    InMemoryLocationRepository,
)
from rpg.domain.models.character_class import CharacterClass
from rpg.domain.models.location import Location


class DifficultyCalibrationTests(unittest.TestCase):
    def _build_service(self) -> CharacterCreationService:
        return CharacterCreationService(
            character_repo=InMemoryCharacterRepository({}),
            class_repo=InMemoryClassRepository([
                CharacterClass(id=1, name="Fighter", slug="fighter", hit_die="d10", primary_ability="strength")
            ]),
            location_repo=InMemoryLocationRepository({1: Location(id=1, name="Start")}),
        )

    def test_default_difficulty_profiles_match_central_balance_table(self) -> None:
        service = self._build_service()
        presets = {preset.slug: preset for preset in service.list_difficulties()}

        for slug, profile in DIFFICULTY_PRESET_PROFILES.items():
            self.assertIn(slug, presets)
            preset = presets[slug]
            self.assertEqual(profile["hp_multiplier"], preset.hp_multiplier)
            self.assertEqual(profile["incoming_damage_multiplier"], preset.incoming_damage_multiplier)
            self.assertEqual(profile["outgoing_damage_multiplier"], preset.outgoing_damage_multiplier)

    def test_difficulty_multipliers_follow_expected_progression(self) -> None:
        service = self._build_service()
        presets = {preset.slug: preset for preset in service.list_difficulties()}

        story = presets["story"]
        normal = presets["normal"]
        hardcore = presets["hardcore"]

        self.assertGreater(story.hp_multiplier, normal.hp_multiplier)
        self.assertGreater(normal.hp_multiplier, hardcore.hp_multiplier)

        self.assertLess(story.incoming_damage_multiplier, normal.incoming_damage_multiplier)
        self.assertLess(normal.incoming_damage_multiplier, hardcore.incoming_damage_multiplier)

        self.assertGreater(hardcore.outgoing_damage_multiplier, normal.outgoing_damage_multiplier)


if __name__ == "__main__":
    unittest.main()
