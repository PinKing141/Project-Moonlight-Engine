import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.event_bus import EventBus
from rpg.application.services.story_director import register_story_director_handlers
from rpg.application.services.world_progression import WorldProgression
from rpg.infrastructure.db.inmemory.repos import InMemoryEntityRepository, InMemoryWorldRepository


class StoryDirectorTests(unittest.TestCase):
    def _build(self, seed: int = 9):
        event_bus = EventBus()
        world_repo = InMemoryWorldRepository(seed=seed)
        entity_repo = InMemoryEntityRepository([])
        progression = WorldProgression(world_repo, entity_repo, event_bus)
        register_story_director_handlers(event_bus=event_bus, world_repo=world_repo, cadence_turns=3)
        return world_repo, progression

    def test_tick_updates_narrative_tension_bounds(self):
        world_repo, progression = self._build()
        world = world_repo.load_default()
        world.threat_level = 4
        world_repo.save(world)

        progression.tick(world_repo.load_default(), ticks=1)
        updated = world_repo.load_default()

        narrative = updated.flags.get("narrative", {})
        tension = int(narrative.get("tension_level", -1))
        self.assertGreaterEqual(tension, 0)
        self.assertLessEqual(tension, 100)

    def test_cadence_markers_are_deterministic_for_same_seed(self):
        repo_a, progression_a = self._build(seed=15)
        repo_b, progression_b = self._build(seed=15)

        for _ in range(12):
            progression_a.tick(repo_a.load_default(), ticks=1)
            progression_b.tick(repo_b.load_default(), ticks=1)

        markers_a = repo_a.load_default().flags.get("narrative", {}).get("injections", [])
        markers_b = repo_b.load_default().flags.get("narrative", {}).get("injections", [])

        self.assertEqual(markers_a, markers_b)

    def test_cadence_respects_minimum_spacing(self):
        world_repo, progression = self._build(seed=22)

        for _ in range(20):
            progression.tick(world_repo.load_default(), ticks=1)

        markers = world_repo.load_default().flags.get("narrative", {}).get("injections", [])
        turns = [int(row.get("turn", 0)) for row in markers if isinstance(row, dict)]
        for left, right in zip(turns, turns[1:]):
            self.assertGreaterEqual(right - left, 3)

    def test_recent_consequences_raise_tension(self):
        world_repo, progression = self._build(seed=33)
        baseline_world = world_repo.load_default()
        baseline_world.threat_level = 2
        world_repo.save(baseline_world)
        progression.tick(world_repo.load_default(), ticks=1)
        base_tension = int(world_repo.load_default().flags.get("narrative", {}).get("tension_level", 0))

        world = world_repo.load_default()
        world.flags.setdefault("consequences", [])
        world.flags["consequences"].append(
            {
                "kind": "test_pressure",
                "message": "Pressure rises",
                "severity": "normal",
                "turn": world.current_turn,
            }
        )
        world_repo.save(world)

        progression.tick(world_repo.load_default(), ticks=1)
        raised_tension = int(world_repo.load_default().flags.get("narrative", {}).get("tension_level", 0))

        self.assertGreater(raised_tension, base_tension)

    def test_recent_flashpoint_echoes_raise_tension(self):
        world_repo, progression = self._build(seed=34)
        baseline_world = world_repo.load_default()
        baseline_world.threat_level = 2
        world_repo.save(baseline_world)
        progression.tick(world_repo.load_default(), ticks=1)
        base_tension = int(world_repo.load_default().flags.get("narrative", {}).get("tension_level", 0))

        world = world_repo.load_default()
        world.flags.setdefault("narrative", {})
        world.flags["narrative"]["flashpoint_echoes"] = [
            {
                "turn": world.current_turn,
                "seed_id": "seed_2_1111",
                "resolution": "faction_shift",
                "channel": "combat",
                "bias_faction": "wardens",
                "rival_faction": "wild",
                "affected_factions": 3,
                "severity_score": 86,
                "severity_band": "critical",
            }
        ]
        world_repo.save(world)

        progression.tick(world_repo.load_default(), ticks=1)
        raised_tension = int(world_repo.load_default().flags.get("narrative", {}).get("tension_level", 0))
        self.assertGreater(raised_tension, base_tension)

    def test_relationship_graph_is_initialized_and_history_bounded(self):
        world_repo, progression = self._build(seed=44)

        for _ in range(60):
            progression.tick(world_repo.load_default(), ticks=1)

        narrative = world_repo.load_default().flags.get("narrative", {})
        graph = narrative.get("relationship_graph", {})
        self.assertTrue(graph)

        edges = graph.get("faction_edges", {})
        self.assertIn("undead|wardens", edges)
        self.assertIn("undead|wild", edges)
        self.assertIn("wardens|wild", edges)

        history = graph.get("history", [])
        self.assertLessEqual(len(history), 30)

    def test_relationship_graph_updates_are_deterministic_for_same_seed(self):
        repo_a, progression_a = self._build(seed=51)
        repo_b, progression_b = self._build(seed=51)

        for _ in range(24):
            progression_a.tick(repo_a.load_default(), ticks=1)
            progression_b.tick(repo_b.load_default(), ticks=1)

        graph_a = repo_a.load_default().flags.get("narrative", {}).get("relationship_graph", {})
        graph_b = repo_b.load_default().flags.get("narrative", {}).get("relationship_graph", {})
        self.assertEqual(graph_a, graph_b)

    def test_story_seed_schema_is_created_on_injection(self):
        world_repo, progression = self._build(seed=63)
        world = world_repo.load_default()
        world.threat_level = 8
        world_repo.save(world)

        for _ in range(30):
            progression.tick(world_repo.load_default(), ticks=1)

        narrative = world_repo.load_default().flags.get("narrative", {})
        rows = narrative.get("story_seeds", [])
        self.assertTrue(rows)

        seed = rows[-1]
        for key in (
            "seed_id",
            "kind",
            "status",
            "initiator",
            "motivation",
            "pressure",
            "opportunity",
            "escalation_stage",
            "escalation_path",
            "resolution_variants",
            "narrative_tags",
            "created_turn",
            "last_update_turn",
        ):
            self.assertIn(key, seed)

    def test_injection_markers_use_multiple_event_categories(self):
        world_repo, progression = self._build(seed=77)
        world = world_repo.load_default()
        world.threat_level = 9
        world_repo.save(world)

        for _ in range(80):
            progression.tick(world_repo.load_default(), ticks=1)

        markers = world_repo.load_default().flags.get("narrative", {}).get("injections", [])
        kinds = {str(row.get("kind")) for row in markers if isinstance(row, dict)}
        self.assertIn("story_seed", kinds)
        self.assertIn("faction_flashpoint", kinds)

    def test_repetition_guard_prevents_short_window_category_spam(self):
        world_repo, progression = self._build(seed=88)
        world = world_repo.load_default()
        world.threat_level = 10
        world_repo.save(world)

        for _ in range(90):
            progression.tick(world_repo.load_default(), ticks=1)

        markers = world_repo.load_default().flags.get("narrative", {}).get("injections", [])
        normalized = [
            (int(row.get("turn", 0)), str(row.get("kind", "")))
            for row in markers
            if isinstance(row, dict)
        ]
        for left, right in zip(normalized, normalized[1:]):
            left_turn, left_kind = left
            right_turn, right_kind = right
            if right_turn - left_turn <= 6:
                self.assertNotEqual(left_kind, right_kind)


if __name__ == "__main__":
    unittest.main()
