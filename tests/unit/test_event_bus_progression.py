import sys
from pathlib import Path
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.event_bus import EventBus
from rpg.application.services.world_progression import WorldProgression
from rpg.domain.events import TickAdvanced
from rpg.domain.models.world import World
from rpg.domain.repositories import EntityRepository, WorldRepository


class _StubWorldRepository(WorldRepository):
    def __init__(self) -> None:
        self.saved = []
        self.world = World(id=1, name="Stubland", current_turn=0, rng_seed=7)

    def load_default(self) -> World:
        return self.world

    def save(self, world: World) -> None:
        self.saved.append(world)


class _StubEntityRepository(EntityRepository):
    def get(self, entity_id: int):
        return None

    def get_many(self, entity_ids: list[int]):
        return []

    def list_for_level(self, target_level: int, tolerance: int = 2):
        return []

    def list_by_location(self, location_id: int):
        return []


class EventBusTests(unittest.TestCase):
    def test_publish_notifies_all_handlers_for_event_type(self) -> None:
        bus = EventBus()
        seen: list[str] = []

        class ExampleEvent:
            pass

        bus.subscribe(ExampleEvent, lambda evt: seen.append("first"))
        bus.subscribe(ExampleEvent, lambda evt: seen.append("second"))

        bus.publish(ExampleEvent())

        self.assertEqual(["first", "second"], seen)

    def test_publish_filters_handlers_by_event_class(self) -> None:
        bus = EventBus()
        seen: list[str] = []

        class Alpha:
            pass

        class Beta:
            pass

        bus.subscribe(Alpha, lambda evt: seen.append("alpha"))
        bus.subscribe(Beta, lambda evt: seen.append("beta"))

        bus.publish(Alpha())

        self.assertEqual(["alpha"], seen)

    def test_publish_honors_priority_order(self) -> None:
        bus = EventBus()
        seen: list[str] = []

        class ExampleEvent:
            pass

        bus.subscribe(ExampleEvent, lambda evt: seen.append("normal"), priority=100)
        bus.subscribe(ExampleEvent, lambda evt: seen.append("early"), priority=10)
        bus.subscribe(ExampleEvent, lambda evt: seen.append("late"), priority=200)

        bus.publish(ExampleEvent())

        self.assertEqual(["early", "normal", "late"], seen)

    def test_publish_preserves_registration_order_for_same_priority(self) -> None:
        bus = EventBus()
        seen: list[str] = []

        class ExampleEvent:
            pass

        bus.subscribe(ExampleEvent, lambda evt: seen.append("first"), priority=50)
        bus.subscribe(ExampleEvent, lambda evt: seen.append("second"), priority=50)

        bus.publish(ExampleEvent())

        self.assertEqual(["first", "second"], seen)

    def test_publish_continues_when_one_handler_raises(self) -> None:
        bus = EventBus()
        seen: list[str] = []

        class ExampleEvent:
            pass

        def _broken(_evt) -> None:
            raise RuntimeError("boom")

        bus.subscribe(ExampleEvent, _broken, priority=10)
        bus.subscribe(ExampleEvent, lambda evt: seen.append("still-runs"), priority=20)

        bus.publish(ExampleEvent())

        self.assertEqual(["still-runs"], seen)
        self.assertEqual(1, len(bus.last_publish_errors()))


class WorldProgressionTests(unittest.TestCase):
    def test_tick_advances_turns_and_persists_once(self) -> None:
        world_repo = _StubWorldRepository()
        entity_repo = _StubEntityRepository()
        events: list[TickAdvanced] = []
        bus = EventBus()
        bus.subscribe(TickAdvanced, lambda evt: events.append(evt))

        progression = WorldProgression(world_repo, entity_repo, bus)
        progression.tick(world_repo.world, ticks=3)

        self.assertEqual(3, world_repo.world.current_turn)
        self.assertEqual(1, len(world_repo.saved))
        self.assertEqual(1, len(events))
        self.assertEqual(3, events[0].turn_after)

    def test_cataclysm_clock_advances_phase_with_turns(self) -> None:
        world_repo = _StubWorldRepository()
        entity_repo = _StubEntityRepository()
        bus = EventBus()
        progression = WorldProgression(world_repo, entity_repo, bus)

        world_repo.world.flags = {
            "cataclysm_state": {
                "active": True,
                "kind": "plague",
                "phase": "whispers",
                "progress": 0,
                "seed": 111,
                "started_turn": 0,
                "last_advance_turn": 0,
            }
        }

        progression.tick(world_repo.world, ticks=30)
        state = world_repo.world.flags.get("cataclysm_state", {})
        self.assertGreater(int(state.get("progress", 0) or 0), 0)
        self.assertIn(str(state.get("phase", "")), {"whispers", "grip_tightens", "map_shrinks", "ruin"})

    def test_cataclysm_clock_is_deterministic_for_same_state(self) -> None:
        repo_a = _StubWorldRepository()
        repo_b = _StubWorldRepository()
        entity_repo = _StubEntityRepository()
        bus_a = EventBus()
        bus_b = EventBus()
        progression_a = WorldProgression(repo_a, entity_repo, bus_a)
        progression_b = WorldProgression(repo_b, entity_repo, bus_b)

        state = {
            "active": True,
            "kind": "tyrant",
            "phase": "whispers",
            "progress": 8,
            "seed": 222,
            "started_turn": 0,
            "last_advance_turn": 0,
        }
        repo_a.world.flags = {"cataclysm_state": dict(state)}
        repo_b.world.flags = {"cataclysm_state": dict(state)}

        progression_a.tick(repo_a.world, ticks=25)
        progression_b.tick(repo_b.world, ticks=25)

        self.assertEqual(
            repo_a.world.flags.get("cataclysm_state", {}),
            repo_b.world.flags.get("cataclysm_state", {}),
        )

    def test_cataclysm_clock_applies_slowdown_and_rollback_buffers(self) -> None:
        world_repo = _StubWorldRepository()
        entity_repo = _StubEntityRepository()
        bus = EventBus()
        progression = WorldProgression(world_repo, entity_repo, bus)

        world_repo.world.flags = {
            "cataclysm_state": {
                "active": True,
                "kind": "demon_king",
                "phase": "grip_tightens",
                "progress": 40,
                "seed": 333,
                "started_turn": 0,
                "last_advance_turn": 0,
                "slowdown_ticks": 4,
                "rollback_buffer": 8,
            }
        }

        progression.tick(world_repo.world, ticks=1)
        state = world_repo.world.flags.get("cataclysm_state", {})
        self.assertLessEqual(int(state.get("progress", 0) or 0), 40)
        self.assertLess(int(state.get("slowdown_ticks", 0) or 0), 4)

    def test_cataclysm_clock_uses_biome_severity_pressure_for_escalation(self) -> None:
        high_repo = _StubWorldRepository()
        low_repo = _StubWorldRepository()
        entity_repo = _StubEntityRepository()
        progression_high = WorldProgression(high_repo, entity_repo, EventBus())
        progression_low = WorldProgression(low_repo, entity_repo, EventBus())

        base_state = {
            "active": True,
            "kind": "plague",
            "phase": "whispers",
            "progress": 0,
            "seed": 444,
            "started_turn": 0,
            "last_advance_turn": 0,
        }
        high_repo.world.flags = {
            "cataclysm_focus_biome": "glacier",
            "cataclysm_state": dict(base_state),
        }
        low_repo.world.flags = {
            "cataclysm_focus_biome": "temperate_deciduous_forest",
            "cataclysm_state": dict(base_state),
        }

        dataset = type(
            "Dataset",
            (),
            {
                "biome_severity_index": {
                    "glacier": 95,
                    "temperate_deciduous_forest": 20,
                }
            },
        )()

        progression_high._REFERENCE_WORLD_DATASET_CACHE.clear()
        progression_low._REFERENCE_WORLD_DATASET_CACHE.clear()

        with mock.patch.object(WorldProgression, "_load_reference_world_dataset_cached", return_value=dataset):
            progression_high.tick(high_repo.world, ticks=12)
            progression_low.tick(low_repo.world, ticks=12)

        high_progress = int(high_repo.world.flags.get("cataclysm_state", {}).get("progress", 0) or 0)
        low_progress = int(low_repo.world.flags.get("cataclysm_state", {}).get("progress", 0) or 0)
        self.assertGreater(high_progress, low_progress)

    def test_faction_conflict_state_normalization_creates_bounded_v1_envelope(self) -> None:
        world_repo = _StubWorldRepository()
        entity_repo = _StubEntityRepository()
        progression = WorldProgression(world_repo, entity_repo, EventBus())

        world_repo.world.flags = {
            "faction_conflict_v1": {
                "active": "yes",
                "relations": {
                    " Wardens | Thieves_Guild ": {
                        "score": "17",
                        "stance": "allied",
                    }
                },
            }
        }

        state = progression._ensure_faction_conflict_state(world_repo.world)
        relation = dict(state.get("relations", {})).get("wardens|thieves_guild", {})

        self.assertEqual(1, int(state.get("version", 0) or 0))
        self.assertTrue(bool(state.get("active", False)))
        self.assertEqual(10, int(relation.get("score", 0) or 0))
        self.assertEqual("allied", str(relation.get("stance", "")))

    def test_faction_conflict_tick_is_deterministic_for_same_seed_and_state(self) -> None:
        repo_a = _StubWorldRepository()
        repo_b = _StubWorldRepository()
        entity_repo = _StubEntityRepository()
        progression_a = WorldProgression(repo_a, entity_repo, EventBus())
        progression_b = WorldProgression(repo_b, entity_repo, EventBus())

        base_state = {
            "version": 1,
            "active": True,
            "relations": {
                "wardens|thieves_guild": {
                    "score": 0,
                    "stance": "neutral",
                    "last_updated_turn": 0,
                },
                "the_crown|free_council": {
                    "score": 2,
                    "stance": "neutral",
                    "last_updated_turn": 0,
                },
            },
            "last_tick_turn": 0,
        }
        repo_a.world.flags = {"faction_conflict_v1": dict(base_state)}
        repo_b.world.flags = {"faction_conflict_v1": dict(base_state)}

        progression_a.tick(repo_a.world, ticks=12)
        progression_b.tick(repo_b.world, ticks=12)

        self.assertEqual(
            repo_a.world.flags.get("faction_conflict_v1", {}),
            repo_b.world.flags.get("faction_conflict_v1", {}),
        )

    def test_faction_conflict_compact_summary_signature_is_stable_for_identical_runs(self) -> None:
        repo_a = _StubWorldRepository()
        repo_b = _StubWorldRepository()
        entity_repo = _StubEntityRepository()
        progression_a = WorldProgression(repo_a, entity_repo, EventBus())
        progression_b = WorldProgression(repo_b, entity_repo, EventBus())

        base_state = {
            "version": 1,
            "active": True,
            "relations": {
                "wardens|thieves_guild": {
                    "score": -3,
                    "stance": "neutral",
                    "last_updated_turn": 0,
                },
                "the_crown|free_council": {
                    "score": 4,
                    "stance": "allied",
                    "last_updated_turn": 0,
                },
            },
            "last_tick_turn": 0,
        }
        repo_a.world.flags = {"faction_conflict_v1": dict(base_state)}
        repo_b.world.flags = {"faction_conflict_v1": dict(base_state)}

        progression_a.tick(repo_a.world, ticks=10)
        progression_b.tick(repo_b.world, ticks=10)

        def compact_signature(world: World) -> tuple[str, int, str]:
            state = dict((world.flags or {}).get("faction_conflict_v1", {}))
            relations = dict(state.get("relations", {}))
            pair = ""
            score = -1
            stance = ""
            for raw_pair, raw_payload in relations.items():
                payload = raw_payload if isinstance(raw_payload, dict) else {}
                relation_score = abs(int(payload.get("score", 0) or 0))
                if relation_score > score:
                    pair = str(raw_pair)
                    score = relation_score
                    stance = str(payload.get("stance", ""))
            return pair, score, stance

        self.assertEqual(compact_signature(repo_a.world), compact_signature(repo_b.world))

    def test_crafting_state_normalization_creates_bounded_v1_envelope(self) -> None:
        world_repo = _StubWorldRepository()
        entity_repo = _StubEntityRepository()
        progression = WorldProgression(world_repo, entity_repo, EventBus())

        world_repo.world.flags = {
            "crafting_v1": {
                "active": "yes",
                "professions": {
                    "gathering": "120",
                    "refining": -9,
                    "fieldcraft": "5",
                },
                "known_recipes": [" Healing Herbs ", "healing herbs", "Whetstone"],
                "stockpile": {" Raw Ore ": "7", "Spoiled": -3},
                "last_tick_turn": "2",
            }
        }

        state = progression._ensure_crafting_state(world_repo.world)

        self.assertEqual(1, int(state.get("version", 0) or 0))
        self.assertTrue(bool(state.get("active", False)))
        professions = dict(state.get("professions", {}))
        self.assertEqual(100, int(professions.get("gathering", 0) or 0))
        self.assertEqual(0, int(professions.get("refining", 0) or 0))
        self.assertEqual(5, int(professions.get("fieldcraft", 0) or 0))
        self.assertEqual(["healing_herbs", "whetstone"], list(state.get("known_recipes", [])))
        self.assertEqual({"raw_ore": 7}, dict(state.get("stockpile", {})))

    def test_crafting_state_signature_is_stable_for_identical_runs(self) -> None:
        repo_a = _StubWorldRepository()
        repo_b = _StubWorldRepository()
        entity_repo = _StubEntityRepository()
        progression_a = WorldProgression(repo_a, entity_repo, EventBus())
        progression_b = WorldProgression(repo_b, entity_repo, EventBus())

        base_state = {
            "version": 1,
            "active": True,
            "professions": {
                "gathering": 3,
                "refining": 2,
                "fieldcraft": 1,
            },
            "known_recipes": ["healing_herbs", "whetstone"],
            "stockpile": {
                "raw_ore": 4,
                "wild_herbs": 2,
            },
            "last_tick_turn": 0,
            "last_craft_turn": 0,
        }
        repo_a.world.flags = {"crafting_v1": dict(base_state)}
        repo_b.world.flags = {"crafting_v1": dict(base_state)}

        progression_a.tick(repo_a.world, ticks=24)
        progression_b.tick(repo_b.world, ticks=24)

        self.assertEqual(
            repo_a.world.flags.get("crafting_v1", {}),
            repo_b.world.flags.get("crafting_v1", {}),
        )


if __name__ == "__main__":
    unittest.main()
