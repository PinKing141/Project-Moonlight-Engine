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


class TravelFlavourInjectionTests(unittest.TestCase):
    def test_travel_preview_includes_culture_hint_when_available(self) -> None:
        event_bus = EventBus()
        world_repo = InMemoryWorldRepository(seed=11)
        character = Character(id=51, name="Iris", location_id=1)
        character_repo = InMemoryCharacterRepository({character.id: character})
        entity_repo = InMemoryEntityRepository([])
        location_repo = InMemoryLocationRepository(
            {
                1: Location(id=1, name="Town", biome="wilderness", recommended_level=1),
                2: Location(
                    id=2,
                    name="Karond",
                    biome="forest",
                    recommended_level=2,
                    hazard_profile=HazardProfile(
                        key="frontier",
                        severity=2,
                        environmental_flags=["culture_raw:Lothian (Dark Elfish)"],
                    ),
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

        destinations = service.get_travel_destinations_intent(character.id)
        self.assertTrue(destinations)
        self.assertIn("Culture Lothian (Dark Elfish)", destinations[0].preview)


if __name__ == "__main__":
    unittest.main()
