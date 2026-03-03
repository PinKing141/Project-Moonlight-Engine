from __future__ import annotations

import time
from collections import deque

from rpg.presentation.windowing.contracts import Cell, DisplayMode
from rpg.presentation.windowing.frame_buffer import FrameBuffer
from rpg.presentation.windowing.pygame_host import PygameConfig, PygameWindowHost
from rpg.presentation.windowing.rich_offscreen import RichOffscreenRenderer
from rpg.presentation.windowing.settings import WindowSettings, load_window_settings, save_window_settings


def _menu_markup(title: str, options: list[str], selected: int, footer: str) -> str:
    lines = ["[#d6c59d]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/#d6c59d]"]
    for idx, option in enumerate(options):
        if idx == selected:
            lines.append(f"[bold black on bright_cyan] ▶ {option} [/bold black on bright_cyan]")
        else:
            lines.append(f"[white]  {option}[/white]")
    lines.extend(
        [
            "",
            "[#d6c59d]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/#d6c59d]",
            f"[yellow]{footer}[/yellow]",
            "[bold white]↑/↓ Navigate • Enter Confirm • Esc Back • F11 Fullscreen[/bold white]",
        ]
    )
    return f"\n[bold yellow]{title}[/bold yellow]\n\n[cyan]{'\n'.join(lines)}[/cyan]"


def _input_markup(prompt: str, value: str) -> str:
    return (
        "\n[bold yellow]Input[/bold yellow]\n\n"
        "[cyan][#d6c59d]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/#d6c59d]\n"
        f"[white]{prompt}[/white]\n"
        f"[bold cyan]>>> {value}[/bold cyan]\n"
        "\n"
        "[#d6c59d]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/#d6c59d]\n"
        "[yellow]Type text, ENTER to confirm, BACKSPACE to edit, ESC to cancel.[/yellow]"
        "[/cyan]"
    )


class WindowMenuBackend:
    def __init__(self) -> None:
        self._settings = load_window_settings()
        self._host = PygameWindowHost(PygameConfig())
        self._host.set_mode(self._settings.display_mode)
        self._renderer = RichOffscreenRenderer(columns=self._host.columns, rows=self._host.rows)
        self._pending_keys: deque[str] = deque()

    def _toggle_fullscreen(self) -> None:
        if self._settings.display_mode == DisplayMode.FULLSCREEN:
            new_mode = DisplayMode.WINDOWED
        else:
            new_mode = DisplayMode.FULLSCREEN
        self._settings = WindowSettings(display_mode=new_mode, font_scale=self._settings.font_scale)
        self._host.set_mode(self._settings.display_mode)
        save_window_settings(self._settings)

    def _pump_events(self) -> None:
        for event in self._host.poll():
            key = str(getattr(event, "key", "") or "")
            if not key:
                continue
            if key == "TOGGLE_FULLSCREEN":
                self._toggle_fullscreen()
                continue
            if key == "QUIT":
                self._pending_keys.append("ESC")
                continue
            self._pending_keys.append(key)

    def _draw_markup(self, markup: str) -> None:
        frame = self._renderer.render_markup(markup)
        self._host.draw(frame)

    def clear_screen(self) -> None:
        blank = FrameBuffer(columns=self._host.columns, rows=self._host.rows)
        self._host.draw(blank.rows_view())

    def read_key(self) -> str | None:
        while self._host.running:
            self._pump_events()
            if self._pending_keys:
                return self._pending_keys.popleft()
            time.sleep(0.01)
        return "ESC"

    def prompt_input(self, prompt: str = "") -> str:
        value = ""
        while self._host.running:
            self._draw_markup(_input_markup(prompt or "Enter value:", value))
            self._pump_events()
            while self._pending_keys:
                key = self._pending_keys.popleft()
                if key == "ENTER":
                    return value
                if key == "ESC":
                    return ""
                if key == "BACKSPACE":
                    value = value[:-1]
                    continue
                if key.startswith("TEXT:"):
                    value += key.removeprefix("TEXT:")
            time.sleep(0.01)
        return ""

    def arrow_menu(
        self,
        title: str,
        options: list[str],
        footer_hint: str | None = None,
        initial_enter_guard_seconds: float | None = None,
    ) -> int:
        if not options:
            return -1
        selected = 0
        while self._host.running:
            footer = str(footer_hint or "Use arrow keys to move, ENTER to select, ESC to cancel.")
            self._draw_markup(_menu_markup(title, options, selected, footer))
            self._pump_events()
            while self._pending_keys:
                key = self._pending_keys.popleft()
                if key == "UP":
                    selected = (selected - 1) % len(options)
                elif key == "DOWN":
                    selected = (selected + 1) % len(options)
                elif key == "ENTER":
                    return selected
                elif key == "ESC":
                    return -1
            time.sleep(0.01)
        return -1

    def stop(self) -> None:
        self._host.stop()
