import sys
from pathlib import Path
import unittest
from unittest import mock

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rpg.infrastructure.db.mysql import repos as mysql_repos
from rpg.infrastructure.db.mysql.repos import MysqlEntityRepository


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


if __name__ == "__main__":
    unittest.main()
