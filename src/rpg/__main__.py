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

from rpg.presentation.loading_screen import startup_loading_screen
from rpg.presentation.display_settings import apply_display_mode

if load_dotenv is not None:
    load_dotenv()


def _print_help_surface() -> None:
    print("\nHelp:")
    print("- Main menu: use UP/DOWN (or W/S), ENTER to select, ESC/Q to go back.")
    print("- In game: choose Rest, Explore, or Quit from the action menu.")
    print("- Startup issues: verify RPG_DATABASE_URL or unset it to use in-memory mode.")


def _apply_console_colour_defaults() -> None:
    if os.name != "nt":
        return
    try:
        os.system("color 0F")
    except Exception:
        return


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


def _open_main_menu(
    game_service,
    initial_choice_idx: int | None = None,
    initial_character_id: int | None = None,
):
    from rpg.presentation.main_menu import main_menu

    return main_menu(
        game_service,
        initial_choice_idx=initial_choice_idx,
        initial_character_id=initial_character_id,
    )


def _use_window_shell() -> bool:
    raw = str(os.getenv("RPG_WINDOW_SHELL", "0") or "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def main():
    window_backend = None
    try:
        _apply_console_colour_defaults()
        apply_display_mode()
        with startup_loading_screen("Booting Realm of Broken Stars..."):
            game_service = _create_game_service()
        initial_choice_idx: int | None = None
        initial_character_id: int | None = None
        if _use_window_shell():
            try:
                from rpg.presentation.windowing.window_menu import run_window_menu
                from rpg.presentation.windowing.menu_backend import WindowMenuBackend
                from rpg.presentation.menu_controls import set_menu_transport_backend

                selection = run_window_menu(game_service)
                if str(getattr(selection, "action", "")) == "quit":
                    return
                initial_choice_idx = getattr(selection, "route_index", None)
                initial_character_id = getattr(selection, "character_id", None)
                window_backend = WindowMenuBackend()
                set_menu_transport_backend(window_backend)
            except Exception as window_exc:
                print(f"Window shell unavailable; continuing in terminal mode. Reason: {window_exc}")
        _open_main_menu(
            game_service,
            initial_choice_idx=initial_choice_idx,
            initial_character_id=initial_character_id,
        )
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
    finally:
        if window_backend is not None:
            try:
                window_backend.stop()
            except Exception:
                pass
        try:
            from rpg.presentation.menu_controls import reset_menu_transport_backend

            reset_menu_transport_backend()
        except Exception:
            pass


if __name__ == "__main__":
    main()
