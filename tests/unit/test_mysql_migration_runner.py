import sys
import tempfile
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.infrastructure.db.mysql.migrate import build_migration_plan


class MysqlMigrationRunnerTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
