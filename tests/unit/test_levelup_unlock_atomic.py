import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.event_bus import EventBus
from rpg.application.services.game_service import GameService
from rpg.application.services.world_progression import WorldProgression
from rpg.domain.models.character import Character
from rpg.domain.models.location import Location
from rpg.infrastructure.db.inmemory.repos import (
    InMemoryCharacterRepository,
    InMemoryEntityRepository,
    InMemoryLocationRepository,
    InMemoryWorldRepository,
)


class LevelUpUnlockAtomicTests(unittest.TestCase):
    def test_submit_level_up_choice_persists_unlock_operation(self) -> None:
        event_bus = EventBus()
        world_repo = InMemoryWorldRepository(seed=9)
        character = Character(id=13, name="Rune", level=1, xp=30, location_id=1)
        character_repo = InMemoryCharacterRepository({character.id: character})
        entity_repo = InMemoryEntityRepository([])
        location_repo = InMemoryLocationRepository({1: Location(id=1, name="Town")})
        progression = WorldProgression(world_repo, entity_repo, event_bus)

        service = GameService(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
            progression=progression,
        )

        result = service.submit_level_up_choice_intent(character_id=13, growth_choice="feat")

        self.assertTrue(any("Level up!" in line for line in result.messages))
        rows = character_repo.list_progression_unlocks(13)
        self.assertEqual(1, len(rows))
        self.assertEqual("growth_choice", rows[0]["unlock_kind"])
        self.assertEqual("level_2_feat", rows[0]["unlock_key"])


if __name__ == "__main__":
    unittest.main()
