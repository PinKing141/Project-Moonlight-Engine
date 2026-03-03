import sys
from pathlib import Path
import unittest
from unittest import mock

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rpg.infrastructure.db.mysql import repos as mysql_repos
from rpg.infrastructure.db.mysql.repos import MysqlClassRepository, MysqlEntityRepository
from rpg.domain.services.class_progression_catalog import progression_rows_for_class


class MysqlEntityRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:", future=True)
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE entity (
                        entity_id INTEGER PRIMARY KEY,
                        name TEXT NOT NULL,
                        level INTEGER,
                        armour_class INTEGER,
                        attack_bonus INTEGER,
                        damage_dice TEXT,
                        hp_max INTEGER,
                        kind TEXT,
                        tags_json TEXT,
                        resistances_json TEXT
                    )
                    """
                )
            )

        self.SessionLocal = sessionmaker(
            bind=self.engine, autoflush=False, autocommit=False
        )
        self.session_patcher = mock.patch.object(
            mysql_repos, "SessionLocal", self.SessionLocal
        )
        self.session_patcher.start()
        self.repo = MysqlEntityRepository()

    def tearDown(self) -> None:
        self.session_patcher.stop()
        self.engine.dispose()

    def test_get_many_supports_multiple_ids(self) -> None:
        with self.SessionLocal.begin() as session:
            session.execute(
                text(
                    """
                    INSERT INTO entity (entity_id, name, level)
                    VALUES (1, 'Slime', 1), (2, 'Dragon Whelp', 4)
                    """
                )
            )

        entities = self.repo.get_many([1, 2])

        self.assertEqual({1, 2}, {entity.id for entity in entities})
        self.assertEqual({"Slime", "Dragon Whelp"}, {entity.name for entity in entities})


class MysqlClassRepositoryProgressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:", future=True)
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE class (
                        class_id INTEGER PRIMARY KEY,
                        name TEXT NOT NULL,
                        open5e_slug TEXT,
                        hit_die TEXT,
                        primary_ability TEXT,
                        source TEXT
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE class_progression_row (
                        class_progression_row_id INTEGER PRIMARY KEY,
                        class_id INTEGER NOT NULL,
                        level INTEGER NOT NULL,
                        gains TEXT NOT NULL
                    )
                    """
                )
            )

        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.session_patcher = mock.patch.object(mysql_repos, "SessionLocal", self.SessionLocal)
        self.session_patcher.start()
        self.repo = MysqlClassRepository()

    def tearDown(self) -> None:
        self.session_patcher.stop()
        self.engine.dispose()

    def test_list_progression_rows_reads_sql_when_table_present(self) -> None:
        with self.SessionLocal.begin() as session:
            session.execute(
                text(
                    """
                    INSERT INTO class (class_id, name, open5e_slug, hit_die, primary_ability, source)
                    VALUES (1, 'Fighter', 'fighter', 'd10', 'strength', 'seed')
                    """
                )
            )
            session.execute(
                text(
                    """
                    INSERT INTO class_progression_row (class_progression_row_id, class_id, level, gains)
                    VALUES
                        (1, 1, 1, 'Fighting Style, Second Wind'),
                        (2, 1, 2, 'Action Surge')
                    """
                )
            )

        rows = self.repo.list_progression_rows("fighter")

        self.assertEqual(2, len(rows))
        self.assertEqual(1, rows[0].level)
        self.assertIn("Fighting Style", rows[0].gains)
        self.assertEqual(2, rows[1].level)
        self.assertIn("Action Surge", rows[1].gains)

    def test_list_progression_rows_falls_back_when_sql_table_missing(self) -> None:
        with self.engine.begin() as conn:
            conn.execute(text("DROP TABLE class_progression_row"))

        rows = self.repo.list_progression_rows("wizard")

        self.assertEqual(progression_rows_for_class("wizard"), rows)


if __name__ == "__main__":
    unittest.main()
