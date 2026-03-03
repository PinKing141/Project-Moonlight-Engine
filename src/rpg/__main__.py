from pathlib import Path
import os
import sys

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

# Ensure the src directory is on sys.path when running as a script
_SRC_DIR = Path(__file__).resolve().parents[1]
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
from rpg.bootstrap import create_game_service
from rpg.presentation.main_menu import main_menu
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
from rpg.presentation.loading_screen import startup_loading_screen

if load_dotenv is not None:
    load_dotenv()


def _print_help_surface() -> None:
    print("\nHelp:")
    print("- Main menu: use UP/DOWN (or W/S), ENTER to select, ESC/Q to go back.")
    print("- In game: choose Rest, Explore, or Quit from the action menu.")
    print("- Startup issues: verify RPG_DATABASE_URL or unset it to use in-memory mode.")


def _is_mysql_rng_seed_schema_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "unknown column 'rng_seed'" in text or ("unknown column" in text and "rng_seed" in text)



def _is_mysql_connectivity_error(exc: Exception) -> bool:
    text = str(exc).lower()
    markers = (
        "can't connect to mysql server",
        "mysql.connector.errors.databaseerror",
        "2003 (hy000)",
        "(10061)",
        "connection refused",
        "sqlalchemy.exc.operationalerror",
    )
    return any(marker in text for marker in markers)


def _create_game_service():
    from rpg.bootstrap import create_game_service

    return create_game_service()


def _open_main_menu(game_service):
    from rpg.presentation.main_menu import main_menu

    return main_menu(game_service)


def main():
    try:
        with startup_loading_screen("Booting Realm of Broken Stars..."):
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
            game_service = create_game_service()
        main_menu(game_service)
=======
            game_service = _create_game_service()
        _open_main_menu(game_service)
>>>>>>> theirs
=======
            game_service = _create_game_service()
        _open_main_menu(game_service)
>>>>>>> theirs
=======
            game_service = _create_game_service()
        _open_main_menu(game_service)
>>>>>>> theirs
=======
            game_service = _create_game_service()
        _open_main_menu(game_service)
>>>>>>> theirs
    except KeyboardInterrupt:
        print("\nSession ended.")
    except Exception as exc:
        print("An unexpected error occurred. The game closed safely.")
        print(f"Reason: {exc}")
        if _is_mysql_rng_seed_schema_error(exc):
            print("Hint: run `python -m rpg.infrastructure.db.mysql.migrate` to apply missing schema updates.")
        elif os.getenv("RPG_DATABASE_URL") and _is_mysql_connectivity_error(exc):
            print("Hint: verify MySQL connectivity or set RPG_DB_ALLOW_INMEMORY_FALLBACK=1.")
        _print_help_surface()


if __name__ == "__main__":
    main()

