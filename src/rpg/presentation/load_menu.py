from pathlib import Path
import json

from rpg.application.services.game_service import GameService
from rpg.presentation.character_creation_ui import create_character_from_export_payload
from rpg.presentation.menu_controls import arrow_menu, clear_screen, prompt_enter


def choose_existing_character(game_service: GameService):
    all_characters = list(game_service.list_character_summaries() or [])

    def _safe_character_id(value) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    characters = [char for char in all_characters if _safe_character_id(getattr(char, "id", 0)) > 0]

    if not characters:
        clear_screen()
        print("No saved characters available.")
        prompt_enter("Press ENTER to return to the menu...")
        clear_screen()
        return None

    options = [
        f"{char.name} (Level {char.level}){' [DEAD]' if not char.alive else ''}"
        for char in characters
    ]

    selection = arrow_menu("Continue", options)
    if selection == -1:
        return None

    return _safe_character_id(characters[selection].id)



def import_character_from_export(game_service: GameService):
    export_dir = Path("exports")
    if not export_dir.exists():
        clear_screen()
        print("No exports directory found. Create and export a character first.")
        prompt_enter("Press ENTER to return to the menu...")
        clear_screen()
        return None

    files = sorted(export_dir.glob("character_*.json"), key=lambda row: row.stat().st_mtime, reverse=True)
    if not files:
        clear_screen()
        print("No exported character files found in exports/.")
        prompt_enter("Press ENTER to return to the menu...")
        clear_screen()
        return None

    options = [f"{path.name}" for path in files]
    selection = arrow_menu("Import Character", options, footer_hint="Pick an exported sheet to import.")
    if selection == -1:
        return None

    chosen = files[selection]
    try:
        payload = json.loads(chosen.read_text(encoding="utf-8"))
    except Exception as exc:
        clear_screen()
        print(f"Failed to read export file: {exc}")
        prompt_enter("Press ENTER to return to the menu...")
        clear_screen()
        return None

    character_id = create_character_from_export_payload(game_service, dict(payload or {}))
    if not character_id:
        clear_screen()
        print("Import failed: could not create a playable character from the export data.")
        prompt_enter("Press ENTER to return to the menu...")
        clear_screen()
        return None
    return int(character_id)
