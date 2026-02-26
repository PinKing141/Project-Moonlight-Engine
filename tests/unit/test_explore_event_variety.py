import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.event_bus import EventBus
from rpg.application.services.game_service import GameService
from rpg.application.services.world_progression import WorldProgression
from rpg.application.dtos import EncounterPlan
from rpg.domain.models.character import Character
from rpg.domain.models.entity import Entity
from rpg.domain.models.location import Location
from rpg.infrastructure.db.inmemory.repos import (
    InMemoryCharacterRepository,
    InMemoryEntityRepository,
    InMemoryLocationRepository,
    InMemoryWorldRepository,
)


class ExploreEventVarietyTests(unittest.TestCase):
    def _build_service(self, seed: int = 37):
        event_bus = EventBus()
        world_repo = InMemoryWorldRepository(seed=seed)
        character = Character(id=909, name="Vale", location_id=1, hp_max=20, hp_current=20, money=10)
        character_repo = InMemoryCharacterRepository({character.id: character})
        entity_repo = InMemoryEntityRepository([])
        location_repo = InMemoryLocationRepository({1: Location(id=1, name="Ashen Wilds", biome="wilderness")})
        progression = WorldProgression(world_repo, entity_repo, event_bus)
        service = GameService(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
            progression=progression,
        )
        return service, character_repo, world_repo, character.id

    def test_explore_without_encounter_emits_noncombat_event(self):
        service, character_repo, world_repo, character_id = self._build_service(seed=41)
        before = character_repo.get(character_id)
        before_hp = before.hp_current
        before_money = before.money

        view, character, enemies = service.explore_intent(character_id)

        self.assertFalse(enemies)
        self.assertFalse(view.has_encounter)
        self.assertTrue(view.message)
        self.assertNotEqual("You find nothing of interest today.", view.message)

        last_event = character.flags.get("last_explore_event", {})
        self.assertIn(last_event.get("kind"), {"discovery", "cache", "hazard"})

        if last_event.get("kind") == "cache":
            self.assertGreaterEqual(character.money, before_money)
        if last_event.get("kind") == "hazard":
            self.assertLessEqual(character.hp_current, before_hp)

        world = world_repo.load_default()
        rows = world.flags.get("consequences", []) if isinstance(world.flags, dict) else []
        self.assertTrue(any(isinstance(row, dict) and str(row.get("kind", "")).startswith("explore_") for row in rows))

    def test_explore_noncombat_event_is_deterministic_for_same_seed(self):
        service_a, repo_a, _world_a, character_id_a = self._build_service(seed=51)
        service_b, repo_b, _world_b, character_id_b = self._build_service(seed=51)

        view_a, character_a, enemies_a = service_a.explore_intent(character_id_a)
        view_b, character_b, enemies_b = service_b.explore_intent(character_id_b)

        self.assertEqual([], enemies_a)
        self.assertEqual([], enemies_b)
        self.assertEqual(view_a.message, view_b.message)
        self.assertEqual(character_a.hp_current, character_b.hp_current)
        self.assertEqual(character_a.money, character_b.money)
        self.assertEqual(
            repo_a.get(character_id_a).flags.get("last_explore_event", {}).get("kind"),
            repo_b.get(character_id_b).flags.get("last_explore_event", {}).get("kind"),
        )

    def test_explore_enemy_plan_without_combat_returns_deterministic_fallback(self):
        service_a, repo_a, world_repo_a, character_id_a = self._build_service(seed=61)
        service_b, repo_b, world_repo_b, character_id_b = self._build_service(seed=61)

        class StubEncounterService:
            @staticmethod
            def generate_plan(**_kwargs):
                enemy = Entity(
                    id=801,
                    name="Bandit Scout",
                    level=1,
                    hp=8,
                    hp_current=8,
                    hp_max=8,
                    armour_class=12,
                    attack_bonus=2,
                    damage_die="d4",
                    attack_min=1,
                    attack_max=3,
                )
                return EncounterPlan(enemies=[enemy], source="table")

        service_a.encounter_service = StubEncounterService()
        service_b.encounter_service = StubEncounterService()
        service_a.combat_service = None
        service_b.combat_service = None

        view_a, character_a, enemies_a = service_a.explore_intent(character_id_a)
        view_b, character_b, enemies_b = service_b.explore_intent(character_id_b)

        self.assertFalse(view_a.has_encounter)
        self.assertFalse(view_b.has_encounter)
        self.assertEqual([], enemies_a)
        self.assertEqual([], enemies_b)
        self.assertEqual(view_a.message, view_b.message)
        self.assertEqual(character_a.hp_current, character_b.hp_current)
        self.assertEqual(character_a.money, character_b.money)

        self.assertEqual("threat_no_combat", repo_a.get(character_id_a).flags.get("last_explore_event", {}).get("kind"))
        self.assertEqual("threat_no_combat", repo_b.get(character_id_b).flags.get("last_explore_event", {}).get("kind"))

        world_a = world_repo_a.load_default()
        world_b = world_repo_b.load_default()
        consequences_a = world_a.flags.get("consequences", []) if isinstance(world_a.flags, dict) else []
        consequences_b = world_b.flags.get("consequences", []) if isinstance(world_b.flags, dict) else []
        self.assertTrue(any(isinstance(row, dict) and row.get("kind") == "explore_no_combat_threat" for row in consequences_a))
        self.assertTrue(any(isinstance(row, dict) and row.get("kind") == "explore_no_combat_threat" for row in consequences_b))


if __name__ == "__main__":
    unittest.main()
