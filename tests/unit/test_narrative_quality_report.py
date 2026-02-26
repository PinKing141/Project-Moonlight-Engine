import json
import os
import sys
import tempfile
import io
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.narrative_quality_batch import (
    DEFAULT_SCRIPT,
    REPORT_SCHEMA_NAME,
    REPORT_SCHEMA_VERSION,
    SCRIPT_PRESETS,
    generate_quality_report,
    write_quality_report_artifact,
)
from rpg.infrastructure.narrative_quality_report import compare_report_artifacts, load_report_artifact, main


class NarrativeQualityReportRuntimeTests(unittest.TestCase):
    def test_generate_quality_report_is_deterministic_for_same_inputs(self) -> None:
        report_a = generate_quality_report(seeds=[111, 222, 333], script=DEFAULT_SCRIPT, profile="balanced")
        report_b = generate_quality_report(seeds=[111, 222, 333], script=DEFAULT_SCRIPT, profile="balanced")

        self.assertEqual(REPORT_SCHEMA_NAME, report_a["schema"]["name"])
        self.assertEqual(REPORT_SCHEMA_VERSION, report_a["schema"]["version"])
        self.assertEqual(report_a["profile"], report_b["profile"])
        self.assertEqual(report_a["quality_targets"], report_b["quality_targets"])
        self.assertEqual(report_a["profile_thresholds"], report_b["profile_thresholds"])
        self.assertEqual(report_a["summaries"], report_b["summaries"])
        self.assertEqual(report_a["aggregate_gate"], report_b["aggregate_gate"])

    def test_runtime_command_writes_json_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_path = Path(temp_dir) / "narrative_report.json"
            rc = main([
                "--seeds",
                "101,202,303",
                "--profile",
                "balanced",
                "--output",
                str(artifact_path),
            ])

            self.assertEqual(0, rc)
            self.assertTrue(artifact_path.exists())

            payload = json.loads(artifact_path.read_text(encoding="utf-8"))
            self.assertEqual([101, 202, 303], payload["seeds"])
            self.assertEqual("balanced", payload["profile"])
            self.assertEqual(REPORT_SCHEMA_VERSION, payload["schema"]["version"])
            self.assertIn("aggregate_gate", payload)
            self.assertIn("summaries", payload)
            self.assertEqual(3, len(payload["summaries"]))

    def test_runtime_command_uses_environment_default_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_path = Path(temp_dir) / "narrative_report_strict.json"
            with patch.dict(os.environ, {"RPG_NARRATIVE_GATE_DEFAULT_PROFILE": "strict"}, clear=False):
                rc = main([
                    "--seeds",
                    "101,202,303",
                    "--output",
                    str(artifact_path),
                ])
            self.assertEqual(0, rc)
            payload = json.loads(artifact_path.read_text(encoding="utf-8"))
            self.assertEqual("strict", payload["profile"])
            self.assertEqual("hold", payload["aggregate_gate"]["release_verdict"])

    def test_loader_rejects_unsupported_schema_version(self) -> None:
        report = generate_quality_report(seeds=[101, 202, 303], script=DEFAULT_SCRIPT, profile="balanced")
        report["schema"] = {"name": REPORT_SCHEMA_NAME, "version": "999.0"}

        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_path = Path(temp_dir) / "unsupported_schema.json"
            write_quality_report_artifact(artifact_path, {**report, "schema": {"name": REPORT_SCHEMA_NAME, "version": REPORT_SCHEMA_VERSION}})
            payload = json.loads(artifact_path.read_text(encoding="utf-8"))
            payload["schema"] = {"name": REPORT_SCHEMA_NAME, "version": "999.0"}
            artifact_path.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Unsupported report schema version"):
                load_report_artifact(artifact_path)

    def test_loader_accepts_current_schema_version(self) -> None:
        report = generate_quality_report(seeds=[101, 202, 303], script=DEFAULT_SCRIPT, profile="balanced")
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_path = Path(temp_dir) / "current_schema.json"
            write_quality_report_artifact(artifact_path, report)
            loaded = load_report_artifact(artifact_path)
        self.assertEqual(REPORT_SCHEMA_VERSION, loaded["schema"]["version"])

    def test_runtime_command_supports_named_script_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_path = Path(temp_dir) / "named_script.json"
            rc = main([
                "--seeds",
                "101,202,303",
                "--script-name",
                "exploration_heavy",
                "--output",
                str(artifact_path),
            ])

            self.assertEqual(0, rc)
            payload = json.loads(artifact_path.read_text(encoding="utf-8"))
            self.assertEqual(list(SCRIPT_PRESETS["exploration_heavy"]), payload["script"])

    def test_runtime_command_rejects_unknown_script_profile(self) -> None:
        with self.assertRaises(SystemExit):
            main(["--script-name", "unknown_profile"])

    def test_runtime_command_rejects_script_and_script_name_together(self) -> None:
        with self.assertRaises(SystemExit):
            main([
                "--script",
                "rest,travel",
                "--script-name",
                "baseline",
            ])

    def test_compare_report_artifacts_returns_deterministic_deltas(self) -> None:
        base_report = generate_quality_report(seeds=[101, 202, 303], script=DEFAULT_SCRIPT, profile="strict")
        candidate_report = generate_quality_report(seeds=[101, 202, 303], script=DEFAULT_SCRIPT, profile="exploratory")

        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir) / "base.json"
            candidate_path = Path(temp_dir) / "candidate.json"
            write_quality_report_artifact(base_path, base_report)
            write_quality_report_artifact(candidate_path, candidate_report)

            delta = compare_report_artifacts(base_path, candidate_path)

        self.assertIn("pass_rate", delta)
        self.assertIn("blockers", delta)
        self.assertIn("semantic_band_counts", delta)
        self.assertIn("gate_verdict", delta)
        self.assertEqual(round(delta["pass_rate"]["candidate"] - delta["pass_rate"]["base"], 4), delta["pass_rate"]["delta"])

    def test_compare_report_artifacts_rejects_incompatible_schema(self) -> None:
        base_report = generate_quality_report(seeds=[101, 202, 303], script=DEFAULT_SCRIPT, profile="balanced")
        candidate_report = generate_quality_report(seeds=[101, 202, 303], script=DEFAULT_SCRIPT, profile="balanced")

        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir) / "base.json"
            candidate_path = Path(temp_dir) / "candidate.json"
            write_quality_report_artifact(base_path, base_report)
            write_quality_report_artifact(candidate_path, candidate_report)

            payload = json.loads(candidate_path.read_text(encoding="utf-8"))
            payload["schema"] = {"name": REPORT_SCHEMA_NAME, "version": "999.0"}
            candidate_path.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Unsupported report schema version"):
                compare_report_artifacts(base_path, candidate_path)

    def test_runtime_command_supports_compare_mode(self) -> None:
        base_report = generate_quality_report(seeds=[101, 202, 303], script=DEFAULT_SCRIPT, profile="strict")
        candidate_report = generate_quality_report(seeds=[101, 202, 303], script=DEFAULT_SCRIPT, profile="exploratory")

        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir) / "base.json"
            candidate_path = Path(temp_dir) / "candidate.json"
            write_quality_report_artifact(base_path, base_report)
            write_quality_report_artifact(candidate_path, candidate_report)

            with patch("sys.stdout", new_callable=io.StringIO) as output:
                rc = main([
                    "--compare-base",
                    str(base_path),
                    "--compare-candidate",
                    str(candidate_path),
                ])

        self.assertEqual(0, rc)
        rendered = output.getvalue()
        self.assertIn('"pass_rate"', rendered)
        self.assertIn('"gate_verdict"', rendered)

    def test_runtime_command_compare_mode_requires_both_paths(self) -> None:
        with self.assertRaises(SystemExit):
            main(["--compare-base", "base.json"])


if __name__ == "__main__":
    unittest.main()
