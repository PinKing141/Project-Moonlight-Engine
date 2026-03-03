from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from rpg.presentation.character_creation_ui import create_character_from_export_payload

from rpg.presentation.windowing.contracts import DisplayMode
from rpg.presentation.windowing.pygame_host import PygameConfig, PygameWindowHost
from rpg.presentation.windowing.rich_offscreen import RichOffscreenRenderer
from rpg.presentation.windowing.settings import WindowSettings, load_window_settings, save_window_settings


@dataclass
class WindowMenuSelection:
    action: str
    route_index: int | None = None
    character_id: int | None = None


def _menu_markup(title: str, options: list[str], selected: int, footer: str) -> str:
    lines = [f"[#d6c59d]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/#d6c59d]", ""]
    for idx, option in enumerate(options):
        if idx == selected:
            lines.append(f"[bold black on bright_cyan] ▶ {option} [/bold black on bright_cyan]")
        else:
            lines.append(f"[white]   {option}[/white]")
    lines.extend([
        "",
        "[#d6c59d]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/#d6c59d]",
        f"[yellow]{footer}[/yellow]",
        "[bold white]↑/↓ Navigate • Enter Confirm • Esc Back • F11 Fullscreen[/bold white]",
    ])
    panel_body = "\n".join(lines)
    return (
        f"\n[bold yellow]{title}[/bold yellow]\n\n"
        f"[cyan]{panel_body}[/cyan]"
    )


def _info_markup(title: str, lines: list[str], footer: str, border: str = "cyan") -> str:
    body = "\n".join(lines)
    return (
        f"\n[bold yellow]{title}[/bold yellow]\n\n"
        f"[{border}]"
        f"[#d6c59d]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/#d6c59d]\n"
        f"{body}\n"
        f"[#d6c59d]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/#d6c59d]\n"
        f"[yellow]{footer}[/yellow]"
        f"[/{border}]"
    )


def _next_display_mode(current: DisplayMode) -> DisplayMode:
    if current == DisplayMode.WINDOWED:
        return DisplayMode.MAXIMIZED
    if current == DisplayMode.MAXIMIZED:
        return DisplayMode.FULLSCREEN
    return DisplayMode.WINDOWED


def _display_mode_label(mode: DisplayMode) -> str:
    if mode == DisplayMode.WINDOWED:
        return "Windowed"
    if mode == DisplayMode.MAXIMIZED:
        return "Maximised"
    return "Fullscreen"


def _safe_character_id(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _character_options(game_service) -> list[tuple[str, int]]:
    rows = list(getattr(game_service, "list_character_summaries", lambda: [])() or [])
    options: list[tuple[str, int]] = []
    for char in rows:
        character_id = _safe_character_id(getattr(char, "id", 0))
        if character_id <= 0:
            continue
        label = f"{getattr(char, 'name', 'Character')} (Level {getattr(char, 'level', 1)})"
        if not bool(getattr(char, "alive", True)):
            label += " [DEAD]"
        options.append((label, character_id))
    return options


def _export_options() -> list[Path]:
    export_dir = Path("exports")
    if not export_dir.exists():
        return []
    return sorted(export_dir.glob("character_*.json"), key=lambda row: row.stat().st_mtime, reverse=True)


def run_window_menu(game_service=None) -> WindowMenuSelection:
    settings = load_window_settings()
    host = PygameWindowHost(PygameConfig())
    host.set_mode(settings.display_mode)
    renderer = RichOffscreenRenderer(columns=host.columns, rows=host.rows)

    options = ["New Game", "Continue", "Import Exported Character", "Settings", "Help", "Credits", "Quit"]
    selected = 0
    sub_selected = 0
    continue_rows: list[tuple[str, int]] = []
    export_rows: list[Path] = []
    notice_title = "Notice"
    notice_lines: list[str] = []
    message = "Window shell active. Select an action to continue."
    page = "menu"
    last_draw = 0.0

    while host.running:
        for event in host.poll():
            if event.key == "QUIT":
                host.stop()
                return WindowMenuSelection(action="quit")
            if event.key == "UP":
                if page == "menu":
                    selected = (selected - 1) % len(options)
                elif page in {"continue", "import"}:
                    page_count = len(continue_rows) if page == "continue" else len(export_rows)
                    sub_selected = (sub_selected - 1) % (page_count + 1)
            elif event.key == "DOWN":
                if page == "menu":
                    selected = (selected + 1) % len(options)
                elif page in {"continue", "import"}:
                    page_count = len(continue_rows) if page == "continue" else len(export_rows)
                    sub_selected = (sub_selected + 1) % (page_count + 1)
            elif event.key == "TOGGLE_FULLSCREEN":
                new_mode = DisplayMode.WINDOWED if settings.display_mode == DisplayMode.FULLSCREEN else DisplayMode.FULLSCREEN
                settings = WindowSettings(display_mode=new_mode, font_scale=settings.font_scale)
                host.set_mode(settings.display_mode)
                save_window_settings(settings)
            elif event.key == "ENTER":
                if page == "menu":
                    if selected == 0:
                        host.stop()
                        return WindowMenuSelection(action="route", route_index=0)
                    if selected == 1:
                        if game_service is None:
                            host.stop()
                            return WindowMenuSelection(action="route", route_index=1)
                        continue_rows = _character_options(game_service)
                        sub_selected = 0
                        if not continue_rows:
                            notice_title = "Continue"
                            notice_lines = ["[white]No saved characters available.[/white]"]
                            page = "notice"
                        else:
                            page = "continue"
                    elif selected == 2:
                        if game_service is None:
                            host.stop()
                            return WindowMenuSelection(action="route", route_index=2)
                        export_rows = _export_options()
                        sub_selected = 0
                        if not export_rows:
                            notice_title = "Import"
                            notice_lines = ["[white]No exported character files found in exports/.[/white]"]
                            page = "notice"
                        else:
                            page = "import"
                    elif selected == 6:
                        host.stop()
                        return WindowMenuSelection(action="quit")
                    if selected == 3:
                        page = "settings"
                    elif selected == 4:
                        page = "help"
                    elif selected == 5:
                        page = "credits"
                elif page == "settings":
                    new_mode = _next_display_mode(settings.display_mode)
                    settings = WindowSettings(display_mode=new_mode, font_scale=settings.font_scale)
                    host.set_mode(settings.display_mode)
                    save_window_settings(settings)
                elif page == "continue":
                    if sub_selected == len(continue_rows):
                        page = "menu"
                    else:
                        host.stop()
                        return WindowMenuSelection(action="route", route_index=1, character_id=int(continue_rows[sub_selected][1]))
                elif page == "import":
                    if sub_selected == len(export_rows):
                        page = "menu"
                    else:
                        chosen = export_rows[sub_selected]
                        try:
                            payload = json.loads(chosen.read_text(encoding="utf-8"))
                            character_id = create_character_from_export_payload(game_service, dict(payload or {}))
                            if not character_id:
                                raise RuntimeError("Could not create a playable character from this export.")
                            host.stop()
                            return WindowMenuSelection(action="route", route_index=2, character_id=int(character_id))
                        except Exception as exc:
                            notice_title = "Import Failed"
                            notice_lines = [f"[white]{str(exc)}[/white]"]
                            page = "notice"
            elif event.key == "ESC":
                if page == "menu":
                    host.stop()
                    return WindowMenuSelection(action="quit")
                page = "menu"

        now = time.monotonic()
        if now - last_draw > (1 / 30):
            if page == "menu":
                markup = _menu_markup("Realm of Broken Stars", options, selected, message)
            elif page == "continue":
                continue_options = [label for label, _ in continue_rows] + ["Back"]
                markup = _menu_markup("Continue", continue_options, sub_selected, "Select a saved character.")
            elif page == "import":
                import_options = [path.name for path in export_rows] + ["Back"]
                markup = _menu_markup("Import Character", import_options, sub_selected, "Pick an exported sheet to import.")
            elif page == "help":
                markup = _info_markup(
                    "Help & Controls",
                    [
                        "[white]- Move menus: UP/DOWN arrows (or W/S)[/white]",
                        "[white]- Select: ENTER[/white]",
                        "[white]- Cancel/Back: ESC (or Q)[/white]",
                        "[white]- Root options: Act, Travel, Rest, Character, Quit[/white]",
                        "[white]- In Settings, ENTER cycles display mode.[/white]",
                        "[white]- F11 toggles fullscreen while in window shell.[/white]",
                    ],
                    "ESC to return",
                    border="cyan",
                )
            elif page == "credits":
                markup = _info_markup(
                    "Credits",
                    [
                        "[bold green]Made by You.[/bold green]",
                        "",
                        "[white]Realm of Broken Stars[/white]",
                    ],
                    "ESC to return",
                    border="green",
                )
            elif page == "notice":
                markup = _info_markup(
                    notice_title,
                    notice_lines,
                    "ESC to return",
                    border="yellow",
                )
            else:
                markup = _info_markup(
                    "Settings",
                    [
                        f"[white]Display Mode: [bold cyan]{_display_mode_label(settings.display_mode)}[/bold cyan][/white]",
                        "",
                        "[white]Press ENTER to cycle:[/white]",
                        "[white]Windowed → Maximised → Fullscreen[/white]",
                    ],
                    "ENTER to change • ESC to return",
                    border="yellow",
                )

            frame = renderer.render_markup(markup)
            host.draw(frame)
            last_draw = now

    return WindowMenuSelection(action="quit")
