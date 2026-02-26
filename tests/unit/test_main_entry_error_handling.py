import io
import os
import sys
from pathlib import Path
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import rpg.__main__ as runtime_main


class MainEntryErrorHandlingTests(unittest.TestCase):
    def test_main_handles_runtime_exceptions_without_traceback(self) -> None:
        output = io.StringIO()
        with mock.patch.object(runtime_main, "create_game_service", side_effect=RuntimeError("db unavailable")), mock.patch(
            "sys.stdout", output
        ):
            runtime_main.main()

        text = output.getvalue()
        self.assertIn("An unexpected error occurred", text)
        self.assertIn("db unavailable", text)
        self.assertIn("Help:", text)
        self.assertNotIn("Traceback", text)

    def test_main_handles_keyboard_interrupt(self) -> None:
        output = io.StringIO()
        with mock.patch.object(runtime_main, "create_game_service", side_effect=KeyboardInterrupt), mock.patch(
            "sys.stdout", output
        ):
            runtime_main.main()

        self.assertIn("Session ended", output.getvalue())

    def test_main_retries_inmemory_when_mysql_connection_fails(self) -> None:
        output = io.StringIO()

        primary_service = object()
        fallback_service = object()

        def menu_side_effect(service):
            if service is primary_service:
                raise RuntimeError(
                    "(mysql.connector.errors.DatabaseError) 2003 (HY000): Can't connect to MySQL server on '127.0.0.1:3307' (10061)"
                )
            return None

        with mock.patch.dict(os.environ, {"RPG_DATABASE_URL": "mysql+mysqlconnector://root@127.0.0.1:3307/rpg_game"}, clear=False), mock.patch.object(
            runtime_main, "create_game_service", side_effect=[primary_service, fallback_service]
        ) as create_mock, mock.patch.object(runtime_main, "main_menu", side_effect=menu_side_effect), mock.patch(
            "sys.stdout", output
        ):
            runtime_main.main()

        text = output.getvalue()
        self.assertIn("retrying in-memory mode", text)
        self.assertEqual(create_mock.call_count, 2)
        self.assertNotIn("An unexpected error occurred", text)


if __name__ == "__main__":
    unittest.main()
