import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.event_bus import EventBus
from rpg.application.services.faction_influence_service import FactionInfluenceService
from rpg.application.services.game_service import GameService
from rpg.application.services.world_progression import WorldProgression
from rpg.domain.events import MonsterSlain
from rpg.domain.models.character import Character
from rpg.domain.models.entity import Entity
from rpg.domain.models.location import Location
from rpg.domain.models.faction import Faction
from rpg.domain.repositories import EntityRepository, FactionRepository
from rpg.infrastructure.db.inmemory.repos import (
    InMemoryCharacterRepository,
    InMemoryEntityRepository,
    InMemoryLocationRepository,
    InMemoryWorldRepository,
)


class _StubEntityRepository(EntityRepository):
    def __init__(self, entities: dict[int, Entity]) -> None:
        self._entities = entities

    def get(self, entity_id: int):
        return self._entities.get(entity_id)

    def get_many(self, entity_ids: list[int]):
        return [self._entities[eid] for eid in entity_ids if eid in self._entities]

    def list_for_level(self, target_level: int, tolerance: int = 2):
        return []

    def list_by_location(self, location_id: int):
        return []


class _StubFactionRepository(FactionRepository):
    def __init__(self, factions: dict[str, Faction]) -> None:
        self._factions = factions

    def get(self, faction_id: str):
        return self._factions.get(faction_id)

    def list_all(self):
        return list(self._factions.values())

    def save(self, faction: Faction) -> None:
        self._factions[faction.id] = faction


class FactionInfluenceTests(unittest.TestCase):
    def test_monster_slain_updates_faction_reputation_and_influence(self) -> None:
        bus = EventBus()
        faction_repo = _StubFactionRepository(
            {"wild": Faction(id="wild", name="Wild Tribes", influence=3)}
        )
        entity_repo = _StubEntityRepository(
            {1: Entity(id=1, name="Goblin", level=1, faction_id="wild")}
        )

        service = FactionInfluenceService(faction_repo, entity_repo, bus)
        service.register_handlers()

        bus.publish(MonsterSlain(monster_id=1, location_id=1, by_character_id=7, turn=2))

        wild = faction_repo.get("wild")
        self.assertIsNotNone(wild)
        self.assertEqual(-2, wild.reputation.get("character:7"))
        self.assertEqual(2, wild.influence)

    def test_monster_without_faction_does_not_change_factions(self) -> None:
        bus = EventBus()
        faction_repo = _StubFactionRepository(
            {"wild": Faction(id="wild", name="Wild Tribes", influence=3)}
        )
        entity_repo = _StubEntityRepository(
            {1: Entity(id=1, name="Wolf", level=1, faction_id=None)}
        )

        service = FactionInfluenceService(faction_repo, entity_repo, bus)
        service.register_handlers()

        bus.publish(MonsterSlain(monster_id=1, location_id=1, by_character_id=9, turn=3))

        wild = faction_repo.get("wild")
        self.assertIsNotNone(wild)
        self.assertEqual({}, wild.reputation)
        self.assertEqual(3, wild.influence)


class FactionStandingsViewIntentTests(unittest.TestCase):
    def _build_service(self, faction_repo: FactionRepository | None):
        event_bus = EventBus()
        world_repo = InMemoryWorldRepository(seed=19)
        character = Character(id=88, name="Mira", location_id=1)
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
            faction_repo=faction_repo,
        )
        return service, character.id

    def test_view_intent_exposes_empty_state_hint_when_no_standings(self) -> None:
        class _EmptyFactionRepo(FactionRepository):
            def get(self, faction_id: str):
                return None

            def list_all(self):
                return []

            def save(self, faction: Faction) -> None:
                return None

        service, character_id = self._build_service(_EmptyFactionRepo())

        view = service.get_faction_standings_view_intent(character_id)

        self.assertEqual({}, view.standings)
        self.assertTrue(view.empty_state_hint)
        self.assertIn("No standings tracked yet", view.empty_state_hint)
        self.assertIn("reputation", view.empty_state_hint.lower())

    def test_view_intent_passes_through_standings_payload(self) -> None:
        faction_repo = _StubFactionRepository(
            {
                "wardens": Faction(id="wardens", name="Wardens", influence=3, reputation={"character:88": 4}),
                "wild": Faction(id="wild", name="Wild Tribes", influence=2, reputation={"character:88": -2}),
            }
        )
        service, character_id = self._build_service(faction_repo)

        view = service.get_faction_standings_view_intent(character_id)

        self.assertEqual({"wardens": 4, "wild": -2}, view.standings)
        self.assertTrue(view.empty_state_hint)


if __name__ == "__main__":
    unittest.main()
