import sys
from pathlib import Path
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.event_bus import EventBus
from rpg.application.services.game_service import GameService
from rpg.application.services.world_progression import WorldProgression
from rpg.domain.models.character import Character
from rpg.domain.models.location import Location
from rpg.infrastructure.inmemory.inmemory_faction_repo import InMemoryFactionRepository
from rpg.infrastructure.db.inmemory.repos import (
    InMemoryCharacterRepository,
    InMemoryEntityRepository,
    InMemoryLocationRepository,
    InMemoryWorldRepository,
)


class TownSocialFlowTests(unittest.TestCase):
    def _build_service(self, *, with_factions: bool = False):
        event_bus = EventBus()
        world_repo = InMemoryWorldRepository(seed=13)
        character = Character(id=101, name="Iris", location_id=1)
        character.attributes["charisma"] = 14
        character.money = 20
        character_repo = InMemoryCharacterRepository({character.id: character})
        entity_repo = InMemoryEntityRepository([])
        location_repo = InMemoryLocationRepository({1: Location(id=1, name="Town")})
        progression = WorldProgression(world_repo, entity_repo, event_bus)
        faction_repo = InMemoryFactionRepository() if with_factions else None
        if faction_repo is not None:
            crown = faction_repo.get("the_crown")
            if crown is not None:
                crown.reputation[f"character:{character.id}"] = 14
        service = GameService(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
            progression=progression,
            faction_repo=faction_repo,
        )
        return service, character.id

    def test_get_town_view_intent_returns_npc_roster(self):
        service, character_id = self._build_service()
        character = service.character_repo.get(character_id)
        self.assertIsNotNone(character)
        character.flags["faction_heat"] = {"wardens": 9}
        service.character_repo.save(character)
        view = service.get_town_view_intent(character_id)

        self.assertGreaterEqual(len(view.npcs), 3)
        self.assertTrue(any(npc.role == "Innkeeper" for npc in view.npcs))
        self.assertTrue(view.district_tag)
        self.assertTrue(view.landmark_tag)
        self.assertIn("Pressure:", view.pressure_summary)
        self.assertTrue(any("Wardens" in line for line in view.pressure_lines))

    def test_social_interaction_is_seed_deterministic_for_same_context(self):
        service_a, character_id_a = self._build_service()
        service_b, character_id_b = self._build_service()

        out_a = service_a.submit_social_approach_intent(character_id_a, "innkeeper_mara", "Friendly")
        out_b = service_b.submit_social_approach_intent(character_id_b, "innkeeper_mara", "Friendly")

        self.assertEqual(out_a.success, out_b.success)
        self.assertEqual(out_a.roll_total, out_b.roll_total)
        self.assertEqual(out_a.target_dc, out_b.target_dc)
        self.assertEqual(out_a.relationship_after, out_b.relationship_after)

    def test_social_interaction_updates_persisted_relationship(self):
        service, character_id = self._build_service()
        before = service.get_npc_interaction_intent(character_id, "captain_ren")

        outcome = service.submit_social_approach_intent(character_id, "captain_ren", "Direct")
        after = service.get_npc_interaction_intent(character_id, "captain_ren")

        self.assertEqual(before.relationship, outcome.relationship_before)
        self.assertEqual(after.relationship, outcome.relationship_after)

    def test_town_view_surfaces_active_story_seed_summary(self):
        service, character_id = self._build_service()
        world = service.world_repo.load_default()
        world.flags.setdefault("narrative", {})
        world.flags["narrative"]["story_seeds"] = [
            {
                "seed_id": "seed_3_0099",
                "status": "active",
                "pressure": "Faction raids on trade routes",
                "escalation_stage": "escalated",
            }
        ]
        service.world_repo.save(world)

        town = service.get_town_view_intent(character_id)
        self.assertTrue(any("Story Seed" in line for line in town.consequences))

    def test_npc_interaction_greeting_echoes_recent_major_event(self):
        service, character_id = self._build_service()
        world = service.world_repo.load_default()
        world.flags.setdefault("narrative", {})
        world.flags["narrative"]["major_events"] = [
            {
                "turn": 6,
                "seed_id": "seed_6_0003",
                "kind": "merchant_under_pressure",
                "resolution": "debt",
                "actor": character_id,
            }
        ]
        service.world_repo.save(world)

        interaction = service.get_npc_interaction_intent(character_id, "innkeeper_mara")
        self.assertIn("recent", interaction.greeting.lower())
        self.assertIn("merchant under pressure", interaction.greeting.lower())

    def test_npc_interaction_greeting_echoes_flashpoint_aftershock(self):
        service, character_id = self._build_service()
        world = service.world_repo.load_default()
        world.flags.setdefault("narrative", {})
        world.flags["narrative"]["flashpoint_echoes"] = [
            {
                "turn": 7,
                "seed_id": "seed_7_0088",
                "resolution": "faction_shift",
                "channel": "combat",
                "bias_faction": "wardens",
                "rival_faction": "wild",
                "affected_factions": 3,
                "severity_score": 86,
                "severity_band": "critical",
            }
        ]
        service.world_repo.save(world)

        interaction = service.get_npc_interaction_intent(character_id, "captain_ren")
        self.assertIn("flashpoint", interaction.greeting.lower())
        self.assertIn("faction shift", interaction.greeting.lower())
        self.assertIn("critical", interaction.greeting.lower())

    def test_npc_interaction_surfaces_invoke_faction_when_reputation_is_high(self):
        service, character_id = self._build_service(with_factions=True)

        interaction = service.get_npc_interaction_intent(character_id, "captain_ren")

        self.assertIn("Invoke Faction", interaction.approaches)

    def test_bribe_approach_consumes_gold_when_used(self):
        service, character_id = self._build_service()
        starting_gold = int(service.character_repo.get(character_id).money)

        interaction = service.get_npc_interaction_intent(character_id, "innkeeper_mara")
        self.assertIn("Bribe", interaction.approaches)

        outcome = service.submit_social_approach_intent(character_id, "innkeeper_mara", "Bribe")
        after = service.character_repo.get(character_id)

        self.assertEqual("bribe", outcome.approach)
        self.assertEqual(starting_gold - 8, after.money)

    def test_silas_leverage_intel_advances_kill_any_without_instant_completion(self):
        service, character_id = self._build_service()
        character = service.character_repo.get(character_id)
        character.attributes["wisdom"] = 30
        character.flags.setdefault("interaction_unlocks", {})["intel_leverage"] = True
        service.character_repo.save(character)

        world = service.world_repo.load_default()
        quests = service._world_quests(world)
        quests["trail_patrol"] = {
            "status": "active",
            "objective_kind": "kill_any",
            "target": 5,
            "progress": 0,
        }
        service.world_repo.save(world)

        outcome = service.submit_social_approach_intent(character_id, "broker_silas", "Leverage Intel")
        self.assertTrue(outcome.success)

        world_after = service.world_repo.load_default()
        quest_after = service._world_quests(world_after)["trail_patrol"]
        self.assertEqual(1, int(quest_after.get("progress", 0)))
        self.assertEqual("active", str(quest_after.get("status", "")))

    def test_social_dc_increases_when_npc_faction_heat_is_high(self):
        service_a, character_id_a = self._build_service()
        service_b, character_id_b = self._build_service()

        heated = service_b.character_repo.get(character_id_b)
        heated.flags["faction_heat"] = {"wardens": 14}
        service_b.character_repo.save(heated)

        out_a = service_a.submit_social_approach_intent(character_id_a, "innkeeper_mara", "Friendly")
        out_b = service_b.submit_social_approach_intent(character_id_b, "innkeeper_mara", "Friendly")

        self.assertEqual(out_a.target_dc + 2, out_b.target_dc)
        self.assertTrue(any("Pressure:" in line for line in out_b.messages))

    def test_failed_social_approach_adds_heat_for_npc_affinity(self):
        service, character_id = self._build_service()
        character = service.character_repo.get(character_id)
        character.attributes["charisma"] = 8
        service.character_repo.save(character)

        with mock.patch("random.Random.randint", return_value=1):
            outcome = service.submit_social_approach_intent(character_id, "captain_ren", "Friendly")

        self.assertFalse(outcome.success)
        saved = service.character_repo.get(character_id)
        heat = dict(saved.flags.get("faction_heat", {}))
        self.assertGreaterEqual(int(heat.get("the_crown", 0) or 0), 1)

    def test_npc_interaction_marks_off_duty_schedule_at_midnight(self):
        service, character_id = self._build_service()
        world = service.world_repo.load_default()
        world.current_turn = 22
        service.world_repo.save(world)

        interaction = service.get_npc_interaction_intent(character_id, "captain_ren")

        self.assertEqual([], list(interaction.approaches or []))
        self.assertIn("off duty", interaction.greeting.lower())


if __name__ == "__main__":
    unittest.main()
