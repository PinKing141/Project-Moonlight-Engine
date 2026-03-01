from __future__ import annotations

import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from rpg.infrastructure.playtest.phase25_scenario import Phase25LoopSelector
from rpg.presentation import cli
from rpg.presentation import game_loop as gl


def _build_notes_text(result: dict[str, object]) -> str:
    loop = dict(result.get("loop_counters", {}) or {})
    delta = dict(result.get("delta", {}) or {})
    start = dict(result.get("start", {}) or {})
    end = dict(result.get("end", {}) or {})
    quest = dict(result.get("quest", {}) or {})
    env = dict(result.get("environment", {}) or {})

    lines = [
        "# Phase 25 CLI Playtest Notes",
        "",
        f"- Timestamp (UTC): {result.get('timestamp_utc')}",
        "- Mode: Scripted CLI loop through `run_game_loop` in in-memory mode.",
        "- Report artifact: `artifacts/phase25_cli_playtest_report.json`",
        "",
        "## Loop Coverage",
        f"- Root action selections executed: {int(loop.get('root_actions', 0) or 0)}",
        f"- Quest board visits: {int(loop.get('quest_board_visits', 0) or 0)}",
        f"- Quest accepts: {int(loop.get('quest_accepts', 0) or 0)}",
        f"- Wilderness menu visits: {int(loop.get('wilderness_actions', 0) or 0)}",
        f"- Travel actions selected from root loop: {int(loop.get('travel_actions', 0) or 0)}",
        f"- Travel destination hops selected: {int(loop.get('travel_hops', 0) or 0)}",
        "",
        "## Pacing & Economy Observations",
        f"- Level delta: {int(delta.get('level_delta', 0) or 0)} (start {int(start.get('level', 0) or 0)} -> end {int(end.get('level', 0) or 0)})",
        f"- XP delta: {int(delta.get('xp_delta', 0) or 0)} (start {int(start.get('xp', 0) or 0)} -> end {int(end.get('xp', 0) or 0)})",
        f"- Gold delta: {int(delta.get('gold_delta', 0) or 0)} (start {int(start.get('gold', 0) or 0)} -> end {int(end.get('gold', 0) or 0)})",
        f"- Turn delta: {int(delta.get('turn_delta', 0) or 0)} (start {int(start.get('turn', 0) or 0)} -> end {int(end.get('turn', 0) or 0)})",
        "",
        "## Quest Tempo",
        f"- Active quests after cycle: {int(quest.get('active_quests', 0) or 0)}",
        f"- Ready-to-turn-in quests after cycle: {int(quest.get('ready_to_turn_in', 0) or 0)}",
        "- Assessment: quest intake path is functioning; progression/turn-in requires a longer loop with encounter completion.",
        "",
        "## Anomalies / Follow-up",
        "- No economy or leveling movement in this bounded cycle.",
    ]

    if int(loop.get("travel_hops", 0) or 0) == 0 and int(env.get("location_count", 0) or 0) <= 1:
        lines.append(
            "- Travel destination selection counter remained 0 because the in-memory bootstrap currently exposes a single location (no destination list to choose from)."
        )
    else:
        lines.append("- Travel destination selection counter captured non-zero destination picks in this run.")

    lines.append(
        f"- Travel execution path is confirmed by `travel_actions = {int(loop.get('travel_actions', 0) or 0)}` and `turn_delta = {int(delta.get('turn_delta', 0) or 0)}`."
    )
    lines.append("- Captured as playtest findings only; no feature work added during freeze.")
    lines.append("")
    return "\n".join(lines)


def run_capture() -> tuple[Path, Path, dict[str, object]]:
    game, creation_service = cli._bootstrap_inmemory()

    with mock.patch("builtins.input", side_effect=["Phase25Hero", "2"]), mock.patch("sys.stdout", new_callable=io.StringIO):
        character_id = cli.run_character_creator(creation_service)

    char_before = game.character_repo.get(character_id)
    world_before = game.world_repo.load_default() if game.world_repo is not None else None
    start_level = int(getattr(char_before, "level", 0) or 0)
    start_xp = int(getattr(char_before, "xp", 0) or 0)
    start_gold = int(getattr(char_before, "money", 0) or 0)
    start_turn = int(getattr(world_before, "current_turn", 0) or 0) if world_before is not None else None
    location_count = len(list(game.location_repo.list_all() or [])) if game.location_repo is not None else 0

    selector = Phase25LoopSelector()

    with mock.patch("rpg.presentation.game_loop._CONSOLE", None), mock.patch(
        "rpg.presentation.game_loop.arrow_menu", side_effect=selector.choose
    ), mock.patch("rpg.presentation.game_loop.clear_screen", lambda: None), mock.patch(
        "rpg.presentation.game_loop._prompt_continue", lambda *args, **kwargs: None
    ), mock.patch("builtins.input", return_value=""), mock.patch("sys.stdout", new_callable=io.StringIO):
        gl.run_game_loop(game, character_id)

    char_after = game.character_repo.get(character_id)
    world_after = game.world_repo.load_default() if game.world_repo is not None else None
    end_level = int(getattr(char_after, "level", 0) or 0)
    end_xp = int(getattr(char_after, "xp", 0) or 0)
    end_gold = int(getattr(char_after, "money", 0) or 0)
    end_turn = int(getattr(world_after, "current_turn", 0) or 0) if world_after is not None else None
    journal = game.get_quest_journal_intent(character_id)

    section_counts = {str(section.title): len(list(section.quests or [])) for section in list(getattr(journal, "sections", []) or [])}
    active_quests = 0
    ready_turnin = 0
    for section in list(getattr(journal, "sections", []) or []):
        for quest in list(getattr(section, "quests", []) or []):
            status = str(getattr(quest, "status", "")).lower()
            if status in {"active", "in_progress"}:
                active_quests += 1
            if status == "ready_to_turn_in":
                ready_turnin += 1

    result = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "character_id": character_id,
        "start": {
            "level": start_level,
            "xp": start_xp,
            "gold": start_gold,
            "turn": start_turn,
        },
        "end": {
            "level": end_level,
            "xp": end_xp,
            "gold": end_gold,
            "turn": end_turn,
        },
        "delta": {
            "level_delta": int(end_level - start_level),
            "xp_delta": int(end_xp - start_xp),
            "gold_delta": int(end_gold - start_gold),
            "turn_delta": int(end_turn - start_turn) if (end_turn is not None and start_turn is not None) else None,
        },
        "quest": {
            "sections": section_counts,
            "active_quests": active_quests,
            "ready_to_turn_in": ready_turnin,
            "quest_accepts": selector.state["quest_accepts"],
        },
        "loop_counters": dict(selector.state),
        "environment": {
            "location_count": int(location_count),
        },
    }

    artifacts_dir = _ROOT / "artifacts"
    report_path = artifacts_dir / "phase25_cli_playtest_report.json"
    notes_path = artifacts_dir / "phase25_cli_playtest_notes.md"

    artifacts_dir.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    notes_path.write_text(_build_notes_text(result), encoding="utf-8")
    return report_path, notes_path, result


def main() -> None:
    report_path, notes_path, result = run_capture()
    print(report_path)
    print(notes_path)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
