import sys
from pathlib import Path
import unittest
from dataclasses import replace

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
        self.assertTrue(any(activity_id == "brew_antitoxin" for activity_id, _label in options))
        self.assertTrue(any(activity_id == "forge_travel_kit" for activity_id, _label in options))

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

    def test_submit_downtime_crafting_outcome_is_deterministic_for_same_seed(self) -> None:
        service_a, repo_a, world_repo_a, _faction_repo_a, character_id_a = self._build_service(money=20)
        service_b, repo_b, world_repo_b, _faction_repo_b, character_id_b = self._build_service(money=20)

        result_a = service_a.submit_downtime_intent(character_id_a, "craft_whetstone")
        result_b = service_b.submit_downtime_intent(character_id_b, "craft_whetstone")

        craft_line_a = next((line for line in result_a.messages if str(line).startswith("Craft result:")), "")
        craft_line_b = next((line for line in result_b.messages if str(line).startswith("Craft result:")), "")
        self.assertTrue(craft_line_a)
        self.assertEqual(craft_line_a, craft_line_b)

        world_a = world_repo_a.load_default()
        world_b = world_repo_b.load_default()
        self.assertEqual(
            dict((world_a.flags or {}).get("crafting_v1", {})),
            dict((world_b.flags or {}).get("crafting_v1", {})),
        )

        crafter_a = repo_a.get(character_id_a)
        crafter_b = repo_b.get(character_id_b)
        self.assertEqual(list(crafter_a.inventory or []), list(crafter_b.inventory or []))


    def test_submit_downtime_uses_activity_family_for_crafting_resolution(self) -> None:
        service, _character_repo, _world_repo, _faction_repo, character_id = self._build_service(money=20)

        activities = list(service.downtime_service.list_activities())
        herbal = next(row for row in activities if row.id == "craft_healing_herbs")
        custom = replace(herbal, id="brew_field_remedy", title="Brew Field Remedy", activity_family="crafting")
        service.downtime_service._ACTIVITIES = tuple([custom, *activities])

        result = service.submit_downtime_intent(character_id, "brew_field_remedy")

        self.assertTrue(any(str(line).startswith("Craft result:") for line in result.messages))

    def test_submit_downtime_crafting_persists_crafting_v1_recipe_and_stockpile(self) -> None:
        service, _character_repo, world_repo, _faction_repo, character_id = self._build_service(money=20)

        service.submit_downtime_intent(character_id, "craft_healing_herbs")

        world = world_repo.load_default()
        crafting = dict((world.flags or {}).get("crafting_v1", {}))
        self.assertTrue(bool(crafting.get("active", False)))
        known = list(crafting.get("known_recipes", []) or [])
        self.assertIn("field_remedy", known)
        stockpile = dict(crafting.get("stockpile", {}))
        self.assertGreaterEqual(int(stockpile.get("healing_herbs", 0) or 0), 1)

    def test_submit_downtime_brew_activity_routes_through_crafting_pipeline(self) -> None:
        service, _character_repo, world_repo, _faction_repo, character_id = self._build_service(money=20)

        result = service.submit_downtime_intent(character_id, "brew_antitoxin")

        self.assertTrue(any(str(line).startswith("Craft result:") for line in result.messages))
        crafting = dict((world_repo.load_default().flags or {}).get("crafting_v1", {}))
        self.assertIn("counteragent_mix", list(crafting.get("known_recipes", []) or []))


if __name__ == "__main__":
    unittest.main()
