import json
import os
from pathlib import Path


_SETTINGS_PATH = Path("data") / "settings" / "ui_settings.json"
_DEFAULT_SETTINGS = {
    "display_mode": "fullscreen",
}


def _normalize_display_mode(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"windowed", "fullscreen", "maximized", "maximised"}:
        if raw in {"maximized", "maximised"}:
            return "fullscreen"
        return raw
    return "fullscreen"


def _ensure_parent_dir() -> None:
    _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)


def load_ui_settings() -> dict[str, str]:
    settings = dict(_DEFAULT_SETTINGS)
    if not _SETTINGS_PATH.exists():
        return settings
    try:
        payload = json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return settings
    if isinstance(payload, dict):
        settings["display_mode"] = _normalize_display_mode(str(payload.get("display_mode", "")))
    return settings


def save_ui_settings(settings: dict[str, str]) -> None:
    merged = dict(_DEFAULT_SETTINGS)
    merged["display_mode"] = _normalize_display_mode(str(settings.get("display_mode", "")))
    _ensure_parent_dir()
    _SETTINGS_PATH.write_text(json.dumps(merged, indent=2), encoding="utf-8")


def get_display_mode() -> str:
    return _normalize_display_mode(load_ui_settings().get("display_mode"))


def set_display_mode(mode: str) -> str:
    normalized = _normalize_display_mode(mode)
    settings = load_ui_settings()
    settings["display_mode"] = normalized
    save_ui_settings(settings)
    return normalized


def get_display_mode_label(mode: str | None = None) -> str:
    active = _normalize_display_mode(mode or get_display_mode())
    if active == "windowed":
        return "Windowed"
    return "Maximised"


def _set_mouse_cursor_visible(user32, visible: bool) -> None:
    for _ in range(16):
        current = int(user32.ShowCursor(bool(visible)))
        if visible and current >= 0:
            break
        if not visible and current < 0:
            break


def _set_console_text_cursor_visible(kernel32, visible: bool) -> None:
    try:
        import ctypes

        class CONSOLE_CURSOR_INFO(ctypes.Structure):
            _fields_ = [("dwSize", ctypes.c_uint32), ("bVisible", ctypes.c_int)]

        std_output_handle = -11
        handle = kernel32.GetStdHandle(std_output_handle)
        if not handle:
            return
        info = CONSOLE_CURSOR_INFO()
        if kernel32.GetConsoleCursorInfo(handle, ctypes.byref(info)) == 0:
            return
        info.bVisible = int(bool(visible))
        kernel32.SetConsoleCursorInfo(handle, ctypes.byref(info))
    except Exception:
        return


def apply_display_mode(mode: str | None = None) -> None:
    active = _normalize_display_mode(mode or get_display_mode())
    if os.name != "nt":
        return
    try:
        import ctypes  # type: ignore
        from ctypes import wintypes  # type: ignore

        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32
        hwnd = kernel32.GetConsoleWindow()
        if not hwnd:
            return

        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", wintypes.LONG),
                ("top", wintypes.LONG),
                ("right", wintypes.LONG),
                ("bottom", wintypes.LONG),
            ]

        class MONITORINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("rcMonitor", RECT),
                ("rcWork", RECT),
                ("dwFlags", wintypes.DWORD),
            ]

        sw_restore = 9
        sw_show = 5
        swp_nozorder = 0x0004
        swp_framechanged = 0x0020
        gwl_style = -16
        ws_overlappedwindow = 0x00CF0000
        ws_caption = 0x00C00000
        ws_thickframe = 0x00040000
        ws_minimize = 0x20000000
        ws_maximizebox = 0x00010000
        ws_sysmenu = 0x00080000
        monitor_defaulttonearest = 2

        monitor = user32.MonitorFromWindow(hwnd, monitor_defaulttonearest)
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if not monitor or user32.GetMonitorInfoW(monitor, ctypes.byref(info)) == 0:
            return

        if active == "fullscreen":
            style = int(user32.GetWindowLongW(hwnd, gwl_style))
            borderless_style = style & ~(ws_caption | ws_thickframe | ws_minimize | ws_maximizebox | ws_sysmenu)
            user32.SetWindowLongW(hwnd, gwl_style, borderless_style)
            width = int(info.rcMonitor.right - info.rcMonitor.left)
            height = int(info.rcMonitor.bottom - info.rcMonitor.top)
            user32.SetWindowPos(
                hwnd,
                0,
                int(info.rcMonitor.left),
                int(info.rcMonitor.top),
                width,
                height,
                swp_nozorder | swp_framechanged,
            )
            user32.ShowWindow(hwnd, sw_show)
            _set_mouse_cursor_visible(user32, visible=False)
            _set_console_text_cursor_visible(kernel32, visible=False)
        else:
            user32.SetWindowLongW(hwnd, gwl_style, ws_overlappedwindow)
            user32.ShowWindow(hwnd, sw_restore)
            monitor_width = int(info.rcMonitor.right - info.rcMonitor.left)
            monitor_height = int(info.rcMonitor.bottom - info.rcMonitor.top)
            window_width = max(960, int(monitor_width * 0.82))
            window_height = max(640, int(monitor_height * 0.82))
            pos_x = int(info.rcMonitor.left + (monitor_width - window_width) // 2)
            pos_y = int(info.rcMonitor.top + (monitor_height - window_height) // 2)
            user32.SetWindowPos(
                hwnd,
                0,
                pos_x,
                pos_y,
                window_width,
                window_height,
                swp_nozorder | swp_framechanged,
            )
            _set_mouse_cursor_visible(user32, visible=True)
            _set_console_text_cursor_visible(kernel32, visible=True)
    except Exception:
        return
