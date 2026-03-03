import os
import sys
from pathlib import Path
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg import bootstrap
from rpg.infrastructure.name_generation import DnDCorpusNameGenerator


class _FakeNameGenerator:
    def suggest_character_name(self, race_name=None, gender=None, context=None):
        return "HookedHero"

    def generate_entity_name(self, default_name, kind=None, faction_id=None, entity_id=None, level=None):
        if kind == "humanoid":
            return f"Hooked-{entity_id}"
        return default_name


class BootstrapNameGeneratorHookTests(unittest.TestCase):
    def test_inmemory_bootstrap_wires_real_name_generator(self) -> None:
        with mock.patch.dict(os.environ, {"RPG_DATABASE_URL": ""}, clear=False):
            service = bootstrap.create_game_service()

        self.assertIsNotNone(service.character_creation_service)
        self.assertIsInstance(service.character_creation_service.name_generator, DnDCorpusNameGenerator)
        self.assertIsNotNone(service.atomic_state_persistor)

    def test_inmemory_bootstrap_passes_name_generator_to_character_and_entity_paths(self) -> None:
        with mock.patch.dict(os.environ, {"RPG_DATABASE_URL": ""}, clear=False), mock.patch.object(
            bootstrap,
            "DnDCorpusNameGenerator",
            _FakeNameGenerator,
        ):
            service = bootstrap.create_game_service()

        self.assertIsNotNone(service.character_creation_service)
        created = service.character_creation_service.create_character(name="  ", class_index=0)
        self.assertEqual("HookedHero", created.name)

        goblin = service.entity_repo.get(1)
        self.assertEqual("Hooked-1", goblin.name)

    def test_create_game_service_raises_when_localhost_unreachable_without_opt_in_fallback(self) -> None:
        with mock.patch.dict(
            os.environ,
            {"RPG_DATABASE_URL": "mysql+mysqlconnector://root@127.0.0.1:3307/rpg_game"},
            clear=False,
        ), mock.patch("rpg.bootstrap.socket.create_connection", side_effect=OSError("refused")), mock.patch.object(
            bootstrap, "_build_mysql_game_service", side_effect=AssertionError("mysql path should be skipped")
        ):
            with self.assertRaises(RuntimeError):
                bootstrap.create_game_service()

    def test_create_game_service_skips_mysql_when_localhost_unreachable_with_opt_in_fallback(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "RPG_DATABASE_URL": "mysql+mysqlconnector://root@127.0.0.1:3307/rpg_game",
                "RPG_DB_ALLOW_INMEMORY_FALLBACK": "1",
            },
            clear=False,
        ), mock.patch("rpg.bootstrap.socket.create_connection", side_effect=OSError("refused")), mock.patch.object(
            bootstrap, "_build_mysql_game_service", side_effect=AssertionError("mysql path should be skipped")
        ):
            service = bootstrap.create_game_service()

        self.assertIsNotNone(service)

    def test_create_game_service_tolerates_invalid_probe_timeout_env(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "RPG_DATABASE_URL": "mysql+mysqlconnector://root@127.0.0.1:3307/rpg_game",
                "RPG_DB_CONNECT_PROBE_TIMEOUT_S": "not-a-number",
                "RPG_DB_ALLOW_INMEMORY_FALLBACK": "1",
            },
            clear=False,
        ), mock.patch("rpg.bootstrap.socket.create_connection", side_effect=OSError("refused")), mock.patch.object(
            bootstrap, "_build_mysql_game_service", side_effect=AssertionError("mysql path should be skipped")
        ):
            service = bootstrap.create_game_service()

        self.assertIsNotNone(service)

    def test_local_mysql_probe_uses_faster_default_timeout(self) -> None:
        with mock.patch.dict(
            os.environ,
            {"RPG_DATABASE_URL": "mysql+mysqlconnector://root@127.0.0.1:3307/rpg_game"},
            clear=False,
        ), mock.patch("rpg.bootstrap.socket.create_connection", side_effect=OSError("refused")) as create_conn:
            self.assertTrue(bootstrap._looks_like_local_mysql_unreachable(os.environ["RPG_DATABASE_URL"]))

        timeout = create_conn.call_args.kwargs.get("timeout")
        self.assertEqual(0.35, timeout)

    def test_create_game_service_tries_mysql_when_probe_succeeds(self) -> None:
        class _DummySocket:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        sentinel = object()
        with mock.patch.dict(
            os.environ,
            {"RPG_DATABASE_URL": "mysql+mysqlconnector://root@127.0.0.1:3307/rpg_game"},
            clear=False,
        ), mock.patch("rpg.bootstrap.socket.create_connection", return_value=_DummySocket()), mock.patch.object(
            bootstrap, "_build_mysql_game_service", return_value=sentinel
        ):
            service = bootstrap.create_game_service()

        self.assertIs(service, sentinel)

    def test_flavour_builder_tolerates_invalid_numeric_env(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "RPG_FLAVOUR_DATAMUSE_ENABLED": "1",
                "RPG_FLAVOUR_TIMEOUT_S": "bad",
                "RPG_FLAVOUR_RETRIES": "bad",
                "RPG_FLAVOUR_BACKOFF_S": "bad",
                "RPG_FLAVOUR_MAX_LINES": "bad",
            },
            clear=False,
        ):
            builder = bootstrap._build_encounter_intro_builder()

        self.assertTrue(callable(builder))


if __name__ == "__main__":
    unittest.main()
