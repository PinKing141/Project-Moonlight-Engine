from rpg.application.services.game_service import GameService
from rpg.presentation.menu_controls import arrow_menu, clear_screen


def choose_existing_character(game_service: GameService):
    all_characters = list(game_service.list_character_summaries() or [])
    characters = [char for char in all_characters if int(getattr(char, "id", 0) or 0) > 0]

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

    return int(characters[selection].id)
