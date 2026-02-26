import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rpg.application.services.event_bus import EventBus
from rpg.application.services.world_progression import WorldProgression
from rpg.domain.events import TickAdvanced
from rpg.domain.models.character import Character
from rpg.domain.models.entity import Entity
from rpg.domain.models.character_class import CharacterClass
from rpg.domain.models.location import Location
from rpg.domain.models.world import World
from rpg.infrastructure.db.inmemory.repos import (
    InMemoryCharacterRepository,
    InMemoryClassRepository,
    InMemoryEntityRepository,
    InMemoryLocationRepository,
    InMemoryWorldRepository,
)


class InMemoryEntityRepositoryTests(unittest.TestCase):
    def test_filters_by_level_and_location(self) -> None:
        entities = [
            Entity(id=1, name="Rat", level=1),
            Entity(id=2, name="Ogre", level=6),
            Entity(id=3, name="Wolf", level=2),
        ]
        repo = InMemoryEntityRepository(entities)
        repo.set_location_entities(location_id=10, entity_ids=[1, 3])

        level_matches = repo.list_for_level(target_level=5)
        self.assertEqual([entities[1]], level_matches)

        nearby = repo.list_by_location(location_id=10)
        self.assertEqual({1, 3}, {e.id for e in nearby})


class InMemoryCharacterRepositoryTests(unittest.TestCase):
    def test_find_by_location_returns_only_matching_characters(self) -> None:
        repo = InMemoryCharacterRepository(
            {
                1: Character(id=1, name="Hero", location_id=2),
                2: Character(id=2, name="Villager", location_id=3),
                3: Character(id=3, name="Scout", location_id=2),
            }
        )

        at_location = repo.find_by_location(location_id=2)
        self.assertEqual({1, 3}, {c.id for c in at_location})

    def test_create_assigns_id_and_location(self) -> None:
        repo = InMemoryCharacterRepository({})
        character = Character(id=None, name="Newcomer", location_id=0)

        created = repo.create(character, location_id=5)

        self.assertIsNotNone(created.id)
        self.assertEqual(5, created.location_id)
        self.assertIn(created.id, repo._characters)


class InMemoryWorldRepositoryTests(unittest.TestCase):
    def test_save_and_load_persists_world_state(self) -> None:
        repo = InMemoryWorldRepository(seed=9)
        world = repo.load_default()
        world.name = "Test World"
        world.advance_turns(3)

        repo.save(world)
        reloaded = repo.load_default()

        self.assertEqual("Test World", reloaded.name)
        self.assertEqual(3, reloaded.current_turn)


class WorldProgressionTests(unittest.TestCase):
    def test_tick_advances_world_and_publishes_event(self) -> None:
        world = World(id=1, name="Seeded", rng_seed=1)
        world_repo = InMemoryWorldRepository(seed=1)
        world_repo.save(world)
        entity_repo = InMemoryEntityRepository([])
        event_bus = EventBus()
        events: list[TickAdvanced] = []
        event_bus.subscribe(TickAdvanced, lambda e: events.append(e))

        progression = WorldProgression(world_repo, entity_repo, event_bus)
        progression.tick(world, ticks=2)

        self.assertEqual(2, world.current_turn)
        self.assertEqual(1, len(events))
        self.assertEqual(2, events[0].turn_after)


class InMemoryLocationRepositoryTests(unittest.TestCase):
    def test_get_starting_location_returns_lowest_id(self) -> None:
        repo = InMemoryLocationRepository(
            {
                2: Location(id=2, name="B", base_level=1),
                1: Location(id=1, name="A", base_level=1),
            }
        )

        starting = repo.get_starting_location()

        self.assertIsNotNone(starting)
        self.assertEqual(1, starting.id)


class InMemoryClassRepositoryTests(unittest.TestCase):
    def test_list_and_get_by_slug(self) -> None:
        fighter = CharacterClass(id=1, name="Fighter", slug="fighter", hit_die="d10")
        wizard = CharacterClass(id=2, name="Wizard", slug="wizard", hit_die="d6")
        repo = InMemoryClassRepository([wizard, fighter])

        listed = repo.list_playable()
        self.assertEqual([fighter, wizard], listed)

        fetched = repo.get_by_slug("wizard")
        self.assertEqual(wizard, fetched)


if __name__ == "__main__":
    unittest.main()
