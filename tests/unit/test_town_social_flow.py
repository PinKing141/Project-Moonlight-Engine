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

    def test_contextual_dialogue_options_expand_under_tension_and_flashpoint(self):
        service, character_id = self._build_service()
        world = service.world_repo.load_default()
        world.flags.setdefault("narrative", {})
        world.flags["narrative"]["tension_level"] = 72
        world.flags["narrative"]["flashpoint_echoes"] = [
            {
                "turn": 5,
                "seed_id": "seed_5_1111",
                "resolution": "debt",
                "channel": "social",
                "severity_band": "high",
            }
        ]
        service.world_repo.save(world)

        with mock.patch.dict(
            "os.environ",
            {
                "RPG_DIALOGUE_TREE_ENABLED": "1",
                "RPG_DIALOGUE_CONTEXTUAL_OPTIONS": "1",
            },
            clear=False,
        ):
            interaction = service.get_npc_interaction_intent(character_id, "broker_silas")

        lowered = [item.lower() for item in interaction.approaches]
        self.assertIn("urgent appeal", lowered)
        self.assertIn("address flashpoint", lowered)
        self.assertIn("critical", interaction.greeting.lower())

    def test_shop_label_includes_cataclysm_strain_when_active(self):
        service, character_id = self._build_service()
        world = service.world_repo.load_default()
        world.flags["cataclysm_state"] = {
            "active": True,
            "kind": "plague",
            "phase": "grip_tightens",
            "progress": 45,
            "seed": 77,
            "started_turn": 4,
            "last_advance_turn": world.current_turn,
        }
        service.world_repo.save(world)

        shop = service.get_shop_view_intent(character_id)

        self.assertIn("cataclysm strain", str(shop.price_modifier_label).lower())

    def test_social_outcome_persists_dialogue_state_v1(self):
        service, character_id = self._build_service()

        with mock.patch.dict("os.environ", {"RPG_DIALOGUE_TREE_ENABLED": "1"}, clear=False):
            service.submit_social_approach_intent(character_id, "innkeeper_mara", "Friendly")

        character = service.character_repo.get(character_id)
        world = service.world_repo.load_default()
        self.assertIsNotNone(character)
        self.assertIsNotNone(world)

        char_state = dict(character.flags.get("dialogue_state_v1", {}))
        world_state = dict(world.flags.get("dialogue_state_v1", {}))
        self.assertEqual(1, int(char_state.get("version", 0)))
        self.assertEqual(1, int(world_state.get("version", 0)))
        sessions = dict(char_state.get("npc_sessions", {}))
        self.assertIn("innkeeper_mara", sessions)

    def test_dialogue_session_reflects_stage_progression_on_success(self):
        service, character_id = self._build_service()

        with mock.patch.dict(
            "os.environ",
            {"RPG_DIALOGUE_TREE_ENABLED": "1", "RPG_DIALOGUE_CONTEXTUAL_OPTIONS": "1"},
            clear=False,
        ), mock.patch(
            "random.Random.randint", return_value=20
        ):
            opening = service.get_dialogue_session_intent(character_id, "broker_silas")
            self.assertEqual("opening", opening.stage_id)

            service.submit_dialogue_choice_intent(character_id, "broker_silas", "friendly")
            probe = service.get_dialogue_session_intent(character_id, "broker_silas")
            self.assertEqual("probe", probe.stage_id)

            service.submit_dialogue_choice_intent(character_id, "broker_silas", "direct")
            resolved = service.get_dialogue_session_intent(character_id, "broker_silas")
            self.assertEqual("resolve", resolved.stage_id)

    def test_dialogue_locked_choice_falls_back_with_reason(self):
        service, character_id = self._build_service()

        with mock.patch.dict("os.environ", {"RPG_DIALOGUE_TREE_ENABLED": "1"}, clear=False):
            outcome = service.submit_dialogue_choice_intent(character_id, "innkeeper_mara", "nonexistent_dialogue_choice")

        self.assertTrue(outcome.messages)
        self.assertTrue(
            "unknown" in outcome.messages[0].lower() or "unavailable" in outcome.messages[0].lower()
        )

    def test_dialogue_session_uses_faction_conditioned_stage_variant(self):
        service, character_id = self._build_service()
        character = service.character_repo.get(character_id)
        character.flags["faction_heat"] = {"wardens": 12}
        service.character_repo.save(character)

        with mock.patch.dict("os.environ", {"RPG_DIALOGUE_TREE_ENABLED": "1"}, clear=False):
            session = service.get_dialogue_session_intent(character_id, "captain_ren")

        self.assertIn("hard suspicion", session.greeting.lower())

    def test_dialogue_choice_uses_faction_conditioned_response_variant(self):
        service, character_id = self._build_service()
        character = service.character_repo.get(character_id)
        character.flags["faction_heat"] = {"wardens": 14}
        service.character_repo.save(character)

        with mock.patch.dict("os.environ", {"RPG_DIALOGUE_TREE_ENABLED": "1"}, clear=False):
            outcome = service.submit_dialogue_choice_intent(character_id, "captain_ren", "direct")

        self.assertTrue(outcome.messages)
        self.assertIn("wardens are already on edge", outcome.messages[0].lower())

    def test_mara_opening_uses_critical_tension_variant_line(self):
        service, character_id = self._build_service()
        world = service.world_repo.load_default()
        world.flags.setdefault("narrative", {})
        world.flags["narrative"]["tension_level"] = 88
        service.world_repo.save(world)

        with mock.patch.dict("os.environ", {"RPG_DIALOGUE_TREE_ENABLED": "1"}, clear=False):
            session = service.get_dialogue_session_intent(character_id, "innkeeper_mara")

        self.assertIn("distant shouting", session.greeting.lower())

    def test_mara_direct_response_uses_wardens_heat_variant(self):
        service, character_id = self._build_service()
        character = service.character_repo.get(character_id)
        character.flags["faction_heat"] = {"wardens": 13}
        service.character_repo.save(character)

        with mock.patch.dict("os.environ", {"RPG_DIALOGUE_TREE_ENABLED": "1"}, clear=False):
            outcome = service.submit_dialogue_choice_intent(character_id, "innkeeper_mara", "direct")

        self.assertTrue(outcome.messages)
        self.assertIn("watch patrols are already hunting sparks", outcome.messages[0].lower())

    def test_captain_resolve_direct_applies_success_effects(self):
        service, character_id = self._build_service()
        character = service.character_repo.get(character_id)
        character.flags["faction_heat"] = {"wardens": 10}
        service.character_repo.save(character)

        world = service.world_repo.load_default()
        world.flags.setdefault("narrative", {})
        world.flags["narrative"]["tension_level"] = 40
        service.world_repo.save(world)

        with mock.patch.dict(
            "os.environ",
            {"RPG_DIALOGUE_TREE_ENABLED": "1", "RPG_DIALOGUE_CONTEXTUAL_OPTIONS": "1"},
            clear=False,
        ), mock.patch(
            "random.Random.randint", return_value=20
        ):
            service.submit_dialogue_choice_intent(character_id, "captain_ren", "friendly")
            service.submit_dialogue_choice_intent(character_id, "captain_ren", "friendly")
            outcome = service.submit_dialogue_choice_intent(character_id, "captain_ren", "direct")

        updated = service.character_repo.get(character_id)
        self.assertEqual(11, int(updated.flags.get("faction_heat", {}).get("wardens", 0) or 0))
        self.assertTrue(any("Pressure shift: wardens +1." in line for line in outcome.messages))
        self.assertTrue(any("Tension shift: +2" in line for line in outcome.messages))

        world = service.world_repo.load_default()
        self.assertEqual(42, int(world.flags.get("narrative", {}).get("tension_level", 0) or 0))
        consequences = list(world.flags.get("consequences", []) or [])
        self.assertTrue(any("tighter checkpoint stance" in str(row.get("message", "")).lower() for row in consequences if isinstance(row, dict)))

    def test_captain_resolve_direct_effects_do_not_apply_on_failure(self):
        service, character_id = self._build_service()
        character = service.character_repo.get(character_id)
        character.flags["faction_heat"] = {"wardens": 10}
        service.character_repo.save(character)

        world = service.world_repo.load_default()
        world.flags.setdefault("narrative", {})
        world.flags["narrative"]["tension_level"] = 40
        service.world_repo.save(world)

        with mock.patch.dict(
            "os.environ",
            {"RPG_DIALOGUE_TREE_ENABLED": "1", "RPG_DIALOGUE_CONTEXTUAL_OPTIONS": "1"},
            clear=False,
        ), mock.patch(
            "random.Random.randint", return_value=20
        ):
            service.submit_dialogue_choice_intent(character_id, "captain_ren", "friendly")
            service.submit_dialogue_choice_intent(character_id, "captain_ren", "friendly")

        with mock.patch.dict("os.environ", {"RPG_DIALOGUE_TREE_ENABLED": "1"}, clear=False), mock.patch(
            "random.Random.randint", return_value=1
        ):
            outcome = service.submit_dialogue_choice_intent(character_id, "captain_ren", "direct")

        updated = service.character_repo.get(character_id)
        self.assertEqual(12, int(updated.flags.get("faction_heat", {}).get("wardens", 0) or 0))
        self.assertTrue(any("Pressure shift: wardens +2." in line for line in outcome.messages))
        self.assertTrue(any("Tension shift: +6" in line for line in outcome.messages))

        world = service.world_repo.load_default()
        self.assertEqual(46, int(world.flags.get("narrative", {}).get("tension_level", 0) or 0))
        consequences = list(world.flags.get("consequences", []) or [])
        self.assertTrue(any("watch crackdown" in str(row.get("message", "")).lower() for row in consequences if isinstance(row, dict)))

    def test_captain_resolve_make_amends_deescalates_active_flashpoint_seed(self):
        service, character_id = self._build_service()
        character = service.character_repo.get(character_id)
        world = service.world_repo.load_default()
        world.flags.setdefault("narrative", {})
        world.flags["narrative"]["story_seeds"] = [
            {
                "seed_id": "seed_ren_001",
                "kind": "faction_flashpoint",
                "status": "active",
                "escalation_stage": "escalated",
                "pressure": "Wardens and rivals posture at checkpoints.",
            }
        ]
        notes = service._apply_dialogue_choice_effects(
            character=character,
            world=world,
            npc_id="captain_ren",
            success=True,
            effects=[
                {
                    "kind": "story_seed_state",
                    "on": "success",
                    "seed_kind": "faction_flashpoint",
                    "status": "active",
                    "escalation_stage": "simmering",
                }
            ],
        )

        seed = world.flags.get("narrative", {}).get("story_seeds", [])[0]
        self.assertEqual("active", str(seed.get("status", "")))
        self.assertEqual("simmering", str(seed.get("escalation_stage", "")))
        self.assertTrue(any("Story seed state shift" in line for line in notes))

    def test_captain_resolve_direct_failure_escalates_active_flashpoint_seed(self):
        service, character_id = self._build_service()
        world = service.world_repo.load_default()
        world.flags.setdefault("narrative", {})
        world.flags["narrative"]["story_seeds"] = [
            {
                "seed_id": "seed_ren_002",
                "kind": "faction_flashpoint",
                "status": "active",
                "escalation_stage": "simmering",
                "pressure": "Checkpoint disputes are spreading.",
            }
        ]
        service.world_repo.save(world)

        with mock.patch.dict("os.environ", {"RPG_DIALOGUE_TREE_ENABLED": "1"}, clear=False), mock.patch(
            "random.Random.randint", return_value=20
        ):
            service.submit_dialogue_choice_intent(character_id, "captain_ren", "friendly")
            service.submit_dialogue_choice_intent(character_id, "captain_ren", "friendly")

        with mock.patch.dict("os.environ", {"RPG_DIALOGUE_TREE_ENABLED": "1"}, clear=False), mock.patch(
            "random.Random.randint", return_value=1
        ):
            outcome = service.submit_dialogue_choice_intent(character_id, "captain_ren", "direct")

        world_after = service.world_repo.load_default()
        seed = world_after.flags.get("narrative", {}).get("story_seeds", [])[0]
        self.assertEqual("escalated", str(seed.get("status", "")))
        self.assertEqual("escalated", str(seed.get("escalation_stage", "")))
        self.assertTrue(any("Story seed state shift" in line for line in outcome.messages))


if __name__ == "__main__":
    unittest.main()
