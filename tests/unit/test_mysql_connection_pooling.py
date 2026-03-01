import os
import sys
from pathlib import Path
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.infrastructure.db.mysql import connection


class MysqlConnectionPoolingTests(unittest.TestCase):
    def test_build_engine_kwargs_for_mysql_enables_pool_settings(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "RPG_DB_POOL_RECYCLE_SECONDS": "1234",
                "RPG_DB_POOL_SIZE": "7",
                "RPG_DB_MAX_OVERFLOW": "9",
                "RPG_DB_POOL_TIMEOUT_SECONDS": "21",
            },
            clear=False,
        ):
            kwargs = connection._build_engine_kwargs("mysql+mysqlconnector://root@localhost:3306/rpg_game")

        self.assertEqual(False, kwargs.get("echo"))
        self.assertEqual(True, kwargs.get("future"))
        self.assertEqual(True, kwargs.get("pool_pre_ping"))
        self.assertEqual(1234, kwargs.get("pool_recycle"))
        self.assertEqual(7, kwargs.get("pool_size"))
        self.assertEqual(9, kwargs.get("max_overflow"))
        self.assertEqual(21, kwargs.get("pool_timeout"))

    def test_build_engine_kwargs_for_mysql_uses_safe_defaults_when_env_invalid(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "RPG_DB_POOL_RECYCLE_SECONDS": "oops",
                "RPG_DB_POOL_SIZE": "-5",
                "RPG_DB_MAX_OVERFLOW": "-4",
                "RPG_DB_POOL_TIMEOUT_SECONDS": "0",
            },
            clear=False,
        ):
            kwargs = connection._build_engine_kwargs("mysql+mysqlconnector://root@localhost:3306/rpg_game")

        self.assertEqual(1800, kwargs.get("pool_recycle"))
        self.assertEqual(1, kwargs.get("pool_size"))
        self.assertEqual(0, kwargs.get("max_overflow"))
        self.assertEqual(1, kwargs.get("pool_timeout"))

    def test_build_engine_kwargs_for_non_mysql_omits_pool_specific_options(self) -> None:
        kwargs = connection._build_engine_kwargs("sqlite+pysqlite:///:memory:")

        self.assertEqual(False, kwargs.get("echo"))
        self.assertEqual(True, kwargs.get("future"))
        self.assertNotIn("pool_pre_ping", kwargs)
        self.assertNotIn("pool_size", kwargs)
        self.assertNotIn("max_overflow", kwargs)
        self.assertNotIn("pool_timeout", kwargs)


if __name__ == "__main__":
    unittest.main()
