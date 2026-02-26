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


class RumourBoardTests(unittest.TestCase):
    def _build_service(self, charisma: int = 10, with_factions: bool = False):
        event_bus = EventBus()
        world_repo = InMemoryWorldRepository(seed=31)
        character = Character(id=601, name="Nyra", location_id=1)
        character.attributes["charisma"] = charisma
        character.attributes["wisdom"] = 12
        character_repo = InMemoryCharacterRepository({character.id: character})
        entity_repo = InMemoryEntityRepository([])
        location_repo = InMemoryLocationRepository({1: Location(id=1, name="Town")})
        faction_repo = InMemoryFactionRepository() if with_factions else None
        progression = WorldProgression(world_repo, entity_repo, event_bus)
        service = GameService(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
            progression=progression,
            faction_repo=faction_repo,
        )
        return service, character.id, world_repo, faction_repo

    def test_rumour_board_is_deterministic_for_same_world_state(self):
        service_a, character_id_a, _world_a, _factions_a = self._build_service()
        service_b, character_id_b, _world_b, _factions_b = self._build_service()

        board_a = service_a.get_rumour_board_intent(character_id_a)
        board_b = service_b.get_rumour_board_intent(character_id_b)

        self.assertEqual([item.rumour_id for item in board_a.items], [item.rumour_id for item in board_b.items])
        self.assertEqual([item.confidence for item in board_a.items], [item.confidence for item in board_b.items])

    def test_rumour_board_exposes_empty_state_guidance(self):
        service, character_id, _world_repo, _factions = self._build_service()

        board = service.get_rumour_board_intent(character_id)

        self.assertTrue(board.empty_state_hint)
        self.assertIn("Check again", board.empty_state_hint)
        self.assertIn("threat", board.empty_state_hint.lower())
        self.assertIn("standing", board.empty_state_hint.lower())

    def test_rumour_board_varies_across_world_turn(self):
        service, character_id, _world_repo, _factions = self._build_service()
        day_one = service.get_rumour_board_intent(character_id)

        service.advance_world(ticks=1)
        day_two = service.get_rumour_board_intent(character_id)

        self.assertNotEqual([item.rumour_id for item in day_one.items], [item.rumour_id for item in day_two.items])

    def test_intel_unlock_increases_rumour_depth(self):
        service, character_id, _world_repo, _factions = self._build_service(charisma=16)
        baseline = service.get_rumour_board_intent(character_id)

        service.purchase_training_intent(character_id, "streetwise_briefing")
        upgraded = service.get_rumour_board_intent(character_id)

        self.assertGreaterEqual(len(upgraded.items), len(baseline.items))

    def test_faction_standing_deterministically_biases_rumour_mix(self):
        neutral_service, neutral_character_id, _world_repo, _factions = self._build_service(with_factions=True)
        neutral_board = neutral_service.get_rumour_board_intent(neutral_character_id)

        biased_service, biased_character_id, _world_repo, biased_factions = self._build_service(with_factions=True)
        wardens = biased_factions.get("wardens")
        wardens.adjust_reputation(f"character:{biased_character_id}", 7)
        biased_factions.save(wardens)

        biased_board = biased_service.get_rumour_board_intent(biased_character_id)

        neutral_ids = [item.rumour_id for item in neutral_board.items]
        biased_ids = [item.rumour_id for item in biased_board.items]
        self.assertNotEqual(neutral_ids, biased_ids)
        self.assertIn("bridge_toll", biased_ids)

    def test_rumour_history_is_pruned_by_window_and_capacity(self):
        service, character_id, world_repo, _factions = self._build_service(with_factions=True)

        for _ in range(20):
            service.get_rumour_board_intent(character_id)
            service.advance_world(ticks=1)

        world = world_repo.load_default()
        rows = world.flags.get("rumour_history", [])
        self.assertLessEqual(len(rows), 12)

        latest_recorded_day = max(int(row.get("day", 0)) for row in rows if isinstance(row, dict))
        oldest = min(int(row.get("day", latest_recorded_day)) for row in rows if isinstance(row, dict))
        self.assertGreaterEqual(oldest, latest_recorded_day - 8)

    def test_relationship_graph_pressure_biases_rumour_selection(self):
        service, character_id, world_repo, faction_repo = self._build_service(with_factions=True)

        wardens = faction_repo.get("wardens")
        wardens.adjust_reputation(f"character:{character_id}", 7)
        faction_repo.save(wardens)

        world = world_repo.load_default()
        world.flags.setdefault("narrative", {})
        world.flags["narrative"]["relationship_graph"] = {
            "faction_edges": {
                "undead|wardens": -25,
                "undead|wild": 0,
                "wardens|wild": 2,
            },
            "npc_faction_affinity": {},
            "history": [],
        }
        world_repo.save(world)

        board = service.get_rumour_board_intent(character_id)
        rumour_ids = [item.rumour_id for item in board.items]
        self.assertIn("crypt_lights", rumour_ids)

    def test_active_story_seed_appears_in_rumour_board(self):
        service, character_id, world_repo, _faction_repo = self._build_service(with_factions=True)

        world = world_repo.load_default()
        world.flags.setdefault("narrative", {})
        world.flags["narrative"]["story_seeds"] = [
            {
                "seed_id": "seed_1_0001",
                "status": "active",
                "pressure": "Faction raids on trade routes",
                "escalation_stage": "simmering",
            }
        ]
        world_repo.save(world)

        board = service.get_rumour_board_intent(character_id)
        self.assertTrue(any(item.rumour_id.startswith("seed:") for item in board.items))
        self.assertTrue(any("Story Seed" in item.text for item in board.items))

    def test_major_event_echo_appears_in_rumour_board(self):
        service, character_id, world_repo, _faction_repo = self._build_service(with_factions=True)

        world = world_repo.load_default()
        world.flags.setdefault("narrative", {})
        world.flags["narrative"]["major_events"] = [
            {
                "turn": 4,
                "seed_id": "seed_4_0007",
                "kind": "merchant_under_pressure",
                "resolution": "faction_shift",
                "actor": character_id,
            }
        ]
        world_repo.save(world)

        board = service.get_rumour_board_intent(character_id)
        self.assertTrue(any(item.rumour_id.startswith("memory:") for item in board.items))
        self.assertTrue(any(item.source == "Town Chronicle" for item in board.items))

    def test_story_memory_fingerprint_deterministically_influences_rumour_mix(self):
        baseline_service, baseline_character_id, _baseline_world_repo, _factions = self._build_service(with_factions=True)
        baseline_board = baseline_service.get_rumour_board_intent(baseline_character_id)

        memory_service, memory_character_id, memory_world_repo, _factions = self._build_service(with_factions=True)
        world = memory_world_repo.load_default()
        world.flags.setdefault("narrative", {})
        world.flags["narrative"]["major_events"] = [
            {
                "turn": 2,
                "seed_id": "seed_2_1234",
                "kind": "merchant_under_pressure",
                "resolution": "prosperity",
                "actor": memory_character_id,
            }
        ]
        memory_world_repo.save(world)

        memory_board = memory_service.get_rumour_board_intent(memory_character_id)
        baseline_ids = [item.rumour_id for item in baseline_board.items]
        memory_ids = [item.rumour_id for item in memory_board.items]
        self.assertNotEqual(baseline_ids, memory_ids)

    def test_flashpoint_echo_appears_in_rumour_board(self):
        service, character_id, world_repo, _faction_repo = self._build_service(with_factions=True)

        world = world_repo.load_default()
        world.flags.setdefault("narrative", {})
        world.flags["narrative"]["flashpoint_echoes"] = [
            {
                "turn": 7,
                "seed_id": "seed_7_4501",
                "resolution": "faction_shift",
                "channel": "combat",
                "bias_faction": "wardens",
                "rival_faction": "wild",
                "affected_factions": 3,
                "severity_score": 84,
                "severity_band": "critical",
            }
        ]
        world_repo.save(world)

        board = service.get_rumour_board_intent(character_id)
        self.assertTrue(any(item.rumour_id.startswith("flashpoint:") for item in board.items))
        self.assertTrue(any("Flashpoint Echo" in item.text for item in board.items))
        self.assertTrue(any("Severity" in item.text for item in board.items if item.rumour_id.startswith("flashpoint:")))

    def test_flashpoint_fingerprint_deterministically_influences_rumour_mix(self):
        baseline_service, baseline_character_id, _world_repo, _factions = self._build_service(with_factions=True)
        baseline_board = baseline_service.get_rumour_board_intent(baseline_character_id)

        fp_service, fp_character_id, fp_world_repo, _factions = self._build_service(with_factions=True)
        world = fp_world_repo.load_default()
        world.flags.setdefault("narrative", {})
        world.flags["narrative"]["flashpoint_echoes"] = [
            {
                "turn": 5,
                "seed_id": "seed_5_2200",
                "resolution": "prosperity",
                "channel": "social",
                "bias_faction": "wild",
                "rival_faction": "undead",
                "affected_factions": 2,
                "severity_score": 58,
                "severity_band": "moderate",
            }
        ]
        fp_world_repo.save(world)

        fp_board = fp_service.get_rumour_board_intent(fp_character_id)
        baseline_ids = [item.rumour_id for item in baseline_board.items]
        fp_ids = [item.rumour_id for item in fp_board.items]
        self.assertNotEqual(baseline_ids, fp_ids)

    def test_high_flashpoint_pressure_increases_rumour_depth(self):
        service, character_id, world_repo, _factions = self._build_service(with_factions=True)

        world = world_repo.load_default()
        world.threat_level = 0
        world.flags.setdefault("narrative", {})
        world.flags["narrative"]["flashpoint_echoes"] = [
            {
                "turn": world.current_turn,
                "seed_id": "seed_1_1111",
                "resolution": "faction_shift",
                "channel": "combat",
                "bias_faction": "wardens",
                "rival_faction": "wild",
                "affected_factions": 3,
                "severity_score": 85,
                "severity_band": "critical",
            }
        ]
        world_repo.save(world)

        board = service.get_rumour_board_intent(character_id)
        self.assertEqual(4, len(board.items))

    def test_flashpoint_bias_faction_influences_rumour_priority(self):
        service, character_id, world_repo, _factions = self._build_service(with_factions=True)

        world = world_repo.load_default()
        world.flags.setdefault("narrative", {})
        world.flags["narrative"]["flashpoint_echoes"] = [
            {
                "turn": world.current_turn,
                "seed_id": "seed_1_2222",
                "resolution": "prosperity",
                "channel": "social",
                "bias_faction": "wardens",
                "rival_faction": "wild",
                "affected_factions": 2,
                "severity_score": 70,
                "severity_band": "high",
            }
        ]
        world_repo.save(world)

        board = service.get_rumour_board_intent(character_id)
        rumour_ids = [item.rumour_id for item in board.items]
        self.assertIn("bridge_toll", rumour_ids)


if __name__ == "__main__":
    unittest.main()
