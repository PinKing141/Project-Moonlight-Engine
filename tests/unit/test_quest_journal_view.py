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


class QuestJournalViewTests(unittest.TestCase):
    def _build_service(self):
        event_bus = EventBus()
        world_repo = InMemoryWorldRepository(seed=13)
        character = Character(id=501, name="Kest", location_id=1)
        character.money = 30
        character_repo = InMemoryCharacterRepository({character.id: character})
        entity_repo = InMemoryEntityRepository([])
        location_repo = InMemoryLocationRepository(
            {
                1: Location(id=1, name="Town", biome="village"),
                2: Location(id=2, name="Ashen Wilds", biome="wilderness"),
            }
        )
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
        )
        return service, world_repo, character.id

    def test_groups_quests_by_status_and_sorts_titles(self):
        service, world_repo, character_id = self._build_service()
        world = world_repo.load_default()
        world.flags.setdefault("quests", {})
        world.flags["quests"] = {
            "quest_c": {
                "status": "active",
                "progress": 1,
                "target": 3,
                "reward_xp": 30,
                "reward_money": 7,
            },
            "quest_a": {
                "status": "active",
                "progress": 0,
                "target": 2,
                "reward_xp": 10,
                "reward_money": 5,
            },
            "quest_turnin": {
                "status": "ready_to_turn_in",
                "progress": 2,
                "target": 2,
                "reward_xp": 40,
                "reward_money": 12,
            },
            "quest_done": {
                "status": "completed",
                "progress": 1,
                "target": 1,
                "reward_xp": 20,
                "reward_money": 9,
            },
            "quest_fail": {
                "status": "failed",
                "progress": 0,
                "target": 1,
                "reward_xp": 0,
                "reward_money": 0,
            },
        }
        world_repo.save(world)

        journal = service.get_quest_journal_intent(character_id)

        section_titles = [section.title for section in journal.sections]
        self.assertEqual(["Ready to Turn In", "Active", "Completed", "Failed"], section_titles)

        active = next(section for section in journal.sections if section.title == "Active")
        active_titles = [quest.title for quest in active.quests]
        self.assertEqual(sorted(active_titles, key=str.lower), active_titles)

    def test_quest_board_exposes_empty_state_guidance(self):
        service, _world_repo, character_id = self._build_service()

        board = service.get_quest_board_intent(character_id)

        self.assertEqual([], board.quests)
        self.assertTrue(board.empty_state_hint)
        self.assertIn("Explore nearby zones", board.empty_state_hint)
        self.assertIn("advance a day", board.empty_state_hint)

    def test_quest_journal_exposes_empty_state_guidance(self):
        service, _world_repo, character_id = self._build_service()

        journal = service.get_quest_journal_intent(character_id)

        self.assertEqual([], journal.sections)
        self.assertTrue(journal.empty_state_hint)
        self.assertIn("quest board", journal.empty_state_hint.lower())
        self.assertIn("monitor progress", journal.empty_state_hint.lower())

    def test_quest_board_includes_objective_summary_and_urgency_for_active_contract(self):
        service, _world_repo, character_id = self._build_service()

        service.advance_world(ticks=1)
        accepted = service.accept_quest_intent(character_id, "first_hunt")
        self.assertIn("Accepted quest", " ".join(accepted.messages))

        board = service.get_quest_board_intent(character_id)
        first_hunt = next(quest for quest in board.quests if quest.quest_id == "first_hunt")

        self.assertEqual("active", first_hunt.status)
        self.assertIn("Defeat hostiles", first_hunt.objective_summary)
        self.assertIn("Due in", first_hunt.urgency_label)

    def test_quest_board_renders_travel_objective_summary_for_supply_drop(self):
        service, _world_repo, character_id = self._build_service()

        service.advance_world(ticks=1)

        board = service.get_quest_board_intent(character_id)
        supply_drop = next(quest for quest in board.quests if quest.quest_id == "supply_drop")

        self.assertIn("Travel legs", supply_drop.objective_summary)
        self.assertEqual("", supply_drop.urgency_label)

    def test_supply_drop_progress_uses_final_travel_days_with_prep(self):
        service, _world_repo, character_id = self._build_service()

        service.advance_world(ticks=1)
        accepted = service.accept_quest_intent(character_id, "supply_drop")
        self.assertIn("Accepted quest", " ".join(accepted.messages))

        bought = service.purchase_travel_prep_intent(character_id, "caravan_contract")
        self.assertIn("Travel prep secured", " ".join(bought.messages))

        service.travel_intent(character_id, destination_id=2, travel_mode="road")
        board = service.get_quest_board_intent(character_id)
        supply_drop = next(quest for quest in board.quests if quest.quest_id == "supply_drop")

        self.assertEqual("ready_to_turn_in", supply_drop.status)
        self.assertEqual(supply_drop.target, supply_drop.progress)


if __name__ == "__main__":
    unittest.main()
