import os
import tempfile
import unittest
from unittest import mock

from rpg.presentation.music import MusicPlayer


class _BackendStub:
    def __init__(self, should_play: bool = True) -> None:
        self.should_play = should_play
        self.play_calls = 0
        self.stop_calls = 0
        self.tracks: list[str] = []

    def play(self, track_path: str, volume: float, *, loop: bool) -> bool:
        self.play_calls += 1
        self.tracks.append(track_path)
        return self.should_play

    def stop(self) -> None:
        self.stop_calls += 1


class MusicPlayerTests(unittest.TestCase):
    def test_from_env_defaults_disabled(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            player = MusicPlayer.from_env()
        self.assertFalse(player.enabled)
        self.assertEqual("", player.track_path)

    def test_from_env_reads_context_tracks(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "RPG_MUSIC": "1",
                "RPG_MUSIC_TRACK_MENU": "menu.mp3",
                "RPG_MUSIC_TRACK_EXPLORATION": "explore.mp3",
                "RPG_MUSIC_TRACK_COMBAT": "combat.mp3",
            },
            clear=True,
        ):
            player = MusicPlayer.from_env()
        self.assertTrue(player.enabled)
        self.assertEqual("menu.mp3", player.tracks_by_context["menu"])
        self.assertEqual("explore.mp3", player.tracks_by_context["exploration"])
        self.assertEqual("combat.mp3", player.tracks_by_context["combat"])

    def test_set_context_does_not_restart_same_track(self) -> None:
        backend = _BackendStub()
        with tempfile.NamedTemporaryFile() as handle:
            player = MusicPlayer(enabled=True, track_path=handle.name, _backend=backend)
            player.set_context("exploration")
            player.set_context("exploration")
        self.assertEqual(1, backend.play_calls)

    def test_set_context_switches_tracks(self) -> None:
        backend = _BackendStub()
        with tempfile.NamedTemporaryFile() as menu_handle, tempfile.NamedTemporaryFile() as combat_handle:
            player = MusicPlayer(
                enabled=True,
                track_path=menu_handle.name,
                tracks_by_context={"menu": menu_handle.name, "combat": combat_handle.name},
                _backend=backend,
            )
            player.set_context("menu")
            player.set_context("combat")
        self.assertEqual(2, backend.play_calls)
        self.assertEqual([menu_handle.name, combat_handle.name], backend.tracks)
        self.assertEqual(1, backend.stop_calls)

    def test_stop_invokes_backend_after_successful_play(self) -> None:
        backend = _BackendStub(should_play=True)
        with tempfile.NamedTemporaryFile() as handle:
            player = MusicPlayer(enabled=True, track_path=handle.name, _backend=backend)
            player.play()
            player.stop()
        self.assertEqual(1, backend.stop_calls)


if __name__ == "__main__":
    unittest.main()
