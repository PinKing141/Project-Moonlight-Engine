import sys
from pathlib import Path
import unittest
from unittest import mock

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.domain.models.character import Character
from rpg.domain.models.world import World
from rpg.infrastructure.db.mysql import atomic_persistence
from rpg.infrastructure.db.mysql.atomic_persistence import save_character_and_world_atomic


class AtomicPersistenceIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:", future=True)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)

        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE "character" (
                        character_id INTEGER PRIMARY KEY,
                        name TEXT NOT NULL,
                        alive INTEGER NOT NULL,
                        level INTEGER NOT NULL,
                        xp INTEGER NOT NULL,
                        money INTEGER NOT NULL,
                        character_type_id INTEGER NOT NULL,
                        hp_current INTEGER NOT NULL,
                        hp_max INTEGER NOT NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE character_location (
                        character_id INTEGER PRIMARY KEY,
                        location_id INTEGER NOT NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE world (
                        world_id INTEGER PRIMARY KEY,
                        name TEXT NOT NULL,
                        current_turn INTEGER NOT NULL,
                        threat_level INTEGER NOT NULL,
                        flags TEXT
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO world (world_id, name, current_turn, threat_level, flags)
                    VALUES (1, 'Default World', 0, 0, '{}')
                    """
                )
            )

        self.session_patcher = mock.patch.object(atomic_persistence, "SessionLocal", self.SessionLocal)
        self.session_patcher.start()

    def tearDown(self) -> None:
        self.session_patcher.stop()
        self.engine.dispose()

    def test_atomic_save_commits_character_and_world_together(self) -> None:
        character = Character(
            id=1,
            name="AtomicHero",
            level=2,
            xp=15,
            money=3,
            character_type_id=1,
            location_id=7,
            hp_current=9,
            hp_max=12,
        )
        world = World(id=1, name="Default World", current_turn=4, threat_level=2, flags={"season": "rain"})

        save_character_and_world_atomic(character, world)

        with self.SessionLocal() as session:
            char_row = session.execute(
                text("SELECT name, hp_current, hp_max FROM \"character\" WHERE character_id = 1")
            ).first()
            loc_row = session.execute(
                text("SELECT location_id FROM character_location WHERE character_id = 1")
            ).first()
            world_row = session.execute(
                text("SELECT current_turn, threat_level FROM world WHERE world_id = 1")
            ).first()

            self.assertEqual("AtomicHero", char_row.name)
            self.assertEqual(7, loc_row.location_id)
            self.assertEqual(4, world_row.current_turn)
            self.assertEqual(2, world_row.threat_level)

    def test_atomic_save_rolls_back_on_failure(self) -> None:
        character = Character(
            id=9,
            name="RollbackHero",
            level=1,
            xp=0,
            money=0,
            character_type_id=1,
            location_id=2,
            hp_current=10,
            hp_max=10,
        )
        world = World(id=1, name="Default World", current_turn=1, threat_level=1, flags={})

        with mock.patch.object(atomic_persistence, "_upsert_world_row", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                save_character_and_world_atomic(character, world)

        with self.SessionLocal() as session:
            char_count = session.execute(
                text("SELECT COUNT(*) FROM \"character\" WHERE character_id = 9")
            ).scalar_one()
            world_turn = session.execute(
                text("SELECT current_turn FROM world WHERE world_id = 1")
            ).scalar_one()

            self.assertEqual(0, char_count, "Character write should roll back when world save fails")
            self.assertEqual(0, world_turn, "World row should remain unchanged on rollback")


if __name__ == "__main__":
    unittest.main()
