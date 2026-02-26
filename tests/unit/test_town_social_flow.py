import sys
from pathlib import Path
import unittest

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
        view = service.get_town_view_intent(character_id)

        self.assertGreaterEqual(len(view.npcs), 3)
        self.assertTrue(any(npc.role == "Innkeeper" for npc in view.npcs))
        self.assertTrue(view.district_tag)
        self.assertTrue(view.landmark_tag)

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


if __name__ == "__main__":
    unittest.main()
