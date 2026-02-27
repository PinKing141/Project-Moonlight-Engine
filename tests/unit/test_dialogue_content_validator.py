import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.dialogue_service import DialogueService
from rpg.infrastructure.dialogue_content_validator import main, validate_dialogue_file


class DialogueContentValidatorTests(unittest.TestCase):
    def test_validate_dialogue_content_accepts_repository_payload(self) -> None:
        path = Path(__file__).resolve().parents[2] / "data" / "world" / "dialogue_trees.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual([], DialogueService.validate_dialogue_content(payload))

    def test_validate_dialogue_content_rejects_missing_line(self) -> None:
        payload = {
            "version": 1,
            "npcs": {
                "innkeeper_mara": {
                    "opening": {
                        "choices": [{"id": "friendly", "label": "Friendly", "requires": []}],
                    }
                }
            },
        }
        errors = DialogueService.validate_dialogue_content(payload)
        self.assertTrue(any("line is required" in item for item in errors))

    def test_validate_dialogue_file_returns_error_for_missing_path(self) -> None:
        errors = validate_dialogue_file(Path("data/world/does_not_exist.json"))
        self.assertTrue(errors)
        self.assertIn("File not found", errors[0])

    def test_validate_dialogue_content_rejects_response_variant_without_line(self) -> None:
        payload = {
            "version": 1,
            "npcs": {
                "captain_ren": {
                    "opening": {
                        "line": "Opening",
                        "choices": [
                            {
                                "id": "direct",
                                "label": "Direct",
                                "requires": [],
                                "response_variants": [{"requires": ["tension_high"]}],
                            }
                        ],
                    }
                }
            },
        }
        errors = DialogueService.validate_dialogue_content(payload)
        self.assertTrue(any("response_variants[0].line is required" in item for item in errors))

    def test_validate_dialogue_content_rejects_story_seed_effect_without_target_state(self) -> None:
        payload = {
            "version": 1,
            "npcs": {
                "captain_ren": {
                    "opening": {
                        "line": "Opening",
                        "choices": [
                            {
                                "id": "direct",
                                "label": "Direct",
                                "requires": [],
                                "effects": [{"kind": "story_seed_state", "on": "success"}],
                            }
                        ],
                    }
                }
            },
        }
        errors = DialogueService.validate_dialogue_content(payload)
        self.assertTrue(any("must include status and/or escalation_stage" in item for item in errors))

    def test_main_returns_zero_for_valid_payload(self) -> None:
        temp = Path("tests") / "_tmp_dialogue_valid.json"
        temp.write_text(
            json.dumps(
                {
                    "version": 1,
                    "npcs": {
                        "captain_ren": {
                            "opening": {
                                "line": "Test line",
                                "choices": [
                                    {"id": "friendly", "label": "Friendly", "requires": []},
                                ],
                            }
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = main(["--path", str(temp)])
            self.assertEqual(0, code)
            self.assertIn("Dialogue content valid", buf.getvalue())
        finally:
            temp.unlink(missing_ok=True)

    def test_main_returns_one_for_invalid_payload(self) -> None:
        temp = Path("tests") / "_tmp_dialogue_invalid.json"
        temp.write_text(
            json.dumps(
                {
                    "version": 1,
                    "npcs": {
                        "captain_ren": {
                            "opening": {
                                "line": "",
                                "choices": [
                                    {"id": "friendly", "label": "", "requires": []},
                                ],
                            }
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = main(["--path", str(temp)])
            self.assertEqual(1, code)
            self.assertIn("Dialogue content invalid", buf.getvalue())
        finally:
            temp.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
