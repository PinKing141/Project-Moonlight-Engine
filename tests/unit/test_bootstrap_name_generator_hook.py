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

    def test_create_game_service_skips_mysql_when_localhost_unreachable(self) -> None:
        with mock.patch.dict(
            os.environ,
            {"RPG_DATABASE_URL": "mysql+mysqlconnector://root@127.0.0.1:3307/rpg_game"},
            clear=False,
        ), mock.patch("rpg.bootstrap.socket.create_connection", side_effect=OSError("refused")), mock.patch.object(
            bootstrap, "_build_mysql_game_service", side_effect=AssertionError("mysql path should be skipped")
        ):
            service = bootstrap.create_game_service()

        self.assertIsNotNone(service)

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


if __name__ == "__main__":
    unittest.main()
