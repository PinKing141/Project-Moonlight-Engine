import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.event_bus import EventBus
from rpg.application.services.game_service import GameService
from rpg.application.services.quest_service import register_quest_handlers
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


class EscalatingQuestsAndRumoursTests(unittest.TestCase):
    def _build_service(self):
        event_bus = EventBus()
        world_repo = InMemoryWorldRepository(seed=23)
        character = Character(id=611, name="Aerin", location_id=1)
        character_id = int(character.id or 0)
        character_repo = InMemoryCharacterRepository({character_id: character})
        entity_repo = InMemoryEntityRepository([])
        location_repo = InMemoryLocationRepository(
            {
                1: Location(id=1, name="Town", biome="village"),
                2: Location(id=2, name="North Wilds", biome="forest"),
            }
        )
        faction_repo = InMemoryFactionRepository()
        progression = WorldProgression(world_repo, entity_repo, event_bus)

        register_quest_handlers(
            event_bus=event_bus,
            world_repo=world_repo,
            character_repo=character_repo,
        )

        service = GameService(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
            progression=progression,
            faction_repo=faction_repo,
        )
        return service, world_repo, faction_repo, character_id

    def test_escalating_quest_advances_then_fails_with_faction_penalty(self):
        service, world_repo, faction_repo, character_id = self._build_service()

        service.advance_world(ticks=1)
        accepted = service.accept_quest_intent(character_id, "forest_path_clearance")
        self.assertIn("Accepted quest", " ".join(accepted.messages))

        service.advance_world(ticks=14)
        board = service.get_quest_board_intent(character_id)
        quest = next(row for row in board.quests if row.quest_id == "forest_path_clearance")

        self.assertEqual("active", quest.status)
        self.assertIn("fortified", quest.objective_summary.lower())
        self.assertIn("urgent", quest.urgency_label.lower())

        world = world_repo.load_default()
        assert world is not None
        consequences = list(world.flags.get("consequences", []))
        self.assertTrue(any(str(row.get("kind", "")) == "quest_escalated" for row in consequences if isinstance(row, dict)))

        wardens_before = faction_repo.get("wardens")
        assert wardens_before is not None
        standing_before = int(wardens_before.reputation.get(f"character:{character_id}", 0) or 0)
        service.advance_world(ticks=7)

        board_after = service.get_quest_board_intent(character_id)
        quest_after = next(row for row in board_after.quests if row.quest_id == "forest_path_clearance")
        self.assertEqual("failed", quest_after.status)

        wardens_after = faction_repo.get("wardens")
        assert wardens_after is not None
        standing_after = int(wardens_after.reputation.get(f"character:{character_id}", 0) or 0)
        self.assertEqual(standing_before - 3, standing_after)

    def test_rumour_projection_has_valid_until_and_expires(self):
        service, world_repo, _faction_repo, character_id = self._build_service()

        service.advance_world(ticks=1)
        board = service.get_rumour_board_intent(character_id)
        self.assertTrue(board.items)

        world = world_repo.load_default()
        assert world is not None
        projection = [row for row in list(world.flags.get("rumour_projection", [])) if isinstance(row, dict)]
        self.assertTrue(projection)
        first_created_turns = {int(row.get("created_turn", 0) or 0) for row in projection}
        self.assertIn(1, first_created_turns)
        self.assertTrue(all(int(row.get("valid_until", 0) or 0) >= 1 for row in projection))

        service.advance_world(ticks=5)
        service.get_rumour_board_intent(character_id)

        world_after = world_repo.load_default()
        assert world_after is not None
        projection_after = [row for row in list(world_after.flags.get("rumour_projection", [])) if isinstance(row, dict)]
        self.assertTrue(projection_after)
        self.assertFalse(any(int(row.get("created_turn", 0) or 0) == 1 for row in projection_after))


if __name__ == "__main__":
    unittest.main()
