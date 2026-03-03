import os
import time

try:  # Windows keyboard polling for timed confirmations
    import msvcrt  # type: ignore
except Exception:  # pragma: no cover - non-Windows fallback
    msvcrt = None

from rpg.application.services.game_service import GameService
from rpg.infrastructure.analysis.narrative_quality_batch import maybe_emit_session_quality_report
from rpg.presentation.character_creation_ui import run_character_creation
from rpg.presentation.game_loop import run_game_loop
from rpg.presentation.live_game_loop import run_live_game_loop
from rpg.presentation.load_menu import choose_existing_character, import_character_from_export
from rpg.presentation.menu_controls import (
    arrow_menu,
    clear_screen,
    get_menu_transport_backend,
    prompt_enter,
    prompt_input,
)
from rpg.presentation.menu_controls import set_menu_transport_backend, reset_menu_transport_backend
from rpg.presentation.music import get_music_player
from rpg.presentation.sound_effects import get_sound_effects
from rpg.presentation.display_settings import (
    apply_display_mode,
    get_display_mode,
    get_display_mode_label,
    set_display_mode,
)

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


def _use_window_shell() -> bool:
    raw = str(os.getenv("RPG_WINDOW_SHELL", "0") or "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _run_with_window_transport(callable_obj, *args, **kwargs):
    if not _use_window_shell():
        return callable_obj(*args, **kwargs)
    try:
        from rpg.presentation.windowing import WindowMenuTransportBackend

        backend = WindowMenuTransportBackend()
        set_menu_transport_backend(backend)
    except Exception:
        return callable_obj(*args, **kwargs)

    try:
        return callable_obj(*args, **kwargs)
    finally:
        reset_menu_transport_backend()
        try:
            backend.close()
        except Exception:
            pass


def _run_selected_game_loop(game_service: GameService, character_id: int) -> None:
    if _use_live_fsm_cli():
        _run_with_window_transport(run_live_game_loop, game_service, character_id)
    else:
        _run_with_window_transport(run_game_loop, game_service, character_id)


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


def _confirm_display_mode_change(label: str, timeout_seconds: int = 10) -> bool:
    timeout_seconds = max(1, int(timeout_seconds))
    if msvcrt is None or get_menu_transport_backend() is not None:
        clear_screen()
        if _CONSOLE is not None and Panel is not None:
            _render_centered_panel(
                f"Display mode set to [bold cyan]{label}[/bold cyan].\n"
                "Press ENTER to keep this change.\n"
                "Type anything else then ENTER to revert.",
                title=_ornate_title("Confirm Display Mode"),
                border_style="yellow",
            )
            response = prompt_input("[bold yellow]Keep change? Press ENTER to keep:[/bold yellow] ")
        else:
            response = prompt_input(
                f"Display mode set to {label}. Press ENTER to keep this change (or type anything to revert): "
            )
        return str(response or "") == ""

    deadline = time.monotonic() + timeout_seconds
    last_remaining = None
    while True:
        remaining = max(0, int(deadline - time.monotonic() + 0.999))
        if remaining != last_remaining:
            clear_screen()
            body = "\n".join(
                [
                    f"Display mode switched to [bold cyan]{label}[/bold cyan].",
                    "",
                    "Press [bold]ENTER[/bold] within the countdown to keep this change.",
                    "If no confirmation is received, the mode will revert automatically.",
                    "",
                    f"[bold yellow]Auto-revert in: {remaining}s[/bold yellow]",
                ]
            )
            if _CONSOLE is not None and Panel is not None:
                _render_centered_panel(
                    body,
                    title=_ornate_title("Confirm Display Mode"),
                    border_style="yellow",
                )
            else:
                print(f"Display mode switched to {label}.")
                print("Press ENTER to keep this change.")
                print(f"Auto-revert in: {remaining}s")
            last_remaining = remaining

        if msvcrt.kbhit():
            key = msvcrt.getch()
            if key in {b"\r", b"\n"}:
                clear_screen()
                return True
            if key == b"\x1b":
                clear_screen()
                return False

        if time.monotonic() >= deadline:
            clear_screen()
            return False
        time.sleep(0.05)


def _open_settings_menu() -> None:
    while True:
        current_mode = get_display_mode()
        current_label = get_display_mode_label(current_mode)
        next_mode = "windowed" if current_mode == "fullscreen" else "fullscreen"
        next_label = get_display_mode_label(next_mode)

        choice = arrow_menu(
            "Settings",
            [
                f"Display Mode: {current_label}",
                "Back",
            ],
            footer_hint=f"ENTER to switch to {next_label}. Press ENTER within 10s to keep, else auto-revert.",
        )

        if choice in {-1, 1}:
            clear_screen()
            return
        if choice == 0:
            previous_mode = current_mode
            set_display_mode(next_mode)
            apply_display_mode(next_mode)
            if not _confirm_display_mode_change(next_label, timeout_seconds=10):
                set_display_mode(previous_mode)
                apply_display_mode(previous_mode)
            clear_screen()


def main_menu(
    game_service: GameService,
    initial_choice_idx: int | None = None,
    initial_character_id: int | None = None,
) -> None:
    options = ["New Game", "Continue", "Import Exported Character", "Settings", "Help", "Credits", "Quit"]
    session_character_id: int | None = None
    pending_choice = initial_choice_idx
    pending_character_id = initial_character_id
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
        if pending_choice is not None:
            choice_idx = int(pending_choice)
            pending_choice = None
        else:
            choice_idx = arrow_menu(
                menu_title,
                options,
                initial_enter_guard_seconds=0.35,
            )

        if choice_idx == 0:  # New Game
            sfx.play("menu_select")
            character_id = _run_with_window_transport(run_character_creation, game_service)
            if character_id is not None:
                session_character_id = character_id
                sfx.play("game_start")
                _run_selected_game_loop(game_service, character_id)

        elif choice_idx == 1:  # Continue
            sfx.play("menu_select")
            if pending_character_id is not None:
                character_id = int(pending_character_id)
                pending_character_id = None
            else:
                character_id = _run_with_window_transport(choose_existing_character, game_service)
            if character_id is not None:
                session_character_id = character_id
                sfx.play("game_start")
                _run_selected_game_loop(game_service, character_id)

        elif choice_idx == 2:  # Import
            sfx.play("menu_select")
            if pending_character_id is not None:
                character_id = int(pending_character_id)
                pending_character_id = None
            else:
                character_id = _run_with_window_transport(import_character_from_export, game_service)
            if character_id is not None:
                session_character_id = character_id
                sfx.play("game_start")
                _run_selected_game_loop(game_service, character_id)

        elif choice_idx == 3:  # Settings
            sfx.play("menu_select")
            _open_settings_menu()

        elif choice_idx == 4:  # Help
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
                            "- Display mode: open Settings from the main menu to switch Windowed/Maximised.",
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
                print("- Display mode: open Settings from the main menu to switch Windowed/Maximised.")
                print("- Act is location-aware: Town Activities in town, Explore Area in wilderness")
                print("- Town options: Talk, Quest Board, Rumour Board, Shop, Training, View Factions")
                print("- If MySQL fails, unset RPG_DATABASE_URL to use in-memory mode.")
            prompt_enter("Press ENTER to return to the menu...")
            clear_screen()

        elif choice_idx == 5:  # Credits
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
            prompt_enter("Press ENTER to return to the menu...")
            clear_screen()

        elif choice_idx == 6 or choice_idx == -1:  # Quit or ESC
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
