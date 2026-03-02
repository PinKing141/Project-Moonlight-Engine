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
from rpg.infrastructure.inmemory.inmemory_faction_repo import InMemoryFactionRepository


class DowntimeFlowTests(unittest.TestCase):
    def _build_service(self, *, money: int = 20):
        event_bus = EventBus()
        world_repo = InMemoryWorldRepository(seed=77)
        character = Character(id=801, name="Lyra", location_id=1, money=money)
        character_repo = InMemoryCharacterRepository({character.id: character})
        entity_repo = InMemoryEntityRepository([])
        location_repo = InMemoryLocationRepository({1: Location(id=1, name="Town")})
        faction_repo = InMemoryFactionRepository()
        progression = WorldProgression(world_repo, entity_repo, event_bus)

        service = GameService(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
            progression=progression,
            faction_repo=faction_repo,
        )
        return service, character_repo, world_repo, faction_repo, character.id

    def test_get_downtime_options_returns_entries(self) -> None:
        service, _char_repo, _world_repo, _faction_repo, character_id = self._build_service(money=12)
        options = service.get_downtime_options_intent(character_id)
        self.assertTrue(options)
        self.assertTrue(any(activity_id == "craft_healing_herbs" for activity_id, _label in options))

    def test_submit_downtime_crafting_spends_gold_adds_item_and_advances_world(self) -> None:
        service, character_repo, world_repo, _faction_repo, character_id = self._build_service(money=20)
        world_before = world_repo.load_default()
        start_turn = int(getattr(world_before, "current_turn", 0) or 0)

        result = service.submit_downtime_intent(character_id, "craft_healing_herbs")
        updated = character_repo.get(character_id)
        world_after = world_repo.load_default()

        self.assertIn("Downtime complete", " ".join(result.messages))
        self.assertIn("Healing Herbs", updated.inventory)
        self.assertEqual(16, int(updated.money))
        self.assertEqual(start_turn + 1, int(getattr(world_after, "current_turn", 0) or 0))

    def test_submit_downtime_updates_faction_reputation(self) -> None:
        service, _character_repo, _world_repo, faction_repo, character_id = self._build_service(money=20)
        wardens = faction_repo.get("wardens")
        before = int(wardens.reputation.get(f"character:{character_id}", 0) or 0)

        result = service.submit_downtime_intent(character_id, "craft_healing_herbs")
        wardens_after = faction_repo.get("wardens")
        after = int(wardens_after.reputation.get(f"character:{character_id}", 0) or 0)

        self.assertEqual(before + 1, after)
        self.assertTrue(any("reputation" in str(line).lower() for line in result.messages))

    def test_submit_downtime_rejects_when_insufficient_gold(self) -> None:
        service, _character_repo, _world_repo, _faction_repo, character_id = self._build_service(money=1)
        result = service.submit_downtime_intent(character_id, "craft_healing_herbs")
        self.assertIn("requires", " ".join(result.messages).lower())


if __name__ == "__main__":
    unittest.main()
