import json
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))


class Phase25PlaytestArtifactConsistencyTests(unittest.TestCase):
    def test_report_and_notes_are_consistent(self) -> None:
        root = Path(__file__).resolve().parents[2]
        report_path = root / "artifacts" / "phase25_cli_playtest_report.json"
        notes_path = root / "artifacts" / "phase25_cli_playtest_notes.md"

        self.assertTrue(report_path.exists())
        self.assertTrue(notes_path.exists())

        report = json.loads(report_path.read_text(encoding="utf-8"))
        notes = notes_path.read_text(encoding="utf-8")

        loop = dict(report.get("loop_counters", {}) or {})
        delta = dict(report.get("delta", {}) or {})
        start = dict(report.get("start", {}) or {})
        end = dict(report.get("end", {}) or {})
        quest = dict(report.get("quest", {}) or {})

        self.assertIn(str(report.get("timestamp_utc", "")), notes)
        self.assertIn(f"- Root action selections executed: {int(loop.get('root_actions', 0) or 0)}", notes)
        self.assertIn(f"- Quest board visits: {int(loop.get('quest_board_visits', 0) or 0)}", notes)
        self.assertIn(f"- Quest accepts: {int(loop.get('quest_accepts', 0) or 0)}", notes)
        self.assertIn(f"- Wilderness menu visits: {int(loop.get('wilderness_actions', 0) or 0)}", notes)
        self.assertIn(f"- Travel actions selected from root loop: {int(loop.get('travel_actions', 0) or 0)}", notes)
        self.assertIn(f"- Travel destination hops selected: {int(loop.get('travel_hops', 0) or 0)}", notes)

        self.assertIn(
            f"- Level delta: {int(delta.get('level_delta', 0) or 0)} (start {int(start.get('level', 0) or 0)} -> end {int(end.get('level', 0) or 0)})",
            notes,
        )
        self.assertIn(
            f"- XP delta: {int(delta.get('xp_delta', 0) or 0)} (start {int(start.get('xp', 0) or 0)} -> end {int(end.get('xp', 0) or 0)})",
            notes,
        )
        self.assertIn(
            f"- Gold delta: {int(delta.get('gold_delta', 0) or 0)} (start {int(start.get('gold', 0) or 0)} -> end {int(end.get('gold', 0) or 0)})",
            notes,
        )
        self.assertIn(
            f"- Turn delta: {int(delta.get('turn_delta', 0) or 0)} (start {int(start.get('turn', 0) or 0)} -> end {int(end.get('turn', 0) or 0)})",
            notes,
        )

        self.assertIn(f"- Active quests after cycle: {int(quest.get('active_quests', 0) or 0)}", notes)
        self.assertIn(f"- Ready-to-turn-in quests after cycle: {int(quest.get('ready_to_turn_in', 0) or 0)}", notes)
        self.assertIn(
            f"`travel_actions = {int(loop.get('travel_actions', 0) or 0)}` and `turn_delta = {int(delta.get('turn_delta', 0) or 0)}`",
            notes,
        )


if __name__ == "__main__":
    unittest.main()

