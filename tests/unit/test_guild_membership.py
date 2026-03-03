import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.domain.services.guild_membership import (
    GUILD_SCHEMA_VERSION,
    default_guild_membership_payload,
    evaluate_tier_promotion,
    normalize_guild_membership_payload,
    portable_reputation_score,
)


class GuildMembershipTests(unittest.TestCase):
    def test_default_payload_matches_schema_defaults(self) -> None:
        payload = default_guild_membership_payload()
        self.assertEqual(GUILD_SCHEMA_VERSION, payload.get("version"))
        self.assertEqual("none", payload.get("membership_status"))
        self.assertEqual("bronze", payload.get("rank_tier"))
        self.assertEqual("solo", payload.get("role_mode"))
        self.assertEqual(0, payload.get("reputation_global"))
        self.assertEqual({}, payload.get("reputation_by_region"))
        self.assertEqual(0, payload.get("merits"))

    def test_normalize_payload_defaults_unknown_enum_values(self) -> None:
        payload = {
            "version": "guild_v9",
            "membership_status": "captain",
            "rank_tier": "obsidian",
            "role_mode": "raid_leader",
            "reputation_global": "12",
            "reputation_by_region": {"northwatch": "8", "": 3, "bay": "oops"},
            "merits": "-4",
        }

        state, warnings = normalize_guild_membership_payload(payload)

        self.assertEqual("guild_v1", state.version)
        self.assertEqual("none", state.membership_status)
        self.assertEqual("bronze", state.rank_tier)
        self.assertEqual("solo", state.role_mode)
        self.assertEqual(12, state.reputation_global)
        self.assertEqual({"northwatch": 8}, state.reputation_by_region)
        self.assertEqual(0, state.merits)
        self.assertGreaterEqual(len(warnings), 4)

    def test_portable_reputation_score_uses_baseline_ratio(self) -> None:
        self.assertEqual(70, portable_reputation_score(100))
        self.assertEqual(35, portable_reputation_score(50))
        self.assertEqual(-14, portable_reputation_score(-20))

    def test_promotion_evaluator_reports_explicit_unmet_criteria(self) -> None:
        result = evaluate_tier_promotion(
            current_tier="bronze",
            completed_contracts=3,
            recent_contract_results=[True, False, "success", "failed"],
            reputation_global=4,
            reputation_by_region={"north": 2},
            conduct_score=20,
            role_competency_score=10,
        )

        self.assertEqual("silver", result.get("target_tier"))
        self.assertFalse(bool(result.get("eligible")))
        unmet = tuple(result.get("unmet_criteria", ()))
        self.assertGreaterEqual(len(unmet), 4)
        self.assertTrue(any("Completed contracts" in item for item in unmet))
        self.assertTrue(any("Recent success ratio" in item for item in unmet))

    def test_promotion_evaluator_passes_when_all_thresholds_are_met(self) -> None:
        result = evaluate_tier_promotion(
            current_tier="bronze",
            completed_contracts=10,
            recent_contract_results=[True] * 9 + [False],
            reputation_global=12,
            reputation_by_region={"north": 8, "east": 5},
            conduct_score=50,
            role_competency_score=32,
        )

        self.assertEqual("silver", result.get("target_tier"))
        self.assertTrue(bool(result.get("eligible")))
        self.assertEqual((), result.get("unmet_criteria"))

    def test_promotion_evaluator_blocks_when_at_max_tier(self) -> None:
        result = evaluate_tier_promotion(
            current_tier="platinum",
            completed_contracts=999,
            recent_contract_results=[True] * 30,
            reputation_global=999,
            reputation_by_region={"north": 999},
            conduct_score=100,
            role_competency_score=100,
        )

        self.assertIsNone(result.get("target_tier"))
        self.assertFalse(bool(result.get("eligible")))


if __name__ == "__main__":
    unittest.main()