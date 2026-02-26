import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.combat_service import CombatService, ability_mod
from rpg.domain.models.character import Character
from rpg.domain.models.stats import (
    AbilityScores,
    ability_modifier,
    ability_scores_from_mapping,
    derive_combat_stats,
)


class DomainStatsTests(unittest.TestCase):
    def test_ability_modifier_matches_standard_formula(self) -> None:
        self.assertEqual(-1, ability_modifier(9))
        self.assertEqual(0, ability_modifier(10))
        self.assertEqual(2, ability_modifier(15))
        self.assertEqual(0, ability_modifier(None))

    def test_ability_scores_mapping_supports_legacy_keys(self) -> None:
        scores = ability_scores_from_mapping(
            {
                "might": 14,
                "agility": 16,
                "constitution": 12,
                "wit": 13,
                "wisdom": 11,
                "spirit": 15,
            }
        )
        self.assertEqual(14, scores.strength)
        self.assertEqual(16, scores.dexterity)
        self.assertEqual(13, scores.intelligence)
        self.assertEqual(15, scores.charisma)
        self.assertEqual(3, scores.initiative)

    def test_derive_combat_stats_uses_dexterity_for_armour_class_and_initiative(self) -> None:
        scores = AbilityScores(dexterity=16)
        derived = derive_combat_stats(scores=scores, base_armour_class=10, armour_bonus=2, speed=30)
        self.assertEqual(15, derived.armour_class)
        self.assertEqual(3, derived.initiative)
        self.assertEqual(30, derived.speed)

    def test_combat_service_ability_mod_delegates_to_domain_rule(self) -> None:
        self.assertEqual(2, ability_mod(14))
        self.assertEqual(-2, ability_mod(7))

    def test_combat_service_derives_from_legacy_attributes(self) -> None:
        service = CombatService()
        character = Character(id=1, name="Scout", class_name="rogue")
        character.attributes.update({"might": 8, "agility": 16, "wit": 14, "spirit": 12})

        stats = service.derive_player_stats(character)

        self.assertEqual(3, stats["weapon_mod"])
        self.assertEqual(3, stats["damage_mod"])
        self.assertEqual(13, stats["ac"])


if __name__ == "__main__":
    unittest.main()
