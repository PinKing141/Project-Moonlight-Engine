import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.event_bus import EventBus
from rpg.application.services.game_service import GameService
from rpg.application.services.world_progression import WorldProgression
from rpg.domain.models.character import Character
from rpg.domain.models.entity import Entity
from rpg.domain.models.location import Location
from rpg.infrastructure.db.inmemory.repos import (
    InMemoryCharacterRepository,
    InMemoryEntityRepository,
    InMemoryLocationRepository,
    InMemoryWorldRepository,
)
from rpg.infrastructure.inmemory.inmemory_faction_repo import InMemoryFactionRepository


class StorySeedResolutionTests(unittest.TestCase):
    def _build_service(self):
        event_bus = EventBus()
        world_repo = InMemoryWorldRepository(seed=41)
        character = Character(id=777, name="Nora", location_id=1, money=10)
        character.attributes["charisma"] = 30
        character.attributes["wisdom"] = 18
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
        return service, world_repo, character_repo, faction_repo, character.id

    def _inject_active_seed(self, world_repo, kind: str = "merchant_under_pressure"):
        world = world_repo.load_default()
        world.flags.setdefault("narrative", {})
        world.flags["narrative"]["story_seeds"] = [
            {
                "seed_id": "seed_9_1234",
                "kind": kind,
                "status": "active",
                "initiator": "broker_silas",
                "motivation": "Protect caravan profits",
                "pressure": "Faction raids on trade routes",
                "opportunity": "Hire local help",
                "escalation_stage": "escalated",
                "escalation_path": ["caravan_delayed", "route_sabotage"],
                "resolution_variants": ["prosperity", "debt", "faction_shift"],
                "faction_bias": "wardens",
                "narrative_tags": ["scarcity", "ambition"],
                "created_turn": 1,
                "last_update_turn": 1,
            }
        ]
        world_repo.save(world)

    def test_successful_broker_social_resolves_active_story_seed(self):
        service, world_repo, character_repo, _faction_repo, character_id = self._build_service()
        self._inject_active_seed(world_repo)

        outcome = service.submit_social_approach_intent(character_id, "broker_silas", "Friendly")

        world = world_repo.load_default()
        seed = world.flags.get("narrative", {}).get("story_seeds", [])[0]
        self.assertEqual("resolved", seed.get("status"))
        self.assertEqual("social", seed.get("resolved_by"))
        self.assertTrue(any("Story seed resolved" in msg for msg in outcome.messages))

        memory = world.flags.get("narrative", {}).get("major_events", [])
        self.assertTrue(memory)

        updated = character_repo.get(character_id)
        self.assertGreaterEqual(updated.money, 6)

    def test_resolved_story_seed_no_longer_surfaces_as_active_seed_rumour(self):
        service, world_repo, _character_repo, _faction_repo, character_id = self._build_service()
        self._inject_active_seed(world_repo)

        before = service.get_rumour_board_intent(character_id)
        self.assertTrue(any(item.rumour_id.startswith("seed:") for item in before.items))

        service.submit_social_approach_intent(character_id, "broker_silas", "Friendly")
        after = service.get_rumour_board_intent(character_id)
        self.assertFalse(any(item.rumour_id.startswith("seed:") for item in after.items))

    def test_combat_reward_resolves_active_story_seed_and_records_memory(self):
        service, world_repo, character_repo, _faction_repo, character_id = self._build_service()
        self._inject_active_seed(world_repo)

        character = character_repo.get(character_id)
        monster = Entity(id=321, name="Road Raider", level=2, faction_id="raiders", hp=1)

        before = service.get_rumour_board_intent(character_id)
        self.assertTrue(any(item.rumour_id.startswith("seed:") for item in before.items))

        service.apply_encounter_reward_intent(character, monster)

        world = world_repo.load_default()
        seed = world.flags.get("narrative", {}).get("story_seeds", [])[0]
        self.assertEqual("resolved", seed.get("status"))
        self.assertEqual("combat", seed.get("resolved_by"))
        self.assertEqual(321, seed.get("resolved_monster_id"))

        memory = world.flags.get("narrative", {}).get("major_events", [])
        self.assertTrue(memory)
        self.assertEqual(321, memory[-1].get("monster_id"))

        after = service.get_rumour_board_intent(character_id)
        self.assertFalse(any(item.rumour_id.startswith("seed:") for item in after.items))

    def test_faction_flashpoint_resolves_via_social_branch(self):
        service, world_repo, _character_repo, _faction_repo, character_id = self._build_service()
        self._inject_active_seed(world_repo, kind="faction_flashpoint")

        outcome = service.submit_social_approach_intent(character_id, "broker_silas", "Friendly")

        world = world_repo.load_default()
        seed = world.flags.get("narrative", {}).get("story_seeds", [])[0]
        self.assertEqual("resolved", seed.get("status"))
        self.assertEqual("social", seed.get("resolved_by"))
        self.assertTrue(any("Story seed resolved" in msg for msg in outcome.messages))

        after = service.get_rumour_board_intent(character_id)
        self.assertFalse(any(item.rumour_id.startswith("seed:") for item in after.items))

        world = world_repo.load_default()
        consequences = world.flags.get("consequences", [])
        self.assertTrue(any(row.get("kind") == "flashpoint_aftershock" for row in consequences if isinstance(row, dict)))

        echoes = world.flags.get("narrative", {}).get("flashpoint_echoes", [])
        self.assertTrue(echoes)
        self.assertEqual("social", echoes[-1].get("channel"))
        self.assertIn(echoes[-1].get("severity_band"), {"low", "moderate", "high", "critical"})
        self.assertGreaterEqual(int(echoes[-1].get("severity_score", 0)), 0)
        self.assertLessEqual(int(echoes[-1].get("severity_score", 0)), 100)

        standings = service.faction_standings_intent(character_id)
        non_zero = [value for value in standings.values() if int(value) != 0]
        self.assertGreaterEqual(len(non_zero), 2)

    def test_faction_flashpoint_resolves_via_combat_branch(self):
        service, world_repo, character_repo, _faction_repo, character_id = self._build_service()
        self._inject_active_seed(world_repo, kind="faction_flashpoint")

        character = character_repo.get(character_id)
        monster = Entity(id=654, name="Militia Skirmisher", level=2, faction_id="wardens", hp=1)
        service.apply_encounter_reward_intent(character, monster)

        world = world_repo.load_default()
        seed = world.flags.get("narrative", {}).get("story_seeds", [])[0]
        self.assertEqual("resolved", seed.get("status"))
        self.assertEqual("combat", seed.get("resolved_by"))
        self.assertEqual(654, seed.get("resolved_monster_id"))

        echoes = world.flags.get("narrative", {}).get("flashpoint_echoes", [])
        self.assertTrue(echoes)
        self.assertEqual("combat", echoes[-1].get("channel"))
        self.assertIn(echoes[-1].get("severity_band"), {"low", "moderate", "high", "critical"})

        after = service.get_rumour_board_intent(character_id)
        self.assertFalse(any(item.rumour_id.startswith("seed:") for item in after.items))

    def test_flashpoint_aftershock_is_deterministic_for_same_seed_and_script(self):
        service_a, world_repo_a, _character_repo_a, _faction_repo_a, character_id_a = self._build_service()
        service_b, world_repo_b, _character_repo_b, _faction_repo_b, character_id_b = self._build_service()

        self._inject_active_seed(world_repo_a, kind="faction_flashpoint")
        self._inject_active_seed(world_repo_b, kind="faction_flashpoint")

        service_a.submit_social_approach_intent(character_id_a, "broker_silas", "Friendly")
        service_b.submit_social_approach_intent(character_id_b, "broker_silas", "Friendly")

        echo_a = world_repo_a.load_default().flags.get("narrative", {}).get("flashpoint_echoes", [])[-1]
        echo_b = world_repo_b.load_default().flags.get("narrative", {}).get("flashpoint_echoes", [])[-1]
        self.assertEqual(echo_a, echo_b)
        self.assertEqual(echo_a.get("severity_band"), echo_b.get("severity_band"))


if __name__ == "__main__":
    unittest.main()
