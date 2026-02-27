import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.event_bus import EventBus
from rpg.application.services.game_service import GameService
from rpg.application.services.world_progression import WorldProgression
from rpg.domain.models.character import Character
from rpg.domain.models.location import Location
from rpg.domain.models.spell import Spell
from rpg.domain.repositories import SpellRepository
from rpg.infrastructure.db.inmemory.repos import (
    InMemoryCharacterRepository,
    InMemoryEntityRepository,
    InMemoryLocationRepository,
    InMemoryWorldRepository,
)


class _StubSpellRepository(SpellRepository):
    def __init__(self, spells: dict[str, Spell]) -> None:
        self._spells = dict(spells)

    def get_by_slug(self, slug: str):
        return self._spells.get(slug)

    def list_by_class(self, class_slug: str, max_level: int):
        _ = class_slug
        _ = max_level
        return []


class TowerSpellFilteringTests(unittest.TestCase):
    def _build_service(self, spell_repo: SpellRepository) -> tuple[GameService, Character]:
        event_bus = EventBus()
        world_repo = InMemoryWorldRepository(seed=31)
        character = Character(id=900, name="Ilya", class_name="wizard", location_id=1)
        character_id = character.id
        if character_id is None:
            raise AssertionError("Expected character.id to be assigned")
        character.known_spells = ["Fire Bolt", "Magic Missile", "Ray of Frost"]
        character.spell_slots_current = 2
        character_repo = InMemoryCharacterRepository({int(character_id): character})
        entity_repo = InMemoryEntityRepository([])
        location_repo = InMemoryLocationRepository({1: Location(id=1, name="Town")})
        progression = WorldProgression(world_repo, entity_repo, event_bus)
        service = GameService(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
            progression=progression,
            spell_repo=spell_repo,
        )
        return service, character

    def test_without_tower_allegiance_all_known_spells_are_visible(self) -> None:
        spell_repo = _StubSpellRepository(
            {
                "fire-bolt": Spell(slug="fire-bolt", name="Fire Bolt", level_int=0, school="Evocation", desc_text="Hurl fire."),
                "magic-missile": Spell(slug="magic-missile", name="Magic Missile", level_int=1, school="Evocation", desc_text="Bolts of force."),
                "ray-of-frost": Spell(slug="ray-of-frost", name="Ray of Frost", level_int=0, school="Evocation", desc_text="A beam of cold energy."),
            }
        )
        service, character = self._build_service(spell_repo)

        options = service.list_spell_options(character)
        slugs = [row.slug for row in options]

        self.assertEqual(["fire-bolt", "magic-missile", "ray-of-frost"], slugs)

    def test_crimson_tower_filters_to_fire_and_force_family_spells(self) -> None:
        spell_repo = _StubSpellRepository(
            {
                "fire-bolt": Spell(slug="fire-bolt", name="Fire Bolt", level_int=0, school="Evocation", desc_text="Hurl fire."),
                "magic-missile": Spell(slug="magic-missile", name="Magic Missile", level_int=1, school="Evocation", desc_text="Bolts of force."),
                "ray-of-frost": Spell(slug="ray-of-frost", name="Ray of Frost", level_int=0, school="Evocation", desc_text="A beam of cold energy."),
            }
        )
        service, character = self._build_service(spell_repo)
        character.flags = {"tower_allegiance": "tower_crimson"}

        options = service.list_spell_options(character)
        slugs = [row.slug for row in options]

        self.assertEqual(["fire-bolt", "magic-missile"], slugs)

    def test_alabaster_tower_allows_healing_spells_by_description(self) -> None:
        spell_repo = _StubSpellRepository(
            {
                "cure-wounds": Spell(
                    slug="cure-wounds",
                    name="Cure Wounds",
                    level_int=1,
                    school="Evocation",
                    desc_text="A creature regains hit points.",
                ),
                "ray-of-frost": Spell(
                    slug="ray-of-frost",
                    name="Ray of Frost",
                    level_int=0,
                    school="Evocation",
                    desc_text="A beam of cold energy.",
                ),
            }
        )
        service, character = self._build_service(spell_repo)
        character.known_spells = ["Cure Wounds", "Ray of Frost"]
        character.flags = {"tower_allegiance": "tower_alabaster"}

        options = service.list_spell_options(character)
        slugs = [row.slug for row in options]

        self.assertEqual(["cure-wounds"], slugs)


if __name__ == "__main__":
    unittest.main()
