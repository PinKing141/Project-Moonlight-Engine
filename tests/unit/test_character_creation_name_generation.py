import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.character_creation_service import CharacterCreationService
from rpg.domain.models.character import Character
from rpg.domain.models.character_class import CharacterClass
from rpg.domain.models.character_options import Race
from rpg.domain.models.location import Location


class _FakeCharacterRepo:
    def __init__(self) -> None:
        self.created = []

    def list_all(self):
        return []

    def create(self, character: Character, location_id: int):
        character.id = 1
        character.location_id = location_id
        self.created.append(character)
        return character


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
            )
        ]

    def list_playable(self):
        return list(self._classes)


class _FakeLocationRepo:
    def get_starting_location(self):
        return Location(id=1, name="Town", base_level=1)


class _FakeNameGenerator:
    def suggest_character_name(self, race_name, gender=None, context=None):
        if race_name and race_name.lower() == "elf":
            return "Aeris"
        return "Borin"


class CharacterCreationNameGenerationTests(unittest.TestCase):
    def test_blank_name_uses_generator(self) -> None:
        char_repo = _FakeCharacterRepo()
        service = CharacterCreationService(
            character_repo=char_repo,
            class_repo=_FakeClassRepo(),
            location_repo=_FakeLocationRepo(),
            open5e_client=None,
            name_generator=_FakeNameGenerator(),
        )

        character = service.create_character(
            name="   ",
            class_index=0,
            race=Race(name="Elf", bonuses={"DEX": 2}, speed=30, traits=[]),
        )

        self.assertEqual("Aeris", character.name)
        self.assertEqual(1, character.id)
        self.assertEqual("Aeris", char_repo.created[0].name)


if __name__ == "__main__":
    unittest.main()
