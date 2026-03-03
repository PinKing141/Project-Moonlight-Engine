import contextlib
import io
import os
import sys
from pathlib import Path
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import rpg.__main__ as runtime_main


class MainEntryErrorHandlingTests(unittest.TestCase):
    def test_main_uses_wrapped_service_and_menu_hooks(self) -> None:
        output = io.StringIO()
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
        with mock.patch.object(runtime_main, "create_game_service", side_effect=RuntimeError("db unavailable")), mock.patch.object(
            runtime_main, "startup_loading_screen", return_value=contextlib.nullcontext()
        ), mock.patch("sys.stdout", output):
=======
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
        fake_service = object()
        with mock.patch.object(runtime_main, "_create_game_service", return_value=fake_service) as create_mock, mock.patch.object(
            runtime_main, "_open_main_menu"
        ) as menu_mock, mock.patch.object(runtime_main, "startup_loading_screen", return_value=contextlib.nullcontext()), mock.patch(
            "sys.stdout", output
        ):
>>>>>>> theirs
            runtime_main.main()

        create_mock.assert_called_once()
        menu_mock.assert_called_once_with(fake_service)

    def test_main_handles_runtime_exceptions_without_traceback(self) -> None:
        output = io.StringIO()
        with mock.patch.object(runtime_main, "_create_game_service", side_effect=RuntimeError("db unavailable")), mock.patch.object(
            runtime_main, "startup_loading_screen", return_value=contextlib.nullcontext()
        ), mock.patch("sys.stdout", output):
            runtime_main.main()

        create_mock.assert_called_once()
        menu_mock.assert_called_once_with(fake_service)

    def test_main_handles_runtime_exceptions_without_traceback(self) -> None:
        output = io.StringIO()
        with mock.patch.object(runtime_main, "_create_game_service", side_effect=RuntimeError("db unavailable")), mock.patch.object(
            runtime_main, "startup_loading_screen", return_value=contextlib.nullcontext()
        ), mock.patch("sys.stdout", output):
            runtime_main.main()

        create_mock.assert_called_once()
        menu_mock.assert_called_once_with(fake_service)

    def test_main_handles_runtime_exceptions_without_traceback(self) -> None:
        output = io.StringIO()
        with mock.patch.object(runtime_main, "_create_game_service", side_effect=RuntimeError("db unavailable")), mock.patch.object(
            runtime_main, "startup_loading_screen", return_value=contextlib.nullcontext()
        ), mock.patch("sys.stdout", output):
            runtime_main.main()

        create_mock.assert_called_once()
        menu_mock.assert_called_once_with(fake_service)

    def test_main_handles_runtime_exceptions_without_traceback(self) -> None:
        output = io.StringIO()
        with mock.patch.object(runtime_main, "_create_game_service", side_effect=RuntimeError("db unavailable")), mock.patch.object(
            runtime_main, "startup_loading_screen", return_value=contextlib.nullcontext()
        ), mock.patch("sys.stdout", output):
            runtime_main.main()

        text = output.getvalue()
        self.assertIn("An unexpected error occurred", text)
        self.assertIn("db unavailable", text)
        self.assertIn("Help:", text)
        self.assertNotIn("Traceback", text)

    def test_main_handles_keyboard_interrupt(self) -> None:
        output = io.StringIO()
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
        with mock.patch.object(runtime_main, "create_game_service", side_effect=KeyboardInterrupt), mock.patch.object(
=======
        with mock.patch.object(runtime_main, "_create_game_service", side_effect=KeyboardInterrupt), mock.patch.object(
>>>>>>> theirs
=======
        with mock.patch.object(runtime_main, "_create_game_service", side_effect=KeyboardInterrupt), mock.patch.object(
>>>>>>> theirs
=======
        with mock.patch.object(runtime_main, "_create_game_service", side_effect=KeyboardInterrupt), mock.patch.object(
>>>>>>> theirs
=======
        with mock.patch.object(runtime_main, "_create_game_service", side_effect=KeyboardInterrupt), mock.patch.object(
>>>>>>> theirs
            runtime_main, "startup_loading_screen", return_value=contextlib.nullcontext()
        ), mock.patch("sys.stdout", output):
            runtime_main.main()

        self.assertIn("Session ended", output.getvalue())

    def test_main_surfaces_mysql_connectivity_hint_without_silent_retry(self) -> None:
        output = io.StringIO()

        with mock.patch.dict(os.environ, {"RPG_DATABASE_URL": "mysql+mysqlconnector://root@127.0.0.1:3307/rpg_game"}, clear=False), mock.patch.object(
            runtime_main,
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
            "create_game_service",
=======
            "_create_game_service",
>>>>>>> theirs
=======
            "_create_game_service",
>>>>>>> theirs
=======
            "_create_game_service",
>>>>>>> theirs
=======
            "_create_game_service",
>>>>>>> theirs
            side_effect=RuntimeError("sqlalchemy.exc.OperationalError: connection refused"),
        ) as create_mock, mock.patch.object(
            runtime_main, "startup_loading_screen", return_value=contextlib.nullcontext()
        ), mock.patch("sys.stdout", output):
            runtime_main.main()

        text = output.getvalue()
        self.assertIn("An unexpected error occurred", text)
        self.assertIn("RPG_DB_ALLOW_INMEMORY_FALLBACK=1", text)
        self.assertEqual(create_mock.call_count, 1)

    def test_main_prints_migration_hint_for_rng_seed_schema_mismatch(self) -> None:
        output = io.StringIO()
        error = RuntimeError(
            "MySQL bootstrap probe failed: (mysql.connector.errors.ProgrammingError) "
            "1054 (42S22): Unknown column 'rng_seed' in 'field list'"
        )

<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
        with mock.patch.object(runtime_main, "create_game_service", side_effect=error), mock.patch.object(
=======
        with mock.patch.object(runtime_main, "_create_game_service", side_effect=error), mock.patch.object(
>>>>>>> theirs
=======
        with mock.patch.object(runtime_main, "_create_game_service", side_effect=error), mock.patch.object(
>>>>>>> theirs
=======
        with mock.patch.object(runtime_main, "_create_game_service", side_effect=error), mock.patch.object(
>>>>>>> theirs
=======
        with mock.patch.object(runtime_main, "_create_game_service", side_effect=error), mock.patch.object(
>>>>>>> theirs
            runtime_main, "startup_loading_screen", return_value=contextlib.nullcontext()
        ), mock.patch("sys.stdout", output):
            runtime_main.main()

        text = output.getvalue()
        self.assertIn("An unexpected error occurred", text)
        self.assertIn("python -m rpg.infrastructure.db.mysql.migrate", text)


if __name__ == "__main__":
    unittest.main()
