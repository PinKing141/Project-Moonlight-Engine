import re
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))


class MigrationChainTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parents[2]
        self.migration_dir = self.root / "src" / "rpg" / "infrastructure" / "db" / "migrations"
        self.apply_all = self.migration_dir / "_apply_all.sql"

    def test_numbered_migrations_are_contiguous(self) -> None:
        numbered = sorted(
            [path.name for path in self.migration_dir.glob("[0-9][0-9][0-9]_*.sql")]
        )
        self.assertTrue(numbered, "No numbered migration files found")

        numbers = [int(name.split("_", 1)[0]) for name in numbered]
        expected = list(range(numbers[0], numbers[0] + len(numbers)))
        self.assertEqual(expected, numbers, "Migration numbering must be contiguous")

    def test_apply_all_references_all_numbered_migrations_in_order(self) -> None:
        content = self.apply_all.read_text(encoding="utf-8")
        sources = [line.strip() for line in content.splitlines() if line.strip().upper().startswith("SOURCE ")]

        numbered = sorted(
            [path.name for path in self.migration_dir.glob("[0-9][0-9][0-9]_*.sql")]
        )
        apply_lines_for_numbered = [line for line in sources if re.search(r"\/[0-9]{3}_|\.[0-9]{3}_|[0-9]{3}_", line)]

        for migration in numbered:
            self.assertTrue(
                any(migration in line for line in apply_lines_for_numbered),
                f"Missing migration in apply-all: {migration}",
            )

        found_order = [
            next((name for name in numbered if name in line), None)
            for line in apply_lines_for_numbered
        ]
        found_order = [name for name in found_order if name is not None]
        self.assertEqual(numbered, found_order, "apply-all migration order must match filename order")

    def test_apply_all_uses_no_absolute_host_paths(self) -> None:
        content = self.apply_all.read_text(encoding="utf-8")
        self.assertNotRegex(content, r"[A-Za-z]:/", "Windows absolute paths are not portable")
        self.assertNotRegex(content, r"^\s*SOURCE\s+/(?!\.)", "Unix absolute paths are not portable")

    def test_migrations_do_not_use_mysql_unsupported_create_index_if_not_exists(self) -> None:
        for migration in self.migration_dir.glob("[0-9][0-9][0-9]_*.sql"):
            content = migration.read_text(encoding="utf-8")
            self.assertNotRegex(
                content,
                r"CREATE\s+INDEX\s+IF\s+NOT\s+EXISTS",
                f"Unsupported MySQL syntax found in {migration.name}",
            )
            self.assertNotRegex(
                content,
                r"ADD\s+COLUMN\s+IF\s+NOT\s+EXISTS",
                f"Unsupported MySQL syntax found in {migration.name}",
            )


if __name__ == "__main__":
    unittest.main()
