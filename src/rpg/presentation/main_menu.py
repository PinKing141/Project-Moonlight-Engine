from rpg.application.services.game_service import GameService
from rpg.application.services.narrative_quality_batch import maybe_emit_session_quality_report
from rpg.presentation.character_creation_ui import run_character_creation
from rpg.presentation.game_loop import run_game_loop
from rpg.presentation.load_menu import choose_existing_character
from rpg.presentation.menu_controls import arrow_menu, clear_screen

try:
    from rich.console import Console
    from rich.panel import Panel
except Exception:  # pragma: no cover - optional dependency fallback
    Console = None
    Panel = None


_CONSOLE = Console() if Console is not None else None
_SPLASH_BORDER = "yellow"
_HELP_BORDER = "yellow"
_CREDITS_BORDER = "green"
_EXIT_BORDER = "magenta"


def _ornate_title(title: str) -> str:
    return f"[bold yellow]{title}[/bold yellow]"


def _show_main_splash() -> None:
    if _CONSOLE is None or Panel is None:
        return
    clear_screen()
    _CONSOLE.print(
        Panel.fit(
            "[bold yellow]REALM OF BROKEN STARS[/bold yellow]",
            border_style=_SPLASH_BORDER,
            title=_ornate_title("Main Menu"),
        )
    )


def main_menu(game_service: GameService) -> None:
    options = ["New Game", "Continue", "Help", "Credits", "Quit"]
    session_character_id: int | None = None

    while True:
        choice_idx = arrow_menu(
            "Realm of Broken Stars",
            options,
            initial_enter_guard_seconds=0.35,
        )

        if choice_idx == 0:  # New Game
            character_id = run_character_creation(game_service)
            if character_id is not None:
                session_character_id = character_id
                run_game_loop(game_service, character_id)

        elif choice_idx == 1:  # Continue
            character_id = choose_existing_character(game_service)
            if character_id is not None:
                session_character_id = character_id
                run_game_loop(game_service, character_id)

        elif choice_idx == 2:  # Help
            clear_screen()
            if _CONSOLE is not None and Panel is not None:
                _CONSOLE.print(
                    Panel.fit(
                        "\n".join(
                            [
                                "[bold]Help & Controls[/bold]",
                                "- Move menus: UP/DOWN arrows (or W/S)",
                                "- Select: ENTER",
                                "- Cancel/Back: ESC (or Q)",
                                "- Root options: Act, Travel, Rest, Character, Quit",
                                "- Act is location-aware: Town Activities in town, Explore Area in wilderness",
                                "- Town options: Talk, Quest Board, Rumour Board, Shop, Training, View Factions",
                                "- If MySQL fails, unset RPG_DATABASE_URL to use in-memory mode.",
                            ]
                        ),
                        title=_ornate_title("Guidance"),
                        border_style=_HELP_BORDER,
                    )
                )
            else:
                print("=== Help & Controls ===")
                print("- Move menus: UP/DOWN arrows (or W/S)")
                print("- Select: ENTER")
                print("- Cancel/Back: ESC (or Q)")
                print("- Root options: Act, Travel, Rest, Character, Quit")
                print("- Act is location-aware: Town Activities in town, Explore Area in wilderness")
                print("- Town options: Talk, Quest Board, Rumour Board, Shop, Training, View Factions")
                print("- If MySQL fails, unset RPG_DATABASE_URL to use in-memory mode.")
            input("Press ENTER to return to the menu...")
            clear_screen()

        elif choice_idx == 3:  # Credits
            clear_screen()
            if _CONSOLE is not None and Panel is not None:
                _CONSOLE.print(
                    Panel.fit(
                        "[bold green]Made by You.[/bold green]",
                        title=_ornate_title("Credits"),
                        border_style=_CREDITS_BORDER,
                    )
                )
            else:
                print("Made by You.")
            input("Press ENTER to return to the menu...")
            clear_screen()

        elif choice_idx == 4 or choice_idx == -1:  # Quit or ESC
            report_path = maybe_emit_session_quality_report(game_service, character_id=session_character_id)
            clear_screen()
            if report_path is not None:
                if _CONSOLE is not None:
                    _CONSOLE.print(f"[yellow]Session quality report saved to:[/yellow] {report_path}")
                else:
                    print(f"Session quality report saved to: {report_path}")
            if _CONSOLE is not None and Panel is not None:
                _CONSOLE.print(
                    Panel.fit(
                        "[bold magenta]Ciao Adventurer!!![/bold magenta]",
                        title=_ornate_title("Farewell"),
                        border_style=_EXIT_BORDER,
                    )
                )
            else:
                print("Ciao Adventurer!!!")
            break
