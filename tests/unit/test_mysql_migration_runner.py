import sys
import tempfile
from pathlib import Path
import unittest
from unittest import mock

from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.infrastructure.db.mysql.migrate import (
    MigrationFilePlan,
    build_migration_plan,
    build_linear_migration_plan,
    build_seed_migration_plan,
    discover_linear_migration_files,
    execute_linear_migration_plan,
)


class MysqlMigrationRunnerTests(unittest.TestCase):
    def test_real_linear_plan_starts_with_numbered_baseline_schema(self) -> None:
        file_names = [plan.file_path.name for plan in build_linear_migration_plan()]
        self.assertTrue(file_names, "Expected at least one migration file in strict linear plan")
        self.assertEqual("000_base_schema.sql", file_names[0])

    def test_build_plan_resolves_source_chain_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sub = root / "migrations"
            sub.mkdir(parents=True, exist_ok=True)

            (root / "base.sql").write_text("CREATE TABLE t1(id INT);\n", encoding="utf-8")
            (sub / "001_first.sql").write_text("INSERT INTO t1(id) VALUES (1);\n", encoding="utf-8")
            (sub / "002_second.sql").write_text("INSERT INTO t1(id) VALUES (2);\n", encoding="utf-8")
            (sub / "_apply_all.sql").write_text(
                "SOURCE ../base.sql;\nSOURCE ./001_first.sql;\nSOURCE ./002_second.sql;\n",
                encoding="utf-8",
            )

            plan = build_migration_plan(sub / "_apply_all.sql")

            self.assertEqual(4, len(plan.files))
            self.assertEqual(3, len(plan.statements))
            self.assertIn("CREATE TABLE t1(id INT)", plan.statements[0])
            self.assertIn("INSERT INTO t1(id) VALUES (1)", plan.statements[1])
            self.assertIn("INSERT INTO t1(id) VALUES (2)", plan.statements[2])

    def test_build_plan_ignores_source_like_text_inside_comments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "_apply_all.sql"
            script.write_text(
                "-- SOURCE ./not_real.sql;\n# SOURCE ./also_not_real.sql;\nCREATE TABLE t2(id INT);\n",
                encoding="utf-8",
            )

            plan = build_migration_plan(script)

            self.assertEqual(1, len(plan.files))
            self.assertEqual(1, len(plan.statements))
            self.assertIn("CREATE TABLE t2(id INT)", plan.statements[0])

    def test_splitter_handles_semicolons_inside_strings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "_apply_all.sql"
            script.write_text(
                "INSERT INTO demo(txt) VALUES ('alpha;beta');\nINSERT INTO demo(txt) VALUES ('gamma');\n",
                encoding="utf-8",
            )

            plan = build_migration_plan(script)

            self.assertEqual(2, len(plan.statements))
            self.assertIn("alpha;beta", plan.statements[0])
            self.assertIn("gamma", plan.statements[1])

    def test_discover_linear_migrations_rejects_legacy_chain_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            migration_dir = Path(tmp) / "migrations"
            migration_dir.mkdir(parents=True, exist_ok=True)
            (migration_dir / "001_first.sql").write_text("SELECT 1;", encoding="utf-8")
            (migration_dir / "_legacy_001_chain.sql").write_text("SELECT 1;", encoding="utf-8")

            with mock.patch("rpg.infrastructure.db.mysql.migrate._migrations_dir", return_value=migration_dir):
                files = discover_linear_migration_files()

            self.assertEqual(["001_first.sql"], [path.name for path in files])

    def test_build_linear_plan_validates_sequential_numbering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            migration_dir = Path(tmp) / "migrations"
            migration_dir.mkdir(parents=True, exist_ok=True)
            (migration_dir / "001_first.sql").write_text("SELECT 1;", encoding="utf-8")
            (migration_dir / "003_third.sql").write_text("SELECT 3;", encoding="utf-8")

            with mock.patch("rpg.infrastructure.db.mysql.migrate._migrations_dir", return_value=migration_dir):
                with self.assertRaises(ValueError):
                    build_linear_migration_plan()

    def test_build_linear_plan_excludes_seed_migrations_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            migration_dir = Path(tmp) / "migrations"
            migration_dir.mkdir(parents=True, exist_ok=True)
            (migration_dir / "001_first.sql").write_text("SELECT 1;", encoding="utf-8")
            (migration_dir / "002_seed_factions.sql").write_text("INSERT INTO faction(name) VALUES ('x');", encoding="utf-8")

            with mock.patch("rpg.infrastructure.db.mysql.migrate._migrations_dir", return_value=migration_dir):
                file_names = [plan.file_path.name for plan in build_linear_migration_plan()]

            self.assertEqual(["001_first.sql"], file_names)

    def test_build_linear_plan_can_include_seed_migrations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            migration_dir = Path(tmp) / "migrations"
            migration_dir.mkdir(parents=True, exist_ok=True)
            (migration_dir / "001_first.sql").write_text("SELECT 1;", encoding="utf-8")
            (migration_dir / "002_seed_factions.sql").write_text("INSERT INTO faction(name) VALUES ('x');", encoding="utf-8")

            with mock.patch("rpg.infrastructure.db.mysql.migrate._migrations_dir", return_value=migration_dir):
                file_names = [plan.file_path.name for plan in build_linear_migration_plan(include_seed_data=True)]

            self.assertEqual(["001_first.sql", "002_seed_factions.sql"], file_names)

    def test_build_seed_plan_includes_only_seed_migrations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            migration_dir = Path(tmp) / "migrations"
            migration_dir.mkdir(parents=True, exist_ok=True)
            (migration_dir / "001_first.sql").write_text("SELECT 1;", encoding="utf-8")
            (migration_dir / "002_seed_factions.sql").write_text("INSERT INTO faction(name) VALUES ('x');", encoding="utf-8")
            (migration_dir / "003_seed_locations.sql").write_text("INSERT INTO place(name) VALUES ('Town');", encoding="utf-8")

            with mock.patch("rpg.infrastructure.db.mysql.migrate._migrations_dir", return_value=migration_dir):
                file_names = [plan.file_path.name for plan in build_seed_migration_plan()]

            self.assertEqual(["002_seed_factions.sql", "003_seed_locations.sql"], file_names)

    def test_execute_linear_plan_tracks_schema_migrations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_url = f"sqlite+pysqlite:///{Path(tmp) / 'migrate_test.db'}"
            f1 = Path(tmp) / "001_first.sql"
            f2 = Path(tmp) / "002_second.sql"
            f1.write_text("CREATE TABLE IF NOT EXISTS demo(id INTEGER PRIMARY KEY, name TEXT);", encoding="utf-8")
            f2.write_text("INSERT INTO demo(id, name) VALUES (1, 'one');", encoding="utf-8")

            file_plans = [
                MigrationFilePlan(file_path=f1, statements=["CREATE TABLE IF NOT EXISTS demo(id INTEGER PRIMARY KEY, name TEXT)"]),
                MigrationFilePlan(file_path=f2, statements=["INSERT INTO demo(id, name) VALUES (1, 'one')"]),
            ]

            applied_files, executed = execute_linear_migration_plan(file_plans, db_url)
            self.assertEqual(2, applied_files)
            self.assertEqual(2, executed)

            applied_files_second, executed_second = execute_linear_migration_plan(file_plans, db_url)
            self.assertEqual(0, applied_files_second)
            self.assertEqual(0, executed_second)

            engine = create_engine(db_url, future=True)
            with engine.begin() as conn:
                rows = conn.execute(text("SELECT migration_name FROM schema_migrations ORDER BY migration_name")).all()
                self.assertEqual([("001_first.sql",), ("002_second.sql",)], [(row[0],) for row in rows])
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
