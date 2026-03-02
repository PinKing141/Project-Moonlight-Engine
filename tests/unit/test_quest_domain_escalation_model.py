import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.domain.models.quest import (
    quest_acceptance_block_reason,
    quest_escalation_path_for,
    quest_payload_from_template,
    quest_template_for,
    quest_title_for,
)


class QuestDomainEscalationModelTests(unittest.TestCase):
    def test_forest_path_clearance_has_typed_escalation_path(self) -> None:
        profile = quest_escalation_path_for("forest_path_clearance")

        self.assertIsNotNone(profile)
        assert profile is not None
        self.assertEqual(30, int(profile.expires_days))
        self.assertEqual(2, len(profile.nodes))

        first = profile.nodes[0]
        self.assertEqual("escalated", first.state)
        self.assertEqual(14, int(first.offset_days))
        self.assertIn("hostages", first.objective_note.lower())

        second = profile.nodes[1]
        self.assertEqual("failed", second.state)
        self.assertEqual("wardens", str(second.failure_faction_id or ""))
        self.assertLess(int(second.failure_reputation_delta), 0)

    def test_unknown_quest_returns_no_escalation_profile(self) -> None:
        self.assertIsNone(quest_escalation_path_for("unknown_quest"))


class QuestDomainTemplateModelTests(unittest.TestCase):
    def test_template_lookup_contains_standard_and_cataclysm_metadata(self) -> None:
        forest = quest_template_for("forest_path_clearance")
        self.assertIsNotNone(forest)
        assert forest is not None
        self.assertFalse(bool(forest.cataclysm_pushback))
        self.assertEqual(30, int(forest.expires_days))

        apex = quest_template_for("cataclysm_apex_clash")
        self.assertIsNotNone(apex)
        assert apex is not None
        self.assertTrue(bool(apex.cataclysm_pushback))
        self.assertTrue(bool(apex.is_apex_objective))
        self.assertEqual(3, int(apex.pushback_tier))

    def test_payload_builder_projects_runtime_fields(self) -> None:
        template = quest_template_for("cataclysm_alliance_accord")
        self.assertIsNotNone(template)
        assert template is not None

        payload = quest_payload_from_template(template, cataclysm_kind="plague", cataclysm_phase="grip_tightens")
        self.assertEqual("cataclysm_alliance_accord", payload["quest_id"])
        self.assertEqual("kill_any", payload["objective_kind"])
        self.assertEqual("plague", payload["pushback_focus"])
        self.assertEqual("grip_tightens", payload["phase"])
        self.assertEqual(10, int(payload["requires_alliance_reputation"]))
        self.assertEqual(2, int(payload["requires_alliance_count"]))

    def test_title_lookup_uses_template_then_fallback(self) -> None:
        self.assertEqual("First Hunt", quest_title_for("first_hunt"))
        self.assertEqual("Unknown Quest", quest_title_for("unknown_quest"))

    def test_acceptance_block_reason_applies_alliance_requirements(self) -> None:
        template = quest_template_for("cataclysm_alliance_accord")
        self.assertIsNotNone(template)
        assert template is not None

        blocked = quest_acceptance_block_reason(
            template,
            faction_standings={
                "wardens": 10,
                "tower_crimson": 5,
            },
        )
        self.assertIn("alliance standing 10+", blocked)

        allowed = quest_acceptance_block_reason(
            template,
            faction_standings={
                "wardens": 12,
                "tower_crimson": 10,
            },
        )
        self.assertEqual("", allowed)


if __name__ == "__main__":
    unittest.main()
