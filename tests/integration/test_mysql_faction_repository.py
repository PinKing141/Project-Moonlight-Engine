import sys
from pathlib import Path
import unittest
from unittest import mock

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.domain.models.faction import Faction
from rpg.infrastructure.db.mysql import repos as mysql_repos
from rpg.infrastructure.db.mysql.repos import MysqlFactionRepository


def _bootstrap_schema(engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE character (character_id INTEGER PRIMARY KEY, name TEXT NOT NULL)"))
        conn.execute(text("INSERT INTO character (character_id, name) VALUES (7, 'Rin')"))
        conn.execute(
            text(
                """
                CREATE TABLE faction (
                    faction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    slug TEXT,
                    alignment TEXT,
                    influence INTEGER
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE character_reputation (
                    character_reputation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    character_id INTEGER NOT NULL,
                    faction_id INTEGER NOT NULL,
                    reputation_score INTEGER NOT NULL,
                    updated_turn INTEGER NOT NULL,
                    UNIQUE(character_id, faction_id)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE reputation_history (
                    reputation_history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    character_id INTEGER NOT NULL,
                    faction_id INTEGER NOT NULL,
                    delta INTEGER NOT NULL,
                    score_before INTEGER NOT NULL,
                    score_after INTEGER NOT NULL,
                    reason TEXT,
                    changed_turn INTEGER NOT NULL,
                    created_at TEXT
                )
                """
            )
        )


class MysqlFactionRepositoryIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:", future=True)
        _bootstrap_schema(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.session_patcher = mock.patch.object(mysql_repos, "SessionLocal", self.SessionLocal)
        self.session_patcher.start()
        self.repo = MysqlFactionRepository()

    def tearDown(self) -> None:
        self.session_patcher.stop()
        self.engine.dispose()

    def test_save_and_get_round_trip_with_reputation_history(self) -> None:
        faction = Faction(
            id="wardens",
            name="Wardens",
            alignment="neutral",
            influence=3,
            reputation={"character:7": 5},
        )

        self.repo.save(faction)
        loaded = self.repo.get("wardens")

        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(5, loaded.reputation.get("character:7"))

        with self.SessionLocal() as session:
            count = session.execute(text("SELECT COUNT(*) FROM reputation_history")).scalar_one()
            self.assertEqual(1, int(count))

    def test_save_rolls_back_when_history_table_missing(self) -> None:
        with self.engine.begin() as conn:
            conn.execute(text("DROP TABLE reputation_history"))

        faction = Faction(
            id="wardens",
            name="Wardens",
            alignment="neutral",
            influence=3,
            reputation={"character:7": 8},
        )

        with self.assertRaises(Exception):
            self.repo.save(faction)

        with self.SessionLocal() as session:
            faction_count = session.execute(text("SELECT COUNT(*) FROM faction")).scalar_one()
            rep_count = session.execute(text("SELECT COUNT(*) FROM character_reputation")).scalar_one()
            self.assertEqual(0, int(faction_count), "Faction write should roll back when history write fails")
            self.assertEqual(0, int(rep_count), "Reputation write should roll back when history write fails")


if __name__ == "__main__":
    unittest.main()
