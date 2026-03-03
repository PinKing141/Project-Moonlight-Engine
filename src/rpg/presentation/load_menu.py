from rpg.application.services.game_service import GameService
from rpg.presentation.menu_controls import arrow_menu, clear_screen


def choose_existing_character(game_service: GameService):
    all_characters = list(game_service.list_character_summaries() or [])
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
    characters = [char for char in all_characters if int(getattr(char, "id", 0) or 0) > 0]
=======
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
    def _safe_character_id(value) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    characters = [char for char in all_characters if _safe_character_id(getattr(char, "id", 0)) > 0]
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs

    if not characters:
        clear_screen()
        print("No saved characters available.")
        input("Press ENTER to return to the menu...")
        clear_screen()
        return None

    options = [
        f"{char.name} (Level {char.level}){' [DEAD]' if not char.alive else ''}"
        for char in characters
    ]

    selection = arrow_menu("Continue", options)
    if selection == -1:
        return None

<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
    return int(characters[selection].id)
=======
    return _safe_character_id(characters[selection].id)
>>>>>>> theirs
=======
    return _safe_character_id(characters[selection].id)
>>>>>>> theirs
=======
    return _safe_character_id(characters[selection].id)
>>>>>>> theirs
=======
    return _safe_character_id(characters[selection].id)
>>>>>>> theirs
