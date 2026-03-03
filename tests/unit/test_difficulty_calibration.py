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

        easy = presets["easy"]
        normal = presets["normal"]
        hard = presets["hard"]
        deadly = presets["deadly"]
        nightmare = presets["nightmare"]

        self.assertGreater(easy.hp_multiplier, normal.hp_multiplier)
        self.assertGreater(normal.hp_multiplier, hard.hp_multiplier)
        self.assertGreater(hard.hp_multiplier, deadly.hp_multiplier)
        self.assertGreater(deadly.hp_multiplier, nightmare.hp_multiplier)

        self.assertLess(easy.incoming_damage_multiplier, normal.incoming_damage_multiplier)
        self.assertLess(normal.incoming_damage_multiplier, hard.incoming_damage_multiplier)
        self.assertLess(hard.incoming_damage_multiplier, deadly.incoming_damage_multiplier)
        self.assertLess(deadly.incoming_damage_multiplier, nightmare.incoming_damage_multiplier)

        self.assertGreater(hard.outgoing_damage_multiplier, normal.outgoing_damage_multiplier)
        self.assertGreaterEqual(deadly.outgoing_damage_multiplier, hard.outgoing_damage_multiplier)
        self.assertGreaterEqual(nightmare.outgoing_damage_multiplier, deadly.outgoing_damage_multiplier)

    def test_difficulty_presets_expose_risk_guardrail_and_legacy_metadata(self) -> None:
        service = self._build_service()
        presets = {preset.slug: preset for preset in service.list_difficulties()}

        self.assertTrue(str(presets["easy"].risk_label))
        self.assertTrue(str(presets["nightmare"].guardrail_warning))
        self.assertIn("story", list(presets["easy"].legacy_labels))
        self.assertIn("hardcore", list(presets["hard"].legacy_labels))


if __name__ == "__main__":
    unittest.main()
