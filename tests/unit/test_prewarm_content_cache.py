import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.infrastructure.prewarm_content_cache import (
    build_prewarm_plan,
    execute_prewarm_plan,
    normalize_targets,
)


class _FakeClient:
    def __init__(self, fail_target: str | None = None):
        self.calls: list[tuple[str, int]] = []
        self.fail_target = fail_target

    def _call(self, target: str, page: int):
        self.calls.append((target, page))
        if self.fail_target == target:
            raise RuntimeError("boom")
        return {"results": []}

    def list_races(self, page: int = 1):
        return self._call("races", page)

    def list_classes(self, page: int = 1):
        return self._call("classes", page)

    def list_spells(self, page: int = 1):
        return self._call("spells", page)

    def list_monsters(self, page: int = 1):
        return self._call("monsters", page)


class PrewarmContentCacheTests(unittest.TestCase):
    def test_normalize_targets_supports_all(self) -> None:
        self.assertEqual(
            ["races", "classes", "spells", "monsters"],
            normalize_targets(["all"]),
        )

    def test_build_plan_creates_expected_call_count(self) -> None:
        plan = build_prewarm_plan(["races", "classes"], pages=2, start_page=1)
        calls = [(entry.target, entry.page, entry.method_name) for entry in plan]
        self.assertEqual(
            [
                ("races", 1, "list_races"),
                ("races", 2, "list_races"),
                ("classes", 1, "list_classes"),
                ("classes", 2, "list_classes"),
            ],
            calls,
        )

    def test_execute_plan_dry_run_skips_calls(self) -> None:
        plan = build_prewarm_plan(["races"], pages=1)
        client = _FakeClient()
        summary = execute_prewarm_plan(client, plan, dry_run=True)
        self.assertEqual(1, summary.planned)
        self.assertEqual(0, summary.executed)
        self.assertEqual([], client.calls)

    def test_execute_plan_counts_success_and_failure(self) -> None:
        plan = build_prewarm_plan(["races", "spells"], pages=1)
        client = _FakeClient(fail_target="spells")
        summary = execute_prewarm_plan(client, plan, dry_run=False)
        self.assertEqual(2, summary.executed)
        self.assertEqual(1, summary.succeeded)
        self.assertEqual(1, summary.failed)


if __name__ == "__main__":
    unittest.main()
