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

from rpg.bootstrap import create_game_service
from rpg.presentation.main_menu import main_menu

if load_dotenv is not None:
    load_dotenv()


def _print_help_surface() -> None:
    print("\nHelp:")
    print("- Main menu: use UP/DOWN (or W/S), ENTER to select, ESC/Q to go back.")
    print("- In game: choose Rest, Explore, or Quit from the action menu.")
    print("- Startup issues: verify RPG_DATABASE_URL or unset it to use in-memory mode.")



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


def main():
    try:
        game_service = create_game_service()
        main_menu(game_service)
    except KeyboardInterrupt:
        print("\nSession ended.")
    except Exception as exc:
        if os.getenv("RPG_DATABASE_URL") and _is_mysql_connectivity_error(exc):
            print("MySQL connection unavailable; retrying in-memory mode.")
            os.environ.pop("RPG_DATABASE_URL", None)
            try:
                game_service = create_game_service()
                main_menu(game_service)
                return
            except KeyboardInterrupt:
                print("\nSession ended.")
                return
            except Exception as fallback_exc:
                exc = fallback_exc
        print("An unexpected error occurred. The game closed safely.")
        print(f"Reason: {exc}")
        _print_help_surface()


if __name__ == "__main__":
    main()

