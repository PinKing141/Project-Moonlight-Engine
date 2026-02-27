import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.event_bus import EventBus
from rpg.application.services.game_service import GameService
from rpg.application.services.world_progression import WorldProgression
from rpg.domain.models.character import Character
from rpg.domain.models.location import HazardProfile, Location
from rpg.infrastructure.db.inmemory.repos import (
    InMemoryCharacterRepository,
    InMemoryEntityRepository,
    InMemoryLocationRepository,
    InMemoryWorldRepository,
)


class TravelFogOfWarTests(unittest.TestCase):
    def _build_service(self):
        event_bus = EventBus()
        world_repo = InMemoryWorldRepository(seed=23)
        character = Character(id=701, name="Vale", location_id=1)
        character_repo = InMemoryCharacterRepository({character.id: character})
        entity_repo = InMemoryEntityRepository([])
        location_repo = InMemoryLocationRepository(
            {
                1: Location(id=1, name="Starting Town", biome="village", x=0.0, y=0.0),
                2: Location(
                    id=2,
                    name="Eldfair",
                    biome="forest",
                    x=60.0,
                    y=0.0,
                    factions=["wardens"],
                    hazard_profile=HazardProfile(key="contested", severity=3),
                ),
            }
        )
        progression = WorldProgression(world_repo, entity_repo, event_bus)
        service = GameService(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
            progression=progression,
        )
        return service, character_repo, character.id

    def test_destination_name_is_hidden_until_discovered(self):
        service, _character_repo, character_id = self._build_service()

        destinations = service.get_travel_destinations_intent(character_id)

        self.assertEqual(1, len(destinations))
        self.assertIn("Unknown Settlement", destinations[0].name)
        self.assertIn("East", destinations[0].name)
        self.assertIn("Risk", destinations[0].preview)
        self.assertNotIn("Low", destinations[0].preview)
        self.assertNotIn("Moderate", destinations[0].preview)
        self.assertNotIn("High", destinations[0].preview)

    def test_traveling_discovers_location_and_persists_flag(self):
        service, character_repo, character_id = self._build_service()

        result = service.travel_intent(character_id, destination_id=2)
        updated = character_repo.get(character_id)

        self.assertIn("travel to", " ".join(result.messages).lower())
        self.assertEqual(2, updated.location_id)
        discovered = updated.flags.get("discovered_locations", [])
        self.assertIn(2, discovered)
        discovered_factions = updated.flags.get("discovered_factions", [])
        self.assertIn("wardens", discovered_factions)


if __name__ == "__main__":
    unittest.main()
