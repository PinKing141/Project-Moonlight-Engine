import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.event_bus import EventBus
from rpg.application.services.quest_service import QuestService
from rpg.domain.events import MonsterSlain, TickAdvanced
from rpg.domain.models.character import Character
from rpg.domain.models.world import World
from rpg.domain.repositories import CharacterRepository, WorldRepository
from rpg.infrastructure.inmemory.inmemory_quest_template_repo import InMemoryQuestTemplateRepository


class _StubWorldRepository(WorldRepository):
    def __init__(self) -> None:
        self.world = World(id=1, name="Test", current_turn=0, flags={})

    def load_default(self):
        return self.world

    def save(self, world: World) -> None:
        self.world = world


class _StubCharacterRepository(CharacterRepository):
    def __init__(self, characters: dict[int, Character]) -> None:
        self.characters = characters

    def get(self, character_id: int):
        return self.characters.get(character_id)

    def list_all(self):
        return list(self.characters.values())

    def save(self, character: Character) -> None:
        self.characters[character.id] = character

    def find_by_location(self, location_id: int):
        return [c for c in self.characters.values() if c.location_id == location_id]

    def create(self, character: Character, location_id: int):
        character.location_id = location_id
        self.characters[character.id] = character
        return character


class QuestServiceTests(unittest.TestCase):
    def test_tick_posts_multiple_quest_contracts(self) -> None:
        bus = EventBus()
        world_repo = _StubWorldRepository()
        hero = Character(id=11, name="Ari", location_id=1, xp=0, money=0)
        char_repo = _StubCharacterRepository({hero.id: hero})

        service = QuestService(world_repo=world_repo, character_repo=char_repo, event_bus=bus)
        service.register_handlers()

        bus.publish(TickAdvanced(turn_after=1))

        quests = world_repo.world.flags.get("quests", {})
        self.assertIn("first_hunt", quests)
        self.assertIn("trail_patrol", quests)
        self.assertIn("supply_drop", quests)
        self.assertIn("crown_hunt_order", quests)
        self.assertIn("syndicate_route_run", quests)
        self.assertIn("forest_path_clearance", quests)
        self.assertIn("ruins_wayfinding", quests)
        self.assertEqual(
            {
                "first_hunt",
                "trail_patrol",
                "supply_drop",
                "crown_hunt_order",
                "syndicate_route_run",
                "forest_path_clearance",
                "ruins_wayfinding",
            },
            set(quests.keys()),
        )
        self.assertEqual("available", quests["first_hunt"]["status"])
        self.assertEqual("kill_any", quests["trail_patrol"]["objective_kind"])
        self.assertEqual("travel_count", quests["supply_drop"]["objective_kind"])
        self.assertEqual("kill_any", quests["crown_hunt_order"]["objective_kind"])
        self.assertEqual("travel_count", quests["syndicate_route_run"]["objective_kind"])
        self.assertEqual("kill_any", quests["forest_path_clearance"]["objective_kind"])
        self.assertEqual("travel_count", quests["ruins_wayfinding"]["objective_kind"])
        self.assertTrue(str(quests["first_hunt"].get("seed_key", "")).startswith("quest:first_hunt:"))
        self.assertTrue(
            str(quests["crown_hunt_order"].get("seed_key", "")).startswith("quest:crown_hunt_order:")
        )
        self.assertTrue(
            str(quests["syndicate_route_run"].get("seed_key", "")).startswith("quest:syndicate_route_run:")
        )
        self.assertTrue(
            str(quests["forest_path_clearance"].get("seed_key", "")).startswith("quest:forest_path_clearance:")
        )
        self.assertTrue(
            str(quests["ruins_wayfinding"].get("seed_key", "")).startswith("quest:ruins_wayfinding:")
        )

    def test_tick_then_monster_slain_marks_quest_ready_to_turn_in(self) -> None:
        bus = EventBus()
        world_repo = _StubWorldRepository()
        hero = Character(id=11, name="Ari", location_id=1, xp=0, money=0)
        char_repo = _StubCharacterRepository({hero.id: hero})

        service = QuestService(world_repo=world_repo, character_repo=char_repo, event_bus=bus)
        service.register_handlers()

        bus.publish(TickAdvanced(turn_after=1))
        quest = world_repo.world.flags.get("quests", {}).get("first_hunt")
        self.assertIsNotNone(quest)
        self.assertEqual("available", quest["status"])

        # emulate acceptance through app intent layer
        quest["status"] = "active"

        bus.publish(MonsterSlain(monster_id=99, location_id=1, by_character_id=11, turn=1))

        quest = world_repo.world.flags.get("quests", {}).get("first_hunt")
        self.assertEqual("ready_to_turn_in", quest["status"])
        self.assertEqual(1, quest["progress"])
        self.assertEqual(11, quest["owner_character_id"])
        updated = char_repo.get(11)
        self.assertEqual(0, updated.xp)
        self.assertEqual(0, updated.money)

    def test_active_travel_contract_progresses_on_ticks(self) -> None:
        bus = EventBus()
        world_repo = _StubWorldRepository()
        hero = Character(id=11, name="Ari", location_id=1, xp=0, money=0)
        char_repo = _StubCharacterRepository({hero.id: hero})

        service = QuestService(world_repo=world_repo, character_repo=char_repo, event_bus=bus)
        service.register_handlers()

        bus.publish(TickAdvanced(turn_after=1))
        quest = world_repo.world.flags.get("quests", {}).get("supply_drop")
        self.assertIsNotNone(quest)
        quest["status"] = "active"

        bus.publish(TickAdvanced(turn_after=2))
        quest = world_repo.world.flags.get("quests", {}).get("supply_drop")
        self.assertEqual(1, quest["progress"])
        self.assertEqual("active", quest["status"])

        bus.publish(TickAdvanced(turn_after=3))
        quest = world_repo.world.flags.get("quests", {}).get("supply_drop")
        self.assertEqual(2, quest["progress"])
        self.assertEqual("ready_to_turn_in", quest["status"])

    def test_tick_uses_template_repository_when_provided(self) -> None:
        bus = EventBus()
        world_repo = _StubWorldRepository()
        hero = Character(id=11, name="Ari", location_id=1, xp=0, money=0)
        char_repo = _StubCharacterRepository({hero.id: hero})
        template_repo = InMemoryQuestTemplateRepository(
            payload_rows=[
                {
                    "template_version": "quest_template_v1",
                    "slug": "guild_recon_pass",
                    "title": "Guild Recon Pass",
                    "objective": {"kind": "travel", "target_key": "route_leg", "target_count": 2},
                    "reward_xp": 13,
                    "reward_money": 6,
                    "cataclysm_pushback": False,
                }
            ]
        )

        service = QuestService(
            world_repo=world_repo,
            character_repo=char_repo,
            event_bus=bus,
            quest_template_repo=template_repo,
        )
        service.register_handlers()

        bus.publish(TickAdvanced(turn_after=1))

        quests = world_repo.world.flags.get("quests", {})
        self.assertIn("guild_recon_pass", quests)
        self.assertEqual("travel_count", quests["guild_recon_pass"]["objective_kind"])

    def test_tick_emits_novelty_metadata_with_bounded_retries(self) -> None:
        bus = EventBus()
        world_repo = _StubWorldRepository()
        history = [{"signature": "guild_recon_pass|travel|route_leg|tier:0|kind:|phase:|variant:0", "turn": index} for index in range(30)]
        world_repo.world.flags["quest_generation_signature_history"] = history

        hero = Character(id=11, name="Ari", location_id=1, xp=0, money=0)
        char_repo = _StubCharacterRepository({hero.id: hero})
        template_repo = InMemoryQuestTemplateRepository(
            payload_rows=[
                {
                    "template_version": "quest_template_v1",
                    "slug": "guild_recon_pass",
                    "title": "Guild Recon Pass",
                    "objective": {"kind": "travel", "target_key": "route_leg", "target_count": 2},
                    "reward_xp": 13,
                    "reward_money": 6,
                    "cataclysm_pushback": False,
                }
            ]
        )

        service = QuestService(
            world_repo=world_repo,
            character_repo=char_repo,
            event_bus=bus,
            quest_template_repo=template_repo,
        )
        service.register_handlers()
        bus.publish(TickAdvanced(turn_after=1))

        payload = world_repo.world.flags.get("quests", {}).get("guild_recon_pass", {})
        self.assertIn("signature", payload)
        self.assertIn("novelty_score", payload)
        self.assertIn("novelty_retry_count", payload)
        self.assertLessEqual(int(payload.get("novelty_retry_count", 0) or 0), 3)

    def test_replay_is_deterministic_for_identical_seed_and_context(self) -> None:
        def _run_once() -> dict[str, dict[str, object]]:
            bus = EventBus()
            world_repo = _StubWorldRepository()
            world_repo.world.flags["quest_generation_signature_history"] = [
                {"signature": "first_hunt|hunt|any_hostile|tier:0|kind:|phase:|variant:1", "turn": 0},
                {"signature": "trail_patrol|hunt|any_hostile|tier:0|kind:|phase:|variant:2", "turn": 0},
            ]
            hero = Character(id=11, name="Ari", location_id=1, xp=0, money=0)
            char_repo = _StubCharacterRepository({hero.id: hero})
            service = QuestService(world_repo=world_repo, character_repo=char_repo, event_bus=bus)
            service.register_handlers()
            bus.publish(TickAdvanced(turn_after=1))
            quests = world_repo.world.flags.get("quests", {})
            result: dict[str, dict[str, object]] = {}
            for quest_id, payload in quests.items():
                if not isinstance(payload, dict):
                    continue
                result[str(quest_id)] = {
                    "seed_key": str(payload.get("seed_key", "")),
                    "signature": str(payload.get("signature", "")),
                    "novelty_retry_count": int(payload.get("novelty_retry_count", 0) or 0),
                }
            return result

        first = _run_once()
        second = _run_once()
        self.assertEqual(first, second)

    def test_rank_gating_preserves_bronze_and_silver_accessibility_floors(self) -> None:
        bus = EventBus()
        world_repo = _StubWorldRepository()
        bronze = Character(
            id=11,
            name="Ari",
            location_id=1,
            flags={"guild": {"rank_tier": "bronze"}},
        )
        char_repo = _StubCharacterRepository({bronze.id: bronze})
        template_repo = InMemoryQuestTemplateRepository(
            payload_rows=[
                {
                    "template_version": "quest_template_v1",
                    "slug": "bronze_patrol",
                    "title": "Bronze Patrol",
                    "objective": {"kind": "hunt", "target_key": "any_hostile", "target_count": 1},
                    "reward_xp": 10,
                    "reward_money": 5,
                    "tags": ["tier:bronze"],
                    "cataclysm_pushback": False,
                },
                {
                    "template_version": "quest_template_v1",
                    "slug": "silver_recon",
                    "title": "Silver Recon",
                    "objective": {"kind": "travel", "target_key": "route_leg", "target_count": 2},
                    "reward_xp": 14,
                    "reward_money": 8,
                    "tags": ["tier:silver"],
                    "cataclysm_pushback": False,
                },
            ]
        )

        service = QuestService(
            world_repo=world_repo,
            character_repo=char_repo,
            event_bus=bus,
            quest_template_repo=template_repo,
        )
        service.register_handlers()
        bus.publish(TickAdvanced(turn_after=1))

        bronze_quests = world_repo.world.flags.get("quests", {})
        self.assertIn("bronze_patrol", bronze_quests)
        self.assertNotIn("silver_recon", bronze_quests)

        world_repo.world.flags["quests"] = {}
        bronze.flags = {"guild": {"rank_tier": "silver"}}
        bus.publish(TickAdvanced(turn_after=2))
        silver_quests = world_repo.world.flags.get("quests", {})
        self.assertIn("bronze_patrol", silver_quests)
        self.assertIn("silver_recon", silver_quests)

    def test_failure_modes_are_diverse_and_reward_scaling_is_bounded(self) -> None:
        bus = EventBus()
        world_repo = _StubWorldRepository()
        hard_character = Character(
            id=11,
            name="Ari",
            location_id=1,
            difficulty="hard",
            flags={"guild": {"rank_tier": "silver"}},
        )
        char_repo = _StubCharacterRepository({hard_character.id: hard_character})
        template_repo = InMemoryQuestTemplateRepository(
            payload_rows=[
                {
                    "template_version": "quest_template_v1",
                    "slug": "escort_line",
                    "title": "Escort Line",
                    "objective": {"kind": "travel", "target_key": "route_leg", "target_count": 4},
                    "reward_xp": 20,
                    "reward_money": 10,
                    "tags": ["tier:silver"],
                    "cataclysm_pushback": False,
                },
                {
                    "template_version": "quest_template_v1",
                    "slug": "nest_purge",
                    "title": "Nest Purge",
                    "objective": {"kind": "hunt", "target_key": "any_hostile", "target_count": 4},
                    "reward_xp": 24,
                    "reward_money": 12,
                    "tags": ["tier:silver"],
                    "cataclysm_pushback": False,
                },
            ]
        )

        service = QuestService(
            world_repo=world_repo,
            character_repo=char_repo,
            event_bus=bus,
            quest_template_repo=template_repo,
        )
        service.register_handlers()
        bus.publish(TickAdvanced(turn_after=1))

        quests = world_repo.world.flags.get("quests", {})
        failure_modes = {
            str(payload.get("failure_mode", ""))
            for payload in quests.values()
            if isinstance(payload, dict)
        }
        self.assertGreaterEqual(len({mode for mode in failure_modes if mode}), 2)

        escort = quests.get("escort_line", {})
        purge = quests.get("nest_purge", {})
        self.assertLessEqual(int(escort.get("target", 0) or 0), 4)
        self.assertLessEqual(int(purge.get("target", 0) or 0), 4)

        self.assertGreaterEqual(int(escort.get("reward_xp", 0) or 0), int(20 * 0.80))
        self.assertLessEqual(int(escort.get("reward_xp", 0) or 0), int(20 * 1.35) + 1)
        self.assertGreaterEqual(int(purge.get("reward_xp", 0) or 0), int(24 * 0.80))
        self.assertLessEqual(int(purge.get("reward_xp", 0) or 0), int(24 * 1.35) + 1)

    def test_generation_telemetry_counters_and_payload_fields_are_emitted(self) -> None:
        bus = EventBus()
        world_repo = _StubWorldRepository()
        hero = Character(id=11, name="Ari", location_id=1)
        char_repo = _StubCharacterRepository({hero.id: hero})
        template_repo = InMemoryQuestTemplateRepository(
            payload_rows=[
                {
                    "template_version": "quest_template_v1",
                    "slug": "forest_patrol",
                    "title": "Forest Patrol",
                    "objective": {"kind": "hunt", "target_key": "goblin", "target_count": 2},
                    "reward_xp": 14,
                    "reward_money": 8,
                    "tags": ["biome:forest", "tier:bronze"],
                    "cataclysm_pushback": False,
                }
            ]
        )

        service = QuestService(
            world_repo=world_repo,
            character_repo=char_repo,
            event_bus=bus,
            quest_template_repo=template_repo,
        )
        service.register_handlers()
        bus.publish(TickAdvanced(turn_after=1))

        payload = world_repo.world.flags.get("quests", {}).get("forest_patrol", {})
        self.assertEqual("hunt", str(payload.get("telemetry_family", "")))
        self.assertEqual("forest", str(payload.get("telemetry_biome", "")))
        self.assertEqual("goblin", str(payload.get("telemetry_antagonist", "")))

        telemetry = world_repo.world.flags.get("quest_generation_telemetry_v1", {})
        counters = telemetry.get("counters", {}) if isinstance(telemetry, dict) else {}
        family = counters.get("family", {}) if isinstance(counters, dict) else {}
        biome = counters.get("biome", {}) if isinstance(counters, dict) else {}
        antagonist = counters.get("antagonist", {}) if isinstance(counters, dict) else {}

        self.assertEqual(1, int(family.get("hunt", 0) or 0))
        self.assertEqual(1, int(biome.get("forest", 0) or 0))
        self.assertEqual(1, int(antagonist.get("goblin", 0) or 0))

    def test_generation_telemetry_alerts_trigger_on_repetition_threshold(self) -> None:
        bus = EventBus()
        world_repo = _StubWorldRepository()
        hero = Character(id=11, name="Ari", location_id=1)
        char_repo = _StubCharacterRepository({hero.id: hero})
        template_repo = InMemoryQuestTemplateRepository(
            payload_rows=[
                {
                    "template_version": "quest_template_v1",
                    "slug": "repeat_hunt",
                    "title": "Repeat Hunt",
                    "objective": {"kind": "hunt", "target_key": "any_hostile", "target_count": 1},
                    "reward_xp": 10,
                    "reward_money": 5,
                    "tags": ["biome:plains", "tier:bronze"],
                    "cataclysm_pushback": False,
                }
            ]
        )

        service = QuestService(
            world_repo=world_repo,
            character_repo=char_repo,
            event_bus=bus,
            quest_template_repo=template_repo,
        )
        service.register_handlers()

        for turn in range(1, 6):
            world_repo.world.flags["quests"] = {}
            envelope = world_repo.world.flags.get("quests_v2", {})
            if isinstance(envelope, dict):
                envelope["contracts"] = {}
                world_repo.world.flags["quests_v2"] = envelope
            bus.publish(TickAdvanced(turn_after=turn))

        telemetry = world_repo.world.flags.get("quest_generation_telemetry_v1", {})
        alerts = telemetry.get("alerts", []) if isinstance(telemetry, dict) else []
        self.assertTrue(any(str(row.get("kind", "")) == "repetition_threshold" for row in alerts if isinstance(row, dict)))

        tuning = telemetry.get("tuning", {}) if isinstance(telemetry, dict) else {}
        self.assertEqual(20, int(tuning.get("recent_window", 0) or 0))
        self.assertEqual(4, int(tuning.get("repeat_alert_threshold", 0) or 0))

    def test_quests_v2_schema_bridge_mirrors_legacy_contracts(self) -> None:
        bus = EventBus()
        world_repo = _StubWorldRepository()
        world_repo.world.flags["quests"] = {
            "legacy_contract": {
                "status": "available",
                "objective_kind": "kill_any",
                "progress": 0,
                "target": 1,
                "reward_xp": 9,
                "reward_money": 4,
            }
        }
        hero = Character(id=11, name="Ari", location_id=1)
        char_repo = _StubCharacterRepository({hero.id: hero})

        service = QuestService(world_repo=world_repo, character_repo=char_repo, event_bus=bus)
        service.register_handlers()
        bus.publish(TickAdvanced(turn_after=1))

        envelope = world_repo.world.flags.get("quests_v2", {})
        self.assertEqual("quest_state_v2", str(envelope.get("version", "")))
        contracts = envelope.get("contracts", {}) if isinstance(envelope, dict) else {}
        self.assertIn("legacy_contract", contracts)
        self.assertIs(world_repo.world.flags.get("quests"), contracts)

    def test_generated_payload_includes_narrative_and_encounter_strategy_fields(self) -> None:
        bus = EventBus()
        world_repo = _StubWorldRepository()
        hero = Character(id=11, name="Ari", location_id=1, difficulty="hard")
        char_repo = _StubCharacterRepository({hero.id: hero})
        template_repo = InMemoryQuestTemplateRepository(
            payload_rows=[
                {
                    "template_version": "quest_template_v1",
                    "slug": "story_hunt",
                    "title": "Story Hunt",
                    "objective": {"kind": "hunt", "target_key": "any_hostile", "target_count": 2},
                    "reward_xp": 14,
                    "reward_money": 7,
                    "tags": ["biome:forest", "tier:bronze"],
                    "cataclysm_pushback": False,
                }
            ]
        )

        service = QuestService(
            world_repo=world_repo,
            character_repo=char_repo,
            event_bus=bus,
            quest_template_repo=template_repo,
        )
        service.register_handlers()
        bus.publish(TickAdvanced(turn_after=1))

        payload = world_repo.world.flags.get("quests", {}).get("story_hunt", {})
        self.assertTrue(str(payload.get("narrative_brief", "")).strip())
        self.assertTrue(str(payload.get("rumor_hook", "")).strip())
        self.assertTrue(str(payload.get("encounter_ai_profile_v2", "")).strip())
        self.assertTrue(str(payload.get("encounter_ai_strategy", "")).strip())
        self.assertIn("Story Hunt", str(payload.get("objective_note", "")))

    def test_analytics_snapshot_export_updates_each_tick(self) -> None:
        bus = EventBus()
        world_repo = _StubWorldRepository()
        hero = Character(id=11, name="Ari", location_id=1)
        char_repo = _StubCharacterRepository({hero.id: hero})

        service = QuestService(world_repo=world_repo, character_repo=char_repo, event_bus=bus)
        service.register_handlers()
        bus.publish(TickAdvanced(turn_after=1))
        bus.publish(TickAdvanced(turn_after=2))

        telemetry = world_repo.world.flags.get("quest_generation_telemetry_v1", {})
        export = telemetry.get("analytics_export", {}) if isinstance(telemetry, dict) else {}
        self.assertEqual("quest_generation_analytics_v1", str(export.get("schema_version", "")))
        self.assertEqual(2, int(export.get("latest_turn", 0) or 0))
        trends = telemetry.get("trends", []) if isinstance(telemetry, dict) else []
        self.assertGreaterEqual(len(trends), 2)


if __name__ == "__main__":
    unittest.main()
