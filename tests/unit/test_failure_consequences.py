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


class FailureConsequencesTests(unittest.TestCase):
    def _build_service(self, charisma: int = 8):
        event_bus = EventBus()
        world_repo = InMemoryWorldRepository(seed=9)
        character = Character(id=77, name="Vale", location_id=1, hp_max=20, hp_current=20)
        character.attributes["charisma"] = charisma
        character.attributes["wisdom"] = 8
        character.attributes["strength"] = 8

        character_repo = InMemoryCharacterRepository({character.id: character})
        entity_repo = InMemoryEntityRepository([])
        location_repo = InMemoryLocationRepository({1: Location(id=1, name="Town")})
        progression = WorldProgression(world_repo, entity_repo, event_bus)

        register_quest_handlers(event_bus=event_bus, world_repo=world_repo, character_repo=character_repo)

        service = GameService(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
            progression=progression,
        )
        return service, world_repo, character_repo, character.id

    def test_social_failure_creates_consequence_visible_in_town_view(self):
        service, _world_repo, _char_repo, character_id = self._build_service()

        # Keep repeating to ensure at least one failure under deterministic rolls.
        for _ in range(3):
            service.submit_social_approach_intent(character_id, "captain_ren", "Intimidate")

        town = service.get_town_view_intent(character_id)
        self.assertTrue(any("rebuffs" in line.lower() for line in town.consequences))

    def test_retreat_penalty_reduces_hp_and_raises_threat(self):
        service, world_repo, char_repo, character_id = self._build_service()
        world_before = world_repo.load_default()
        threat_before = world_before.threat_level

        result = service.apply_retreat_consequence_intent(character_id)
        updated = char_repo.get(character_id)
        world_after = world_repo.load_default()

        self.assertIn("Retreat has consequences", " ".join(result.messages))
        self.assertLess(updated.hp_current, 20)
        self.assertGreaterEqual(world_after.threat_level, threat_before + 1)

    def test_quest_expiry_marks_failed(self):
        service, world_repo, _char_repo, character_id = self._build_service()
        service.advance_world(ticks=1)
        service.accept_quest_intent(character_id, "first_hunt")

        # Advance beyond default expiry window (accepted_turn + 5).
        service.advance_world(ticks=6)
        board = service.get_quest_board_intent(character_id)
        first_hunt = next(q for q in board.quests if q.quest_id == "first_hunt")
        self.assertEqual("failed", first_hunt.status)

        world = world_repo.load_default()
        rows = world.flags.get("consequences", [])
        self.assertTrue(any(row.get("kind") == "quest_expired" for row in rows if isinstance(row, dict)))

    def test_non_combat_social_success_can_ready_active_quest(self):
        service, _world_repo, _char_repo, character_id = self._build_service(charisma=18)
        service.advance_world(ticks=1)
        service.accept_quest_intent(character_id, "first_hunt")

        # Broker path for non-combat progression.
        for _ in range(5):
            service.submit_social_approach_intent(character_id, "broker_silas", "Friendly")
            state = next(q for q in service.get_quest_board_intent(character_id).quests if q.quest_id == "first_hunt")
            if state.status == "ready_to_turn_in":
                break

        state = next(q for q in service.get_quest_board_intent(character_id).quests if q.quest_id == "first_hunt")
        self.assertEqual("ready_to_turn_in", state.status)

    def test_defeat_consequence_applies_recovery_and_relocation(self):
        event_bus = EventBus()
        world_repo = InMemoryWorldRepository(seed=9)
        character = Character(id=78, name="Vale", location_id=2, hp_max=20, hp_current=1, money=40, alive=False)

        character_repo = InMemoryCharacterRepository({character.id: character})
        entity_repo = InMemoryEntityRepository([])
        location_repo = InMemoryLocationRepository(
            {
                1: Location(id=1, name="Starting Town", biome="village"),
                2: Location(id=2, name="Ashen Wilds", biome="wilderness"),
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

        result = service.apply_defeat_consequence_intent(character.id)
        updated = character_repo.get(character.id)

        self.assertIn("Defeat has consequences", " ".join(result.messages))
        self.assertEqual(10, updated.hp_current)
        self.assertTrue(updated.alive)
        self.assertEqual(30, updated.money)
        self.assertEqual(1, updated.location_id)
        recovery_note = service.get_recovery_status_intent(character.id)
        self.assertTrue(recovery_note and "Recovery:" in recovery_note)


if __name__ == "__main__":
    unittest.main()
