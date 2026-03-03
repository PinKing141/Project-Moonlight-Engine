import sys
from pathlib import Path
from typing import Any, cast
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.domain.models.quest import QuestObjectiveKind
from rpg.domain.services.quest_template_catalog import (
    QUEST_TEMPLATE_SCHEMA_VERSION,
    build_template_from_payload,
    normalize_template_payload,
)
from rpg.infrastructure.inmemory.inmemory_quest_template_repo import InMemoryQuestTemplateRepository


class QuestTemplateCatalogTests(unittest.TestCase):
    def test_normalize_template_payload_applies_version_defaults_and_safe_fallback(self) -> None:
        normalized, warnings = normalize_template_payload(
            {
                "template_version": "quest_template_v9",
                "slug": "",
                "objective": {"kind": "unknown_kind", "target_key": "  ", "target_count": "x"},
                "reward_xp": "11",
                "reward_money": "7",
                "expires_days": 0,
            }
        )
        normalized_any = cast(dict[str, Any], normalized)
        objective_any = cast(dict[str, Any], normalized_any["objective"])

        self.assertEqual(QUEST_TEMPLATE_SCHEMA_VERSION, normalized_any["template_version"])
        self.assertEqual("", normalized_any["slug"])
        self.assertEqual("hunt", objective_any["kind"])
        self.assertEqual(1, int(objective_any["target_count"]))
        self.assertEqual(11, int(normalized_any["reward_xp"]))
        self.assertEqual(7, int(normalized_any["reward_money"]))
        self.assertEqual(1, int(normalized_any["expires_days"]))
        self.assertTrue(warnings)

    def test_build_template_from_payload_ignores_unknown_fields(self) -> None:
        template, warnings = build_template_from_payload(
            {
                "template_version": "quest_template_v1",
                "slug": "frontier_retrieval",
                "title": "Frontier Retrieval",
                "objective": {"kind": "gather", "target_key": "artifact", "target_count": 2},
                "reward_xp": 15,
                "reward_money": 9,
                "tags": ["retrieval", "frontier"],
                "unknown_field": "ignored",
            }
        )

        self.assertIsNotNone(template)
        assert template is not None
        self.assertEqual("frontier_retrieval", template.slug)
        self.assertEqual(QuestObjectiveKind.GATHER, template.objective.kind)
        self.assertEqual(("retrieval", "frontier"), template.tags)
        self.assertTrue(any("Unsupported template fields ignored" in row for row in warnings))


class InMemoryQuestTemplateRepositoryTests(unittest.TestCase):
    def test_loader_skips_malformed_rows_and_keeps_valid_templates(self) -> None:
        repo = InMemoryQuestTemplateRepository(
            payload_rows=[
                {
                    "template_version": "quest_template_v1",
                    "slug": "",
                    "objective": {"kind": "hunt", "target_key": "any_hostile", "target_count": 1},
                },
                {
                    "template_version": "quest_template_v1",
                    "slug": "deep_recon",
                    "title": "Deep Recon",
                    "objective": {"kind": "travel", "target_key": "route_leg", "target_count": 2},
                    "tags": ["recon", "biome:forest"],
                    "cataclysm_pushback": False,
                },
            ]
        )

        self.assertIsNotNone(repo.get_template("deep_recon"))
        self.assertIsNone(repo.get_template(""))
        self.assertTrue(repo.last_warnings)

    def test_filtering_supports_cataclysm_and_tag_constraints(self) -> None:
        repo = InMemoryQuestTemplateRepository(
            payload_rows=[
                {
                    "template_version": "quest_template_v1",
                    "slug": "regional_escort",
                    "title": "Regional Escort",
                    "objective": {"kind": "travel", "target_key": "route_leg", "target_count": 3},
                    "tags": ["escort", "region"],
                    "cataclysm_pushback": False,
                },
                {
                    "template_version": "quest_template_v1",
                    "slug": "cataclysm_front",
                    "title": "Cataclysm Front",
                    "objective": {"kind": "hunt", "target_key": "any_hostile", "target_count": 3},
                    "tags": ["hunt", "cataclysm"],
                    "cataclysm_pushback": True,
                },
            ]
        )

        standard = repo.list_templates(include_cataclysm=False)
        cataclysm = repo.list_templates(include_cataclysm=True)
        escort = repo.list_templates(include_cataclysm=False, required_tags=["escort"], forbidden_tags=["cataclysm"])

        self.assertEqual(["regional_escort"], [row.slug for row in standard])
        self.assertEqual(["cataclysm_front"], [row.slug for row in cataclysm])
        self.assertEqual(["regional_escort"], [row.slug for row in escort])


if __name__ == "__main__":
    unittest.main()
