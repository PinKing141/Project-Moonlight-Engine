import io
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from rpg.presentation import cli
from rpg.presentation import game_loop as gl


game, creation_service = cli._bootstrap_inmemory()

with mock.patch("builtins.input", side_effect=["Phase25Hero", "2"]), mock.patch("sys.stdout", new_callable=io.StringIO):
    character_id = cli.run_character_creator(creation_service)

char_before = game.character_repo.get(character_id)
world_before = game.world_repo.load_default() if game.world_repo is not None else None

state = {
    "root_actions": 0,
    "quest_board_visits": 0,
    "quest_accepts": 0,
    "wilderness_actions": 0,
    "travel_hops": 0,
}


def _choose_menu(title, options):
    text = str(title)
    if text.endswith("— Actions"):
        sequence = [0, 1, 0, 2, 4]
        idx = sequence[state["root_actions"]] if state["root_actions"] < len(sequence) else 4
        state["root_actions"] += 1
        return idx

    if text.startswith("Town Options"):
        if state["quest_board_visits"] == 0:
            return 1
        return 8

    if text.startswith("Quest Board"):
        state["quest_board_visits"] += 1
        if state["quest_accepts"] == 0 and len(options) > 1:
            state["quest_accepts"] += 1
            return 0
        return len(options) - 1

    if text.startswith("Travel Mode"):
        return 0

    if text.startswith("Travel Pace"):
        return 1

    if "Wilderness Actions" in text:
        state["wilderness_actions"] += 1
        return 5

    if text.startswith("Wilderness Rest"):
        return 1

    if "Travel" in text and "—" in text:
        if len(options) > 1:
            state["travel_hops"] += 1
            return 0
        return -1

    if options:
        return len(options) - 1
    return -1


with mock.patch("rpg.presentation.game_loop._CONSOLE", None), mock.patch(
    "rpg.presentation.game_loop.arrow_menu", side_effect=_choose_menu
), mock.patch("rpg.presentation.game_loop.clear_screen", lambda: None), mock.patch(
    "rpg.presentation.game_loop._prompt_continue", lambda *args, **kwargs: None
), mock.patch("builtins.input", return_value=""), mock.patch("sys.stdout", new_callable=io.StringIO):
    gl.run_game_loop(game, character_id)

char_after = game.character_repo.get(character_id)
world_after = game.world_repo.load_default() if game.world_repo is not None else None
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
        "level": int(getattr(char_before, "level", 0) or 0),
        "xp": int(getattr(char_before, "xp", 0) or 0),
        "gold": int(getattr(char_before, "money", 0) or 0),
        "turn": int(getattr(world_before, "current_turn", 0) or 0) if world_before is not None else None,
    },
    "end": {
        "level": int(getattr(char_after, "level", 0) or 0),
        "xp": int(getattr(char_after, "xp", 0) or 0),
        "gold": int(getattr(char_after, "money", 0) or 0),
        "turn": int(getattr(world_after, "current_turn", 0) or 0) if world_after is not None else None,
    },
    "delta": {
        "level_delta": int((getattr(char_after, "level", 0) or 0) - (getattr(char_before, "level", 0) or 0)),
        "xp_delta": int((getattr(char_after, "xp", 0) or 0) - (getattr(char_before, "xp", 0) or 0)),
        "gold_delta": int((getattr(char_after, "money", 0) or 0) - (getattr(char_before, "money", 0) or 0)),
        "turn_delta": int((getattr(world_after, "current_turn", 0) or 0) - (getattr(world_before, "current_turn", 0) or 0)) if (world_after is not None and world_before is not None) else None,
    },
    "quest": {
        "sections": section_counts,
        "active_quests": active_quests,
        "ready_to_turn_in": ready_turnin,
        "quest_accepts": state["quest_accepts"],
    },
    "loop_counters": state,
}

report_path = Path("artifacts") / "phase25_cli_playtest_report.json"
report_path.parent.mkdir(parents=True, exist_ok=True)
report_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
print(report_path)
print(json.dumps(result, indent=2))
