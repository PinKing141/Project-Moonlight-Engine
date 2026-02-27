import json
import os
import sys
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.event_bus import EventBus
from rpg.application.services.game_service import GameService
from rpg.application.services.narrative_quality_batch import (
    quality_profile_thresholds as shared_quality_profile_thresholds,
    quality_targets as shared_quality_targets,
    resolved_quality_profiles as shared_resolved_quality_profiles,
)
from rpg.application.services.story_director import register_story_director_handlers
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


class NarrativeSimulationBatchTests(unittest.TestCase):
    SCRIPT = [
        "rest",
        "rumour",
        "travel",
        "rest",
        "social",
        "travel",
        "rest",
        "rumour",
        "explore",
        "social",
        "rest",
        "travel",
        "rest",
        "travel",
        "rumour",
        "rest",
    ]

    @staticmethod
    def _build_service(seed: int) -> tuple[GameService, int]:
        event_bus = EventBus()
        world_repo = InMemoryWorldRepository(seed=seed)
        world = world_repo.load_default()
        world.threat_level = 7
        world_repo.save(world)

        character = Character(id=901, name="BatchHero", location_id=1)
        character.attributes["charisma"] = 14
        character.attributes["wisdom"] = 14
        character_repo = InMemoryCharacterRepository({character.id: character})

        entities = [
            Entity(id=1, name="Wolf", level=1, hp=6, faction_id="wild"),
            Entity(id=2, name="Bandit", level=2, hp=8, faction_id="wardens"),
            Entity(id=3, name="Ghoul", level=2, hp=9, faction_id="undead"),
        ]
        entity_repo = InMemoryEntityRepository(entities)
        entity_repo.set_location_entities(2, [1, 2, 3])

        location_repo = InMemoryLocationRepository(
            {
                1: Location(id=1, name="Town Square", tags=["town"], factions=["wardens"]),
                2: Location(id=2, name="North Wilds", tags=["wilderness"], factions=["wild"]),
            }
        )

        faction_repo = InMemoryFactionRepository()
        progression = WorldProgression(world_repo, entity_repo, event_bus)
        register_story_director_handlers(event_bus=event_bus, world_repo=world_repo, cadence_turns=2)

        service = GameService(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
            progression=progression,
            faction_repo=faction_repo,
        )
        return service, character.id

    @classmethod
    def _quality_targets(cls) -> dict:
        return shared_quality_targets()

    @classmethod
    def _semantic_arc_score(cls, *, summary: dict) -> tuple[int, str]:
        tension = int(summary.get("tension_level", 0))
        resolved = int(summary.get("story_seed_resolved", 0))
        active = int(summary.get("story_seed_active", 0))
        major_events = int(summary.get("major_event_count", 0))
        injection_count = int(summary.get("injection_count", 0))
        injection_kinds = tuple(summary.get("injection_kinds", ()))
        unique_categories = len({str(kind) for kind in injection_kinds if str(kind)})

        score = 0
        score += min(25, resolved * 12)
        score += min(20, major_events * 8)
        score += min(15, max(0, injection_count - 1) * 3)
        score += min(15, unique_categories * 7)

        if 40 <= tension <= 75:
            score += 15
        elif 25 <= tension <= 90:
            score += 8

        if active == 0:
            score += 10
        elif active == 1:
            score += 5
        else:
            score -= min(10, (active - 1) * 4)

        score = max(0, min(100, int(score)))
        if score >= 75:
            band = "strong"
        elif score >= 50:
            band = "stable"
        elif score >= 30:
            band = "fragile"
        else:
            band = "weak"
        return score, band

    @classmethod
    def _quality_alerts(cls, *, summary: dict) -> tuple[str, ...]:
        alerts: list[str] = []
        targets = cls._quality_targets()
        semantic_score = int(summary.get("semantic_arc_score", 0))
        tension = int(summary.get("tension_level", 0))
        active = int(summary.get("story_seed_active", 0))
        major_events = int(summary.get("major_event_count", 0))

        if semantic_score < int(targets["semantic_min"]):
            alerts.append("semantic_below_target")
        if tension < int(targets["tension_min"]):
            alerts.append("tension_under_target")
        if tension > int(targets["tension_max"]):
            alerts.append("tension_over_target")
        if active > int(targets["max_active_seeds"]):
            alerts.append("too_many_active_seeds")
        if major_events < int(targets["min_major_events"]):
            alerts.append("low_event_density")
        return tuple(alerts)

    @classmethod
    def _quality_status(cls, *, alerts: tuple[str, ...]) -> str:
        if not alerts:
            return "pass"
        if "semantic_below_target" in alerts and "low_event_density" in alerts:
            return "fail"
        return "warn"

    @classmethod
    def _quality_profile_thresholds(cls, profile: str) -> dict:
        return shared_quality_profile_thresholds(profile)

    @classmethod
    def _batch_quality_gate(cls, summaries: list[dict], profile: str = "balanced") -> dict:
        thresholds = cls._quality_profile_thresholds(profile)
        total = len(summaries)
        pass_count = sum(1 for row in summaries if str(row.get("quality_status", "")) == "pass")
        warn_count = sum(1 for row in summaries if str(row.get("quality_status", "")) == "warn")
        fail_count = sum(1 for row in summaries if str(row.get("quality_status", "")) == "fail")
        pass_rate = (pass_count / total) if total > 0 else 0.0

        blockers: list[str] = []
        if fail_count > thresholds["max_fail_count"]:
            blockers.append("too_many_failures")
        if pass_rate < thresholds["min_pass_rate"]:
            blockers.append("pass_rate_below_target")
        if warn_count > thresholds["max_warn_count"]:
            blockers.append("too_many_warnings")

        verdict = "go" if not blockers else "hold"
        return {
            "profile": thresholds["profile"],
            "total": int(total),
            "pass_count": int(pass_count),
            "warn_count": int(warn_count),
            "fail_count": int(fail_count),
            "pass_rate": round(float(pass_rate), 4),
            "target_min_pass_rate": float(thresholds["min_pass_rate"]),
            "target_max_warn_count": int(thresholds["max_warn_count"]),
            "target_max_fail_count": int(thresholds["max_fail_count"]),
            "blockers": tuple(blockers),
            "release_verdict": verdict,
        }

    @classmethod
    def _simulate_arc(cls, seed: int, script: list[str]) -> dict:
        service, character_id = cls._build_service(seed)
        rumour_ids: list[str] = []

        for action in script:
            if action == "rest":
                service.rest_intent(character_id)
            elif action == "travel":
                service.travel_intent(character_id)
            elif action == "social":
                service.submit_social_approach_intent(character_id, "broker_silas", "Friendly")
            elif action == "rumour":
                board = service.get_rumour_board_intent(character_id)
                rumour_ids = [item.rumour_id for item in board.items]
            elif action == "explore":
                service.explore(character_id)
            else:
                raise ValueError(f"Unknown simulation action: {action}")

        world = service._require_world()
        narrative = world.flags.get("narrative", {}) if isinstance(world.flags, dict) else {}
        injections = narrative.get("injections", []) if isinstance(narrative, dict) else []
        story_seeds = narrative.get("story_seeds", []) if isinstance(narrative, dict) else []
        major_events = narrative.get("major_events", []) if isinstance(narrative, dict) else []

        resolved = 0
        active = 0
        for row in story_seeds:
            if not isinstance(row, dict):
                continue
            status = str(row.get("status", ""))
            if status == "resolved":
                resolved += 1
            if status in {"active", "simmering", "escalated", "critical"}:
                active += 1

        summary = {
            "seed": int(seed),
            "script_len": len(script),
            "final_turn": int(getattr(world, "current_turn", 0)),
            "threat_level": int(getattr(world, "threat_level", 0)),
            "tension_level": int(narrative.get("tension_level", 0)) if isinstance(narrative, dict) else 0,
            "injection_count": len([row for row in injections if isinstance(row, dict)]),
            "injection_kinds": tuple(
                str(row.get("kind", "")) for row in injections if isinstance(row, dict)
            ),
            "story_seed_total": len([row for row in story_seeds if isinstance(row, dict)]),
            "story_seed_resolved": int(resolved),
            "story_seed_active": int(active),
            "major_event_count": len([row for row in major_events if isinstance(row, dict)]),
            "rumour_signature": tuple(rumour_ids),
        }
        semantic_score, semantic_band = cls._semantic_arc_score(summary=summary)
        summary["semantic_arc_score"] = int(semantic_score)
        summary["semantic_arc_band"] = semantic_band
        alerts = cls._quality_alerts(summary=summary)
        summary["quality_alerts"] = alerts
        summary["quality_status"] = cls._quality_status(alerts=alerts)
        return summary

    @classmethod
    def _run_batch(cls, seeds: list[int], script: list[str]) -> list[dict]:
        return [cls._simulate_arc(seed, script) for seed in seeds]

    def test_fixed_seed_batch_produces_arc_summaries(self) -> None:
        summaries = self._run_batch([101, 202, 303], self.SCRIPT)
        self.assertEqual(3, len(summaries))

        for summary in summaries:
            self.assertGreater(summary["final_turn"], 0)
            self.assertGreaterEqual(summary["injection_count"], 1)
            self.assertIn("rumour_signature", summary)
            self.assertGreaterEqual(summary["semantic_arc_score"], 0)
            self.assertLessEqual(summary["semantic_arc_score"], 100)
            self.assertIn(summary["semantic_arc_band"], {"weak", "fragile", "stable", "strong"})
            self.assertIn(summary["quality_status"], {"pass", "warn", "fail"})
            self.assertIsInstance(summary["quality_alerts"], tuple)

        gate = self._batch_quality_gate(summaries)
        self.assertEqual("balanced", gate["profile"])
        self.assertEqual(3, gate["total"])
        self.assertIn(gate["release_verdict"], {"go", "hold"})
        self.assertIn("blockers", gate)

    def test_batch_replay_is_deterministic_for_same_seed_and_script(self) -> None:
        run_a = self._run_batch([111, 222, 333], self.SCRIPT)
        run_b = self._run_batch([111, 222, 333], self.SCRIPT)
        self.assertEqual(run_a, run_b)

    def test_batch_quality_gate_is_deterministic_for_same_seed_and_script(self) -> None:
        run_a = self._run_batch([111, 222, 333], self.SCRIPT)
        run_b = self._run_batch([111, 222, 333], self.SCRIPT)
        gate_a = self._batch_quality_gate(run_a, profile="strict")
        gate_b = self._batch_quality_gate(run_b, profile="strict")

        self.assertEqual(gate_a, gate_b)

    def test_quality_gate_profiles_yield_profile_specific_verdicts(self) -> None:
        summaries = self._run_batch([101, 202, 303], self.SCRIPT)
        strict_gate = self._batch_quality_gate(summaries, profile="strict")
        balanced_gate = self._batch_quality_gate(summaries, profile="balanced")
        exploratory_gate = self._batch_quality_gate(summaries, profile="exploratory")

        self.assertEqual("strict", strict_gate["profile"])
        self.assertEqual("balanced", balanced_gate["profile"])
        self.assertEqual("exploratory", exploratory_gate["profile"])
        self.assertIn(strict_gate["release_verdict"], {"go", "hold"})
        self.assertIn(balanced_gate["release_verdict"], {"go", "hold"})
        self.assertIn(exploratory_gate["release_verdict"], {"go", "hold"})
        self.assertGreaterEqual(float(exploratory_gate["target_min_pass_rate"]), 0.0)
        self.assertLessEqual(float(exploratory_gate["target_min_pass_rate"]), 1.0)
        self.assertGreaterEqual(float(balanced_gate["target_min_pass_rate"]), float(exploratory_gate["target_min_pass_rate"]))
        self.assertGreaterEqual(float(strict_gate["target_min_pass_rate"]), float(balanced_gate["target_min_pass_rate"]))
        self.assertLessEqual(int(exploratory_gate["target_max_warn_count"]), int(exploratory_gate["total"]))
        self.assertLessEqual(int(balanced_gate["target_max_warn_count"]), int(balanced_gate["total"]))
        self.assertLessEqual(int(strict_gate["target_max_warn_count"]), int(strict_gate["total"]))

    def test_default_profile_can_be_selected_via_environment(self) -> None:
        summaries = self._run_batch([101, 202, 303], self.SCRIPT)
        with patch.dict(os.environ, {"RPG_NARRATIVE_GATE_DEFAULT_PROFILE": "strict"}, clear=False):
            gate = self._batch_quality_gate(summaries, profile="")
            explicit = self._batch_quality_gate(summaries, profile="strict")
        self.assertEqual("strict", gate["profile"])
        self.assertEqual(explicit, gate)

    def test_profile_thresholds_can_be_overridden_via_environment(self) -> None:
        summaries = self._run_batch([101, 202, 303], self.SCRIPT)
        with patch.dict(
            os.environ,
            {
                "RPG_NARRATIVE_GATE_STRICT_MIN_PASS_RATE": "0.60",
                "RPG_NARRATIVE_GATE_STRICT_MAX_WARN_COUNT": "1",
                "RPG_NARRATIVE_GATE_STRICT_MAX_FAIL_COUNT": "0",
            },
            clear=False,
        ):
            strict_gate = self._batch_quality_gate(summaries, profile="strict")
        self.assertEqual("go", strict_gate["release_verdict"])

    def test_profiles_can_be_loaded_from_json_file(self) -> None:
        summaries = self._run_batch([101, 202, 303], self.SCRIPT)
        payload = {
            "profiles": {
                "strict": {
                    "min_pass_rate": 0.6,
                    "max_warn_count": 1,
                    "max_fail_count": 0,
                }
            }
        }

        fd, path = tempfile.mkstemp(suffix=".json")
        try:
            os.close(fd)
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle)
            with patch.dict(os.environ, {"RPG_NARRATIVE_GATE_PROFILE_FILE": path}, clear=False):
                strict_gate = self._batch_quality_gate(summaries, profile="strict")
            self.assertEqual("go", strict_gate["release_verdict"])
        finally:
            try:
                os.remove(path)
            except OSError:
                pass

    def test_config_resolution_matches_runtime_service(self) -> None:
        with patch.dict(
            os.environ,
            {
                "RPG_NARRATIVE_GATE_DEFAULT_PROFILE": "strict",
                "RPG_NARRATIVE_GATE_TARGET_SEMANTIC_MIN": "60",
                "RPG_NARRATIVE_GATE_STRICT_MIN_PASS_RATE": "0.75",
            },
            clear=False,
        ):
            targets = self._quality_targets()
            profiles = shared_resolved_quality_profiles()
            thresholds = self._quality_profile_thresholds("")
            shared_targets = shared_quality_targets()
            shared_profiles = shared_resolved_quality_profiles()

        self.assertEqual(shared_targets, targets)
        self.assertEqual(shared_profiles, profiles)
        self.assertEqual("strict", thresholds["profile"])
        self.assertEqual(0.75, thresholds["min_pass_rate"])


if __name__ == "__main__":
    unittest.main()
