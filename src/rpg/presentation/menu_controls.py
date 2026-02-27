import os
import sys
import time

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.live import Live
except Exception:  # pragma: no cover - optional dependency fallback
    Console = None
    Panel = None
    Live = None

try:  # Windows-specific keyboard handling
    import msvcrt  # type: ignore
except ImportError:  # pragma: no cover - fallback for non-Windows
    msvcrt = None


_CONSOLE = Console() if Console is not None else None
_KEY_REPEAT_DEBOUNCE_SECONDS = 0.08
_INITIAL_ENTER_GUARD_SECONDS = 0.18
_ENTER_AFTER_NAV_GUARD_SECONDS = 0.14
_ENTER_AFTER_NOISE_GUARD_SECONDS = 0.22


def _decorate_title(title: str) -> str:
    core = str(title or "").strip()
    if not core:
        core = "Menu"
    return f"[bold yellow]{core}[/bold yellow]"


def clear_screen() -> None:
    """Clear the console in a basic cross-platform way."""

    os.system("cls" if os.name == "nt" else "clear")


def _read_key_windows():
    """Read a single key from the keyboard on Windows using msvcrt."""

    ch = msvcrt.getch()

    if ch in (b"\x00", b"\xe0"):
        ch2 = msvcrt.getch()
        if ch2 == b"H":
            return "UP"
        if ch2 == b"P":
            return "DOWN"
        if ch2 == b"K":
            return "LEFT"
        if ch2 == b"M":
            return "RIGHT"
        return None

    if ch in (b"\r", b"\n"):
        return "ENTER"
    if ch == b"\x1b":
        return "ESC"

    try:
        return ch.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _flush_windows_input_buffer() -> None:
    if msvcrt is None:
        return
    try:
        while msvcrt.kbhit():
            msvcrt.getch()
    except Exception:
        return


def read_key():
    """Read a key, defaulting to simple input when msvcrt is unavailable."""

    if msvcrt is not None:
        return _read_key_windows()

    # Basic fallback: rely on blocking stdin
    line = sys.stdin.readline()
    if line == "":
        return None
    return line.strip()


def normalize_menu_key(key):
    if key is None:
        return None

    if not isinstance(key, str):
        return key

    if key in {"UP", "DOWN", "LEFT", "RIGHT", "ENTER", "ESC"}:
        return key

    lowered = key.lower().strip()
    mapping = {
        "w": "UP",
        "s": "DOWN",
        "a": "LEFT",
        "d": "RIGHT",
        "": "ENTER",
        "enter": "ENTER",
        "q": "ESC",
        "esc": "ESC",
    }
    return mapping.get(lowered, key)


def arrow_menu(
    title: str,
    options: list[str],
    footer_hint: str | None = None,
    initial_enter_guard_seconds: float | None = None,
) -> int:
    """Render a vertical menu controlled by arrow keys.

    Returns the selected option index, or -1 if the user presses ESC.
    """

    if not options:
        raise ValueError("arrow_menu requires at least one option")

    _flush_windows_input_buffer()
    enter_guard_seconds = (
        float(initial_enter_guard_seconds)
        if initial_enter_guard_seconds is not None
        else _INITIAL_ENTER_GUARD_SECONDS
    )
    selected = 0
    last_nav_at = 0.0
    last_noise_at = 0.0
    menu_opened_at = time.monotonic()
    has_navigation_input = False

    def _is_guarded_initial_enter(key: str | None, raw_key, now: float) -> bool:
        nonlocal menu_opened_at
        if msvcrt is None:
            return False
        if raw_key != "ENTER":
            return False
        if has_navigation_input:
            return False
        if key != "ENTER":
            return False
        if (now - menu_opened_at) < enter_guard_seconds:
            menu_opened_at = now
            return True
        return False

    def _next_selection(current: int, key: str | None, now: float) -> int | None:
        nonlocal last_nav_at, has_navigation_input
        if key == "UP":
            if now - last_nav_at < _KEY_REPEAT_DEBOUNCE_SECONDS:
                return current
            last_nav_at = now
            has_navigation_input = True
            return (current - 1) % len(options)
        if key == "DOWN":
            if now - last_nav_at < _KEY_REPEAT_DEBOUNCE_SECONDS:
                return current
            last_nav_at = now
            has_navigation_input = True
            return (current + 1) % len(options)
        return None

    def _register_noise(key: str | None, raw_key, now: float) -> None:
        nonlocal last_noise_at
        if key in {"UP", "DOWN", "LEFT", "RIGHT", "ENTER", "ESC"}:
            return
        if raw_key in (None, "", "ENTER"):
            return
        last_noise_at = now

    def _build_rich_panel(index: int):
        body_lines: list[str] = []
        body_lines.append("[#d6c59d]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/#d6c59d]")
        for idx, option in enumerate(options):
            if idx == index:
                body_lines.append(f"[bold black on yellow] ▶ {option} [/bold black on yellow]")
            else:
                body_lines.append(f"[white]  {option}[/white]")
        body_lines.append("")
        body_lines.append("[#d6c59d]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/#d6c59d]")
        if footer_hint:
            body_lines.append(f"[yellow]{footer_hint}[/yellow]")
        body_lines.append("[dim]Use arrow keys to move, ENTER to select, ESC to cancel.[/dim]")
        return Panel.fit(
            "\n".join(body_lines),
            title=_decorate_title(title),
            border_style="yellow",
            subtitle="[dim]↑/↓ Navigate • Enter Confirm • Esc Back[/dim]",
            subtitle_align="left",
            padding=(0, 1),
        )

    if _CONSOLE is not None and Panel is not None and Live is not None:
        clear_screen()
        with Live(_build_rich_panel(selected), console=_CONSOLE, refresh_per_second=30, transient=True) as live:
            while True:
                raw_key = read_key()
                key = normalize_menu_key(raw_key)
                now = time.monotonic()
                next_selected = _next_selection(selected, key, now)
                if next_selected is not None:
                    if next_selected != selected:
                        selected = next_selected
                        live.update(_build_rich_panel(selected), refresh=True)
                    continue
                _register_noise(key, raw_key, now)
                if key == "ENTER":
                    if msvcrt is not None and raw_key == "ENTER" and (now - last_nav_at) < _ENTER_AFTER_NAV_GUARD_SECONDS:
                        continue
                    if (now - last_noise_at) < _ENTER_AFTER_NOISE_GUARD_SECONDS:
                        continue
                    if _is_guarded_initial_enter(key, raw_key, now):
                        continue
                    return selected
                if key == "ESC":
                    return -1
        return -1

    while True:
        clear_screen()
        print("=" * 40)
        print(f"{title:^40}")
        print("=" * 40)
        print("")

        for idx, option in enumerate(options):
            prefix = "> " if idx == selected else "  "
            print(f"{prefix}{option}")

        print("")
        if footer_hint:
            print(footer_hint)
        print("-" * 40)
        print("Use arrow keys to move, ENTER to select, ESC to cancel.")
        print("-" * 40)

        raw_key = read_key()
        key = normalize_menu_key(raw_key)
        now = time.monotonic()
        next_selected = _next_selection(selected, key, now)
        if next_selected is not None:
            selected = next_selected
            continue
        _register_noise(key, raw_key, now)
        if key == "ENTER":
            if msvcrt is not None and raw_key == "ENTER" and (now - last_nav_at) < _ENTER_AFTER_NAV_GUARD_SECONDS:
                continue
            if (now - last_noise_at) < _ENTER_AFTER_NOISE_GUARD_SECONDS:
                continue
            if _is_guarded_initial_enter(key, raw_key, now):
                continue
            return selected
        if key == "ESC":
            return -1
