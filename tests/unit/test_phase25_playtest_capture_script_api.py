import importlib.util
import json
from pathlib import Path
import unittest


class Phase25PlaytestCaptureScriptApiTests(unittest.TestCase):
    def _load_module(self):
        root = Path(__file__).resolve().parents[2]
        script_path = root / "tools" / "testing" / "phase25_cli_playtest_capture.py"
        spec = importlib.util.spec_from_file_location("phase25_capture_script", script_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        return module

    def test_run_capture_function_writes_expected_artifacts(self) -> None:
        module = self._load_module()
        self.assertTrue(hasattr(module, "run_capture"))

        report_path, notes_path, result = module.run_capture()

        self.assertTrue(Path(report_path).exists())
        self.assertTrue(Path(notes_path).exists())
        self.assertIn("timestamp_utc", result)
        self.assertIn("loop_counters", result)
        self.assertIn("delta", result)
        report_payload = json.loads(Path(report_path).read_text(encoding="utf-8"))
        self.assertEqual(result.get("timestamp_utc"), report_payload.get("timestamp_utc"))


if __name__ == "__main__":
    unittest.main()

