from __future__ import annotations

import os
import sys
import threading
import time
from contextlib import contextmanager


@contextmanager
def startup_loading_screen(message: str = "Loading game systems..."):
    """Render a lightweight startup status indicator while bootstrapping services."""
    if str(os.getenv("RPG_LOADING_SCREEN_ENABLED", "1") or "1").strip().lower() in {"0", "false", "no", "off"}:
        yield
        return

    spinner_frames = ["|", "/", "-", "\\"]
    stop_event = threading.Event()

    def _run_spinner() -> None:
        frame = 0
        while not stop_event.is_set():
            elapsed = time.perf_counter() - started_at
            sys.stdout.write(f"\r{spinner_frames[frame % len(spinner_frames)]} {message} {elapsed:0.1f}s")
            sys.stdout.flush()
            frame += 1
            time.sleep(0.1)

    started_at = time.perf_counter()
    spinner_thread: threading.Thread | None = None
    use_spinner = bool(getattr(sys.stdout, "isatty", lambda: False)())
    if use_spinner:
        spinner_thread = threading.Thread(target=_run_spinner, daemon=True)
        spinner_thread.start()
    else:
        print(message)

    try:
        yield
    finally:
        stop_event.set()
        if spinner_thread is not None:
            spinner_thread.join(timeout=0.3)
            elapsed = time.perf_counter() - started_at
            sys.stdout.write(f"\r✓ Ready in {elapsed:0.2f}s{' ' * 40}\n")
            sys.stdout.flush()
