from __future__ import annotations

import time

from rpg.presentation.windowing.contracts import DisplayMode
from rpg.presentation.windowing.frame_buffer import FrameBuffer
from rpg.presentation.windowing.pygame_host import PygameConfig, PygameWindowHost
from rpg.presentation.windowing.rich_offscreen import RichOffscreenRenderer
from rpg.presentation.windowing.settings import WindowSettings, load_window_settings, save_window_settings


class WindowMenuTransportBackend:
    """Transport backend that serves menu/input flows from the native window host.

    This backend is intentionally scoped to menu-style interactions (`arrow_menu`,
    `read_key`, `prompt_input`) and is designed for incremental adoption while
    terminal-backed screens are still being migrated.
    """

    def __init__(self, config: PygameConfig | None = None) -> None:
        self._config = config or PygameConfig()
        self._host: PygameWindowHost | None = None
        self._renderer: RichOffscreenRenderer | None = None
        self._settings = load_window_settings()

    def _ensure_host(self) -> None:
        if self._host is not None and self._renderer is not None and self._host.running:
            return
        self._host = PygameWindowHost(self._config)
        self._host.set_mode(self._settings.display_mode)
        self._renderer = RichOffscreenRenderer(columns=self._host.columns, rows=self._host.rows)

    def _toggle_fullscreen(self) -> None:
        mode = self._settings.display_mode
        if mode == DisplayMode.FULLSCREEN:
            next_mode = DisplayMode.WINDOWED
        else:
            next_mode = DisplayMode.FULLSCREEN
        self._settings = WindowSettings(display_mode=next_mode, font_scale=self._settings.font_scale)
        if self._host is not None:
            self._host.set_mode(self._settings.display_mode)
        save_window_settings(self._settings)

    def _menu_markup(self, title: str, options: list[str], selected: int, footer_hint: str | None) -> str:
        lines = ["[#d6c59d]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/#d6c59d]"]
        for idx, option in enumerate(options):
            if idx == selected:
                lines.append(f"[bold black on bright_cyan] ▶ {option} [/bold black on bright_cyan]")
            else:
                lines.append(f"[white]  {option}[/white]")
        lines.extend([
            "",
            "[#d6c59d]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/#d6c59d]",
        ])
        if footer_hint:
            lines.append(f"[yellow]{footer_hint}[/yellow]")
        lines.append("[bold white]Use arrow keys to move, ENTER to select, ESC to cancel. F11 toggles fullscreen.[/bold white]")
        return f"\n[bold yellow]{title}[/bold yellow]\n\n[cyan]{'\\n'.join(lines)}[/cyan]"

    def _prompt_markup(self, prompt: str, value: str) -> str:
        lines = [
            "[#d6c59d]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/#d6c59d]",
            f"[white]{prompt or 'Input'}[/white]",
            "",
            f"[bold cyan]>>>[/bold cyan] [white]{value}[/white]",
            "",
            "[#d6c59d]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/#d6c59d]",
            "[bold white]Type text, ENTER to confirm, ESC to cancel, BACKSPACE to delete.[/bold white]",
        ]
        return "\n[bold yellow]Input[/bold yellow]\n\n[cyan]" + "\n".join(lines) + "[/cyan]"

    def clear_screen(self) -> None:
        self._ensure_host()
        assert self._host is not None
        blank = FrameBuffer(columns=self._host.columns, rows=self._host.rows)
        self._host.draw(blank.rows_view())

    def read_key(self) -> str | None:
        self._ensure_host()
        assert self._host is not None
        while self._host.running:
            for event in self._host.poll():
                if event.key == "QUIT":
                    return "ESC"
                if event.key == "TOGGLE_FULLSCREEN":
                    self._toggle_fullscreen()
                    continue
                if event.key.startswith("TEXT:"):
                    return event.key.split(":", 1)[1]
                if event.key == "BACKSPACE":
                    return "BACKSPACE"
                if event.key in {"UP", "DOWN", "LEFT", "RIGHT", "ENTER", "ESC"}:
                    return event.key
            time.sleep(0.01)
        return "ESC"

    def arrow_menu(
        self,
        title: str,
        options: list[str],
        footer_hint: str | None = None,
        initial_enter_guard_seconds: float | None = None,
    ) -> int:
        if not options:
            raise ValueError("arrow_menu requires at least one option")
        self._ensure_host()
        assert self._host is not None
        assert self._renderer is not None

        selected = 0
        opened_at = time.monotonic()
        guard = float(initial_enter_guard_seconds or 0.18)
        last_draw = 0.0

        while self._host.running:
            for event in self._host.poll():
                if event.key == "QUIT":
                    return -1
                if event.key == "TOGGLE_FULLSCREEN":
                    self._toggle_fullscreen()
                    continue
                if event.key == "UP":
                    selected = (selected - 1) % len(options)
                    continue
                if event.key == "DOWN":
                    selected = (selected + 1) % len(options)
                    continue
                if event.key == "ENTER":
                    if (time.monotonic() - opened_at) < guard:
                        continue
                    return selected
                if event.key == "ESC":
                    return -1

            now = time.monotonic()
            if now - last_draw > (1 / 30):
                frame = self._renderer.render_markup(self._menu_markup(title, options, selected, footer_hint))
                self._host.draw(frame)
                last_draw = now

        return -1

    def prompt_input(self, prompt: str = "") -> str:
        self._ensure_host()
        assert self._host is not None
        assert self._renderer is not None

        value = ""
        last_draw = 0.0
        while self._host.running:
            for event in self._host.poll():
                if event.key == "QUIT":
                    return ""
                if event.key == "TOGGLE_FULLSCREEN":
                    self._toggle_fullscreen()
                    continue
                if event.key == "BACKSPACE":
                    value = value[:-1]
                    continue
                if event.key == "ESC":
                    return ""
                if event.key == "ENTER":
                    return value
                if event.key.startswith("TEXT:"):
                    value += event.key.split(":", 1)[1]

            now = time.monotonic()
            if now - last_draw > (1 / 30):
                frame = self._renderer.render_markup(self._prompt_markup(prompt, value))
                self._host.draw(frame)
                last_draw = now

        return ""

    def close(self) -> None:
        if self._host is not None:
            self._host.stop()
