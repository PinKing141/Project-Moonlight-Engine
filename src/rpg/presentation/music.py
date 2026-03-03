from __future__ import annotations

import importlib
import os
from dataclasses import dataclass, field
from pathlib import Path


class _MusicBackend:
    def play(self, track_path: str, volume: float, *, loop: bool) -> bool:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError


@dataclass(slots=True)
class _PygameMusicBackend(_MusicBackend):
    _pygame: object | None = None

    def _load_pygame(self) -> object | None:
        if self._pygame is not None:
            return self._pygame
        if importlib.util.find_spec("pygame") is None:
            return None
        pygame = importlib.import_module("pygame")
        self._pygame = pygame
        return pygame

    def play(self, track_path: str, volume: float, *, loop: bool) -> bool:
        pygame = self._load_pygame()
        if pygame is None or not Path(track_path).exists():
            return False
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.load(track_path)
            pygame.mixer.music.set_volume(max(0.0, min(1.0, float(volume))))
            pygame.mixer.music.play(-1 if loop else 0)
            return True
        except Exception:
            return False

    def stop(self) -> None:
        pygame = self._load_pygame()
        if pygame is None:
            return
        try:
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
        except Exception:
            return


@dataclass(slots=True)
class MusicPlayer:
    enabled: bool
    track_path: str = ""
    volume: float = 0.35
    loop: bool = True
    tracks_by_context: dict[str, str] = field(default_factory=dict)
    _backend: _MusicBackend = field(default_factory=_PygameMusicBackend)
    _is_playing: bool = False
    _current_track_path: str = ""
    _current_context: str = "default"

    @classmethod
    def from_env(cls) -> "MusicPlayer":
        raw_enabled = str(os.getenv("RPG_MUSIC", "0") or "0").strip().lower()
        enabled = raw_enabled in {"1", "true", "yes", "on"}
        track_path = str(os.getenv("RPG_MUSIC_FILE", "") or "").strip()
        try:
            volume = float(str(os.getenv("RPG_MUSIC_VOLUME", "0.35") or "0.35"))
        except ValueError:
            volume = 0.35
        tracks = {
            "menu": str(os.getenv("RPG_MUSIC_TRACK_MENU", "") or "").strip(),
            "exploration": str(os.getenv("RPG_MUSIC_TRACK_EXPLORATION", "") or "").strip(),
            "combat": str(os.getenv("RPG_MUSIC_TRACK_COMBAT", "") or "").strip(),
        }
        return cls(enabled=enabled, track_path=track_path, volume=volume, tracks_by_context=tracks)

    def _resolve_track_for_context(self, context: str) -> str:
        normalized = str(context or "default").strip().lower() or "default"
        track = str(self.tracks_by_context.get(normalized, "") or "").strip()
        if track:
            return track
        return str(self.track_path or "").strip()

    def play(self) -> None:
        self.set_context(self._current_context)

    def set_context(self, context: str) -> None:
        if not self.enabled:
            return
        normalized = str(context or "default").strip().lower() or "default"
        target_track = self._resolve_track_for_context(normalized)
        if not target_track:
            return
        if self._is_playing and self._current_track_path == target_track:
            self._current_context = normalized
            return
        if self._is_playing:
            self._backend.stop()
            self._is_playing = False
        played = bool(self._backend.play(target_track, self.volume, loop=self.loop))
        if played:
            self._is_playing = True
            self._current_track_path = target_track
            self._current_context = normalized

    def stop(self) -> None:
        if not self._is_playing:
            return
        self._backend.stop()
        self._is_playing = False
        self._current_track_path = ""


_MUSIC_SINGLETON: MusicPlayer | None = None


def get_music_player() -> MusicPlayer:
    global _MUSIC_SINGLETON
    if _MUSIC_SINGLETON is None:
        _MUSIC_SINGLETON = MusicPlayer.from_env()
    return _MUSIC_SINGLETON
