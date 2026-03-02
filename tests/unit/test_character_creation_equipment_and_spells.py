import random
import sys
from pathlib import Path
from typing import Any, cast
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.character_creation_service import CharacterCreationService
from rpg.domain.models.character_class import CharacterClass
from rpg.domain.models.character_options import Race, Subrace
from rpg.domain.models.location import Location


class _FakeCharacterRepo:
    def __init__(self) -> None:
        self.created = []

    def list_all(self):
        return []

    def create(self, character, location_id: int):
        character.id = 999
        character.location_id = location_id
        self.created.append(character)
        return character


class _FakeLocationRepo:
    def get_starting_location(self):
        return Location(id=1, name="Town", base_level=1)


class _FakeClassRepo:
    def __init__(self) -> None:
        self._classes = [
            CharacterClass(
                id=1,
                name="Fighter",
                slug="fighter",
                hit_die="d10",
                primary_ability="strength",
                base_attributes={"STR": 15, "CON": 14, "DEX": 12},
            ),
            CharacterClass(
                id=2,
                name="Wizard",
                slug="wizard",
                hit_die="d6",
                primary_ability="intelligence",
                base_attributes={"INT": 15, "DEX": 14, "CON": 13},
            ),
        ]

    def list_playable(self):
        return list(self._classes)


class CharacterCreationEquipmentAndSpellsTests(unittest.TestCase):
    def _build_service(self) -> CharacterCreationService:
        return CharacterCreationService(
            character_repo=cast(Any, _FakeCharacterRepo()),
            class_repo=cast(Any, _FakeClassRepo()),
            location_repo=cast(Any, _FakeLocationRepo()),
            open5e_client=None,
        )

    def test_resolve_starting_equipment_starting_gold_mode(self) -> None:
        service = self._build_service()
        payload = service.resolve_starting_equipment_choice(
            "fighter",
            "starting_gold",
            rng=random.Random(7),
        )
        gold_bonus = int(cast(int, payload.get("gold_bonus", 0) or 0))
        items = list(cast(list[str], payload.get("items", []) or []))

        self.assertEqual("starting_gold", payload.get("mode"))
        self.assertGreater(gold_bonus, 0)
        self.assertEqual([], items)

    def test_create_character_applies_equipment_override_and_gold_bonus(self) -> None:
        service = self._build_service()
        race = Race(name="Human", bonuses={"STR": 1}, speed=30, traits=[])

        created = service.create_character(
            name="Arin",
            class_index=0,
            race=race,
            starting_equipment_override=["Leather Armor", "Longbow", "Arrows x20"],
            starting_gold_bonus=35,
        )

        self.assertEqual(["Leather Armor", "Longbow", "Arrows x20"], created.inventory)
        self.assertGreaterEqual(int(created.money), 35)

    def test_list_starting_spell_options_for_wizard(self) -> None:
        service = self._build_service()
        profile = service.list_starting_spell_options("wizard")
        required_cantrips = int(cast(int, profile.get("required_cantrips", 0) or 0))
        required_spells = int(cast(int, profile.get("required_spells", 0) or 0))
        cantrip_pool = list(cast(list[str], profile.get("cantrip_pool", []) or []))
        spell_pool = list(cast(list[str], profile.get("spell_pool", []) or []))

        self.assertTrue(bool(profile.get("spellcasting", False)))
        self.assertGreater(required_cantrips, 0)
        self.assertGreater(required_spells, 0)
        self.assertTrue(cantrip_pool)
        self.assertTrue(spell_pool)

    def test_create_character_applies_spell_choices_with_racial_grant(self) -> None:
        service = self._build_service()
        race = Race(name="Elf", bonuses={"DEX": 2}, speed=30, traits=["Keen Senses"])
        subrace = Subrace(name="High Elf", parent_race="Elf", bonuses={"INT": 1}, traits=["Cantrip Aptitude"])
        profile = service.list_starting_spell_options("wizard", race_name=race.name, subrace_name=subrace.name)
        cantrip_pool = list(cast(list[str], profile.get("cantrip_pool", []) or []))
        spell_pool = list(cast(list[str], profile.get("spell_pool", []) or []))
        required_cantrips = int(cast(int, profile.get("required_cantrips", 1) or 1))
        required_spells = int(cast(int, profile.get("required_spells", 1) or 1))

        self.assertTrue(cantrip_pool)
        self.assertTrue(spell_pool)

        selected_cantrips = cantrip_pool[: max(1, required_cantrips)]
        selected_spells = spell_pool[: max(1, required_spells)]

        created = service.create_character(
            name="Selene",
            class_index=1,
            race=race,
            subrace=subrace,
            selected_cantrips=selected_cantrips,
            selected_known_spells=selected_spells,
        )

        self.assertGreaterEqual(len(created.cantrips), max(0, required_cantrips))
        self.assertGreaterEqual(len(created.known_spells), max(0, required_spells))

    def test_tiefling_racial_cantrip_is_granted(self) -> None:
        service = self._build_service()
        tiefling = Race(name="Tiefling", bonuses={"CHA": 2}, speed=30, traits=["Darkvision"])
        profile = service.list_starting_spell_options("fighter", race_name=tiefling.name)
        granted = list(cast(list[str], profile.get("granted_cantrips", []) or []))

        self.assertTrue(bool(profile.get("spellcasting", False)))
        self.assertIn("Thaumaturgy", granted)

        created = service.create_character(
            name="Keth",
            class_index=0,
            race=tiefling,
            selected_cantrips=[],
            selected_known_spells=[],
        )

        self.assertIn("Thaumaturgy", list(created.cantrips or []))

    def test_background_extra_choices_profile_is_available(self) -> None:
        service = self._build_service()
        profile = service.list_background_choice_options("Night Runner")
        tool_choices = int(cast(int, profile.get("tool_choices", 0) or 0))
        language_choices = int(cast(int, profile.get("language_choices", 0) or 0))
        tool_pool = list(cast(list[str], profile.get("tool_pool", []) or []))
        language_pool = list(cast(list[str], profile.get("language_pool", []) or []))

        self.assertEqual(1, tool_choices)
        self.assertEqual(1, language_choices)
        self.assertTrue(tool_pool)
        self.assertTrue(language_pool)

    def test_roll_background_personality_returns_expected_keys(self) -> None:
        service = self._build_service()
        payload = service.roll_background_personality("Lorekeeper", rng=random.Random(3))

        self.assertIn("trait", payload)
        self.assertIn("ideal", payload)
        self.assertIn("bond", payload)
        self.assertIn("flaw", payload)
        self.assertTrue(str(payload["trait"]).strip())

    def test_fighter_fighting_style_defence_applies_ac_bonus(self) -> None:
        service = self._build_service()
        race = Race(name="Human", bonuses={"STR": 1}, speed=30, traits=[])
        created = service.create_character(
            name="Dane",
            class_index=0,
            race=race,
            class_feature_choices={"fighting_style": "Defence"},
        )

        self.assertEqual("Defence", str(created.flags.get("fighting_style", "") or ""))
        self.assertGreaterEqual(int(created.armour_class), 11)

    def test_rogue_expertise_choices_are_persisted(self) -> None:
        class RogueClassRepo(_FakeClassRepo):
            def __init__(self) -> None:
                self._classes = [
                    CharacterClass(
                        id=3,
                        name="Rogue",
                        slug="rogue",
                        hit_die="d8",
                        primary_ability="dexterity",
                        base_attributes={"DEX": 15, "INT": 13, "CHA": 12},
                    )
                ]

        service = CharacterCreationService(
            character_repo=cast(Any, _FakeCharacterRepo()),
            class_repo=cast(Any, RogueClassRepo()),
            location_repo=cast(Any, _FakeLocationRepo()),
            open5e_client=None,
        )
        race = Race(name="Human", bonuses={"DEX": 1}, speed=30, traits=[])
        created = service.create_character(
            name="Shade",
            class_index=0,
            race=race,
            class_feature_choices={"expertise_skills": ["Stealth", "Perception"]},
        )

        expertise = list(created.flags.get("expertise_skills", []) or [])
        self.assertIn("Stealth", expertise)
        self.assertIn("Perception", expertise)

    def test_variant_human_feat_applies_tough_bonus(self) -> None:
        service = self._build_service()
        race = Race(name="Human", bonuses={"STR": 1}, speed=30, traits=[])
        subrace = Subrace(name="Variant Human", parent_race="Human", bonuses={"DEX": 1}, traits=["Bonus Feat"])
        created = service.create_character(
            name="Tara",
            class_index=0,
            race=race,
            subrace=subrace,
            selected_feat_slug="tough",
        )

        self.assertEqual("tough", str(created.flags.get("level1_feat", "") or ""))
        self.assertGreaterEqual(int(created.hp_max), 14)


if __name__ == "__main__":
    unittest.main()
