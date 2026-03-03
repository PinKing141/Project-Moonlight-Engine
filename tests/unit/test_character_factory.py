import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.domain.models.character_class import CharacterClass
from rpg.domain.models.character import CharacterAlignment
from rpg.domain.models.character_options import Background, DifficultyPreset, Race
from rpg.domain.services.character_factory import create_new_character


class CharacterFactoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.wizard = CharacterClass(
            id=3, name="Wizard", slug="wizard", hit_die="d6", primary_ability="intelligence"
        )

    def test_applies_racial_bonuses_and_difficulty_to_character(self) -> None:
        race = Race(name="High Elf", bonuses={"DEX": 2, "INT": 1}, speed=35, traits=["Keen Senses"])
        difficulty = DifficultyPreset(slug="story", name="Story", hp_multiplier=1.5, incoming_damage_multiplier=0.5)

        character = create_new_character(
            name="Lyra",
            cls=self.wizard,
            ability_scores={"str": 8, "DEX": 14, "int": 15},
            race=race,
            difficulty=difficulty,
        )

        self.assertEqual("wizard", character.class_name)
        self.assertEqual(12, character.hp_max, "HP should reflect hit die and difficulty multiplier")
        self.assertGreater(character.attributes["dexterity"], character.base_attributes["dexterity"])
        self.assertIn("Keen Senses", character.race_traits)
        self.assertEqual("story", character.difficulty)
        self.assertEqual(0.5, character.incoming_damage_multiplier)
        self.assertGreaterEqual(character.spell_slots_max, 1, "Casters should start with spell slots")
        self.assertTrue(character.cantrips, "Casters should start with at least one cantrip")

    def test_includes_background_flags_and_starting_equipment(self) -> None:
        background = Background(
            name="Soldier", proficiencies=["Athletics"], feature="Military Rank", faction="alliance", starting_money=25
        )

        character = create_new_character(
            name="Tamsin",
            cls=self.wizard,
            ability_scores={"STR": 10, "DEX": 12, "INT": 14},
            background=background,
            starting_equipment=["Spellbook", "Quarterstaff"],
        )

        self.assertEqual("Soldier", character.background)
        self.assertIn("Military Rank", character.background_features)
        self.assertEqual(25, character.money)
        self.assertIn("alliance", character.flags.get("faction_affinity", ""))
        self.assertIn("Spellbook", character.inventory)
        self.assertEqual({"strength": 10, "dexterity": 12, "intelligence": 14}, character.base_attributes)

    def test_defaults_alignment_when_not_provided(self) -> None:
        character = create_new_character(
            name="Mira",
            cls=self.wizard,
            ability_scores={"STR": 10, "DEX": 12, "INT": 14},
        )

        self.assertEqual(CharacterAlignment.TRUE_NEUTRAL.value, character.alignment)

    def test_persists_hardcore_toggle_defaults_and_opt_in_overrides(self) -> None:
        character = create_new_character(
            name="Rhea",
            cls=self.wizard,
            ability_scores={"STR": 10, "DEX": 12, "INT": 14},
            hardcore_toggles={"max_monster_hp": True},
        )

        flags = character.flags if isinstance(character.flags, dict) else {}
        self.assertEqual("hardcore_toggles_v1", flags.get("hardcore_toggles_version"))
        toggles = flags.get("hardcore_toggles", {}) if isinstance(flags.get("hardcore_toggles", {}), dict) else {}
        self.assertTrue(bool(toggles.get("max_monster_hp")))
        self.assertFalse(bool(toggles.get("deadlier_death_saves")))
        self.assertFalse(bool(toggles.get("rest_lock_on_failed_saves")))


if __name__ == "__main__":
    unittest.main()
