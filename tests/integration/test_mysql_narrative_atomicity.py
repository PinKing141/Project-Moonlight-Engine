import sys
from pathlib import Path
import unittest
from unittest import mock

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.domain.models.quest import QuestState
from rpg.infrastructure.db.mysql import repos as mysql_repos
from rpg.infrastructure.db.mysql.repos import MysqlNarrativeStateRepository


def _bootstrap_schema(engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE location (location_id INTEGER PRIMARY KEY)"))
        conn.execute(text("INSERT INTO location (location_id) VALUES (1)"))
        conn.execute(
            text(
                """
                CREATE TABLE quest_definition (
                    quest_definition_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    quest_slug TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    objective_kind TEXT NOT NULL,
                    target_count INTEGER NOT NULL,
                    reward_xp INTEGER NOT NULL,
                    reward_money INTEGER NOT NULL,
                    faction_id INTEGER,
                    source TEXT NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE character_active_quest (
                    character_active_quest_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    character_id INTEGER NOT NULL,
                    quest_definition_id INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    progress INTEGER NOT NULL,
                    target_count INTEGER NOT NULL,
                    accepted_turn INTEGER NOT NULL,
                    completed_turn INTEGER,
                    seed_key TEXT,
                    UNIQUE(character_id, quest_definition_id)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE location_history (
                    location_history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    location_id INTEGER NOT NULL,
                    changed_turn INTEGER NOT NULL,
                    flag_key TEXT NOT NULL,
                    old_value TEXT,
                    new_value TEXT,
                    reason TEXT,
                    created_at TEXT
                )
                """
            )
        )


class MysqlNarrativeAtomicityIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:", future=True)
        _bootstrap_schema(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.session_patcher = mock.patch.object(mysql_repos, "SessionLocal", self.SessionLocal)
        self.session_patcher.start()
        self.repo = MysqlNarrativeStateRepository()

    def tearDown(self) -> None:
        self.session_patcher.stop()
        self.engine.dispose()

    def test_save_active_with_history_rolls_back_when_history_insert_fails(self) -> None:
        # No quest_history table exists, so history insert should fail after active upsert.
        with self.assertRaises(Exception):
            self.repo.save_active_with_history(
                character_id=7,
                state=QuestState(template_slug="first_hunt", status="active", progress=1, accepted_turn=3),
                target_count=2,
                seed_key="quest:first_hunt:123",
                action="accepted",
                action_turn=3,
                payload_json="{}",
            )

        with self.SessionLocal() as session:
            active_count = session.execute(text("SELECT COUNT(*) FROM character_active_quest")).scalar_one()
            definition_count = session.execute(text("SELECT COUNT(*) FROM quest_definition")).scalar_one()
            self.assertEqual(0, int(active_count), "Active quest row should roll back with failed history write")
            self.assertEqual(0, int(definition_count), "Quest definition insert should also roll back")

    def test_location_history_write_persists_on_success(self) -> None:
        self.repo.record_flag_change(
            location_id=1,
            changed_turn=4,
            flag_key="hazard:last_resolution",
            old_value=None,
            new_value="Quicksand",
            reason="explore_hazard_failed_check",
        )

        with self.SessionLocal() as session:
            count = session.execute(text("SELECT COUNT(*) FROM location_history")).scalar_one()
            self.assertEqual(1, int(count))


if __name__ == "__main__":
    unittest.main()
