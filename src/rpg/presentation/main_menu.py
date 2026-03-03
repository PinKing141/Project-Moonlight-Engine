import os

from rpg.application.services.game_service import GameService
from rpg.infrastructure.analysis.narrative_quality_batch import maybe_emit_session_quality_report
from rpg.presentation.character_creation_ui import run_character_creation
from rpg.presentation.game_loop import run_game_loop
from rpg.presentation.live_game_loop import run_live_game_loop
from rpg.presentation.load_menu import choose_existing_character
from rpg.presentation.menu_controls import arrow_menu, clear_screen
from rpg.presentation.music import get_music_player
from rpg.presentation.sound_effects import get_sound_effects

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.align import Align
except Exception:  # pragma: no cover - optional dependency fallback
    Console = None
    Panel = None
    Align = None


_CONSOLE = Console() if Console is not None else None
_SPLASH_BORDER = "cyan"
_HELP_BORDER = "cyan"
_CREDITS_BORDER = "green"
_EXIT_BORDER = "magenta"


def _use_live_fsm_cli() -> bool:
    raw = str(os.getenv("RPG_CLI_LIVE_FSM", "0") or "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _ornate_title(title: str) -> str:
    return f"[bold yellow]{title}[/bold yellow]"


def _render_centered_panel(body: str, *, title: str, border_style: str) -> None:
    if _CONSOLE is None or Panel is None:
        return
    panel_width = 72
    try:
        panel_width = max(56, min(108, int(_CONSOLE.size.width) - 8))
    except Exception:
        panel_width = 72
    panel = Panel(
        body,
        title=title,
        border_style=border_style,
        width=panel_width,
        expand=False,
    )
    if Align is not None:
        _CONSOLE.print(Align.center(panel, vertical="middle"))
        return
    _CONSOLE.print(panel)


def _show_main_splash() -> None:
    if _CONSOLE is None or Panel is None:
        return
    clear_screen()
    _render_centered_panel(
        "[bold yellow]REALM OF BROKEN STARS[/bold yellow]",
        title=_ornate_title("Main Menu"),
        border_style=_SPLASH_BORDER,
    )


def main_menu(game_service: GameService) -> None:
    options = ["New Game", "Continue", "Help", "Credits", "Quit"]
    session_character_id: int | None = None
    sfx = get_sound_effects()
    music = get_music_player()
    music.set_context("menu")

    while True:
        menu_title = "Realm of Broken Stars"
        if session_character_id is not None:
            try:
                loop_view = game_service.get_game_loop_view(session_character_id)
                if bool(getattr(loop_view, "cataclysm_active", False)):
                    summary = str(getattr(loop_view, "cataclysm_summary", "") or "").strip()
                    if summary:
                        menu_title = f"Realm of Broken Stars — DOOMSDAY: {summary}"
            except Exception:
                pass
        choice_idx = arrow_menu(
            menu_title,
            options,
            initial_enter_guard_seconds=0.35,
        )

        if choice_idx == 0:  # New Game
            sfx.play("menu_select")
            character_id = run_character_creation(game_service)
            if character_id is not None:
                session_character_id = character_id
                sfx.play("game_start")
                if _use_live_fsm_cli():
                    run_live_game_loop(game_service, character_id)
                else:
                    run_game_loop(game_service, character_id)

        elif choice_idx == 1:  # Continue
            sfx.play("menu_select")
            character_id = choose_existing_character(game_service)
            if character_id is not None:
                session_character_id = character_id
                sfx.play("game_start")
                if _use_live_fsm_cli():
                    run_live_game_loop(game_service, character_id)
                else:
                    run_game_loop(game_service, character_id)

        elif choice_idx == 2:  # Help
            sfx.play("menu_back")
            clear_screen()
            if _CONSOLE is not None and Panel is not None:
                _render_centered_panel(
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
            sfx.play("menu_back")
            clear_screen()
            if _CONSOLE is not None and Panel is not None:
                _render_centered_panel(
                    "[bold green]Made by You.[/bold green]",
                    title=_ornate_title("Credits"),
                    border_style=_CREDITS_BORDER,
                )
            else:
                print("Made by You.")
            input("Press ENTER to return to the menu...")
            clear_screen()

        elif choice_idx == 4 or choice_idx == -1:  # Quit or ESC
            sfx.play("quit")
            music.stop()
            report_path = maybe_emit_session_quality_report(game_service, character_id=session_character_id)
            clear_screen()
            if report_path is not None:
                if _CONSOLE is not None:
                    _CONSOLE.print(f"[yellow]Session quality report saved to:[/yellow] {report_path}")
                else:
                    print(f"Session quality report saved to: {report_path}")
            if _CONSOLE is not None and Panel is not None:
                _render_centered_panel(
                    "[bold magenta]Ciao Adventurer!!![/bold magenta]",
                    title=_ornate_title("Farewell"),
                    border_style=_EXIT_BORDER,
                )
            else:
                print("Ciao Adventurer!!!")
            break
