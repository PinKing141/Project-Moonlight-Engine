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


class FactionDiplomacyLayerTests(unittest.TestCase):
    def _build_service(self):
        event_bus = EventBus()
        world_repo = InMemoryWorldRepository(seed=53)
        character = Character(id=702, name="Rook", location_id=1)
        assert character.id is not None
        character_repo = InMemoryCharacterRepository({int(character.id): character})
        entity_repo = InMemoryEntityRepository([])
        location_repo = InMemoryLocationRepository(
            {
                1: Location(id=1, name="Town", biome="village", factions=["wardens"]),
                2: Location(id=2, name="Frontier Pass", biome="wilderness", factions=["wardens", "wild"]),
            }
        )
        progression = WorldProgression(world_repo, entity_repo, event_bus)
        faction_repo = InMemoryFactionRepository()
        service = GameService(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
            progression=progression,
            faction_repo=faction_repo,
        )
        return service, int(character.id), world_repo

    def _set_war_state(self, world_repo: InMemoryWorldRepository) -> None:
        world = world_repo.load_default()
        assert world is not None
        world.flags.setdefault("narrative", {})
        world.flags["narrative"]["faction_diplomacy"] = {
            "last_turn": int(world.current_turn),
            "factions": ["wardens", "wild", "undead"],
            "relations": {"wardens|wild": -72, "undead|wardens": -24, "undead|wild": -8},
            "active_wars": ["wardens|wild"],
            "active_alliances": [],
            "border_pressure": {"wardens": 6, "wild": 6},
        }
        world.flags["narrative"]["relationship_graph"] = {
            "faction_edges": {
                "wardens|wild": -72,
                "undead|wardens": -24,
                "undead|wild": -8,
            },
            "npc_faction_affinity": {},
            "history": [],
        }
        world_repo.save(world)

    def test_travel_destinations_show_border_conflict_route_note(self):
        service, character_id, world_repo = self._build_service()
        self._set_war_state(world_repo)

        destinations = service.get_travel_destinations_intent(character_id)
        frontier = next(row for row in destinations if row.location_id == 2)

        self.assertIn("Border clashes", frontier.route_note)

    def test_rumour_board_includes_diplomacy_war_rumour(self):
        service, character_id, world_repo = self._build_service()
        self._set_war_state(world_repo)

        board = service.get_rumour_board_intent(character_id)

        self.assertTrue(any(item.rumour_id.startswith("diplomacy:war:") for item in board.items))

    def test_travel_quest_urgency_includes_warfront_pressure(self):
        service, character_id, world_repo = self._build_service()
        self._set_war_state(world_repo)

        world = world_repo.load_default()
        assert world is not None
        world.flags.setdefault("quests", {})
        world.flags["quests"]["courier_run"] = {
            "objective_kind": "travel_to",
            "objective_target_location_id": 2,
            "progress": 0,
            "target": 1,
            "status": "active",
            "reward_xp": 15,
            "reward_money": 8,
        }
        world_repo.save(world)

        board = service.get_quest_board_intent(character_id)
        courier = next(row for row in board.quests if row.quest_id == "courier_run")

        self.assertIn("Warfront pressure", courier.urgency_label)


if __name__ == "__main__":
    unittest.main()
