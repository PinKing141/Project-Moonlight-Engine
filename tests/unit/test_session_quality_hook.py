import json
import os
import sys
import tempfile
from pathlib import Path
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.narrative_quality_batch import maybe_emit_session_quality_report
from rpg.bootstrap import create_game_service
from rpg.presentation import main_menu as main_menu_module


class SessionQualityHookTests(unittest.TestCase):
    def test_maybe_emit_session_quality_report_is_noop_by_default(self) -> None:
        service = create_game_service()
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("RPG_NARRATIVE_SESSION_REPORT_ENABLED", None)
            path = maybe_emit_session_quality_report(service, character_id=None)
        self.assertIsNone(path)

    def test_maybe_emit_session_quality_report_writes_artifact_when_enabled(self) -> None:
        service = create_game_service()
        with tempfile.TemporaryDirectory() as temp_dir:
            report_path = Path(temp_dir) / "session_quality.json"
            with mock.patch.dict(
                os.environ,
                {
                    "RPG_NARRATIVE_SESSION_REPORT_ENABLED": "1",
                    "RPG_NARRATIVE_SESSION_REPORT_OUTPUT": str(report_path),
                    "RPG_NARRATIVE_SESSION_REPORT_PROFILE": "balanced",
                    "RPG_NARRATIVE_SESSION_REPORT_SEED_COUNT": "3",
                },
                clear=False,
            ):
                written = maybe_emit_session_quality_report(service, character_id=0)

            self.assertIsNotNone(written)
            self.assertTrue(report_path.exists())
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual("balanced", payload["profile"])
            self.assertEqual(3, len(payload["seeds"]))
            self.assertIn("aggregate_gate", payload)
            self.assertIn("session_context", payload)

    def test_main_menu_quit_invokes_session_report_hook(self) -> None:
        service = create_game_service()
        with mock.patch.object(main_menu_module, "arrow_menu", side_effect=[4]), mock.patch.object(
            main_menu_module,
            "clear_screen",
            return_value=None,
        ), mock.patch.object(
            main_menu_module,
            "maybe_emit_session_quality_report",
            return_value=None,
        ) as emit_mock:
            main_menu_module.main_menu(service)

        emit_mock.assert_called_once_with(service, character_id=None)


if __name__ == "__main__":
    unittest.main()
