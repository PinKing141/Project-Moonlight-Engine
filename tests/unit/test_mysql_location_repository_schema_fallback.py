import sys
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from sqlalchemy.exc import ProgrammingError

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.infrastructure.db.mysql.repos import MysqlLocationRepository


class _SessionContext:
    def __init__(self, session):
        self._session = session

    def __enter__(self):
        return self._session

    def __exit__(self, exc_type, exc, tb):
        return False


class MysqlLocationRepositorySchemaFallbackTests(unittest.TestCase):
    def test_get_starting_location_falls_back_when_new_columns_missing(self) -> None:
        repo = MysqlLocationRepository()
        missing_column = ProgrammingError("SELECT", {}, Exception("Unknown column 'l.biome_key' in 'field list'"))
        row = SimpleNamespace(
            location_id=7,
            x=12,
            y=34,
            place_name="Rivertown",
            biome_key="wilderness",
            hazard_profile_key="standard",
            environmental_flags=None,
        )

        first_result = MagicMock()
        first_result.first.side_effect = missing_column
        second_result = MagicMock()
        second_result.first.return_value = row

        session = MagicMock()
        session.execute.side_effect = [first_result, second_result]

        with patch("rpg.infrastructure.db.mysql.repos.SessionLocal", return_value=_SessionContext(session)):
            location = repo.get_starting_location()

        self.assertIsNotNone(location)
        self.assertEqual(7, location.id)
        self.assertEqual("Rivertown", location.name)
        self.assertEqual("wilderness", location.biome)
        self.assertEqual("standard", location.hazard_profile.key)

        fallback_sql = str(session.execute.call_args_list[1].args[0])
        self.assertIn("'wilderness' AS biome_key", fallback_sql)

    def test_get_falls_back_when_new_columns_missing(self) -> None:
        repo = MysqlLocationRepository()
        missing_column = ProgrammingError("SELECT", {}, Exception("Unknown column 'l.hazard_profile_key' in 'field list'"))
        row = SimpleNamespace(
            location_id=3,
            x=1,
            y=2,
            place_name="Stonekeep",
            biome_key="wilderness",
            hazard_profile_key="standard",
            environmental_flags=None,
        )

        first_result = MagicMock()
        first_result.first.side_effect = missing_column
        second_result = MagicMock()
        second_result.first.return_value = row

        session = MagicMock()
        session.execute.side_effect = [first_result, second_result]

        with patch("rpg.infrastructure.db.mysql.repos.SessionLocal", return_value=_SessionContext(session)):
            location = repo.get(3)

        self.assertIsNotNone(location)
        self.assertEqual(3, location.id)
        self.assertEqual("Stonekeep", location.name)


if __name__ == "__main__":
    unittest.main()
