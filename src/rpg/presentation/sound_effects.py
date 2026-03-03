from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass


_EVENT_BELL_COUNT: dict[str, int] = {
    "menu_move": 1,
    "menu_select": 1,
    "menu_back": 1,
    "game_start": 2,
    "action_success": 1,
    "combat_hit": 1,
    "combat_crit": 2,
    "error": 3,
    "boot_ready": 2,
    "quit": 1,
}


@dataclass(slots=True)
class SoundEffects:
    enabled: bool
    min_interval_s: float = 0.04
    _last_played_at: float = 0.0

    @classmethod
    def from_env(cls) -> "SoundEffects":
        raw = str(os.getenv("RPG_SOUND_EFFECTS", "0") or "0").strip().lower()
        enabled = raw in {"1", "true", "yes", "on"}
        return cls(enabled=enabled)

    def play(self, event: str) -> None:
        if not self.enabled:
            return
        now = time.perf_counter()
        if now - self._last_played_at < self.min_interval_s:
            return
        self._last_played_at = now
        bell_count = _EVENT_BELL_COUNT.get(str(event or ""), 1)
        sys.stdout.write("\a" * max(1, int(bell_count)))
        sys.stdout.flush()


_SOUND_EFFECTS_SINGLETON: SoundEffects | None = None


def get_sound_effects() -> SoundEffects:
    global _SOUND_EFFECTS_SINGLETON
    if _SOUND_EFFECTS_SINGLETON is None:
        _SOUND_EFFECTS_SINGLETON = SoundEffects.from_env()
    return _SOUND_EFFECTS_SINGLETON
