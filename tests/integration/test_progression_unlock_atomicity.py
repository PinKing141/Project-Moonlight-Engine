import sys
from pathlib import Path
import unittest
from unittest import mock

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.domain.models.character import Character
from rpg.domain.models.world import World
from rpg.infrastructure.db.mysql import atomic_persistence, repos as mysql_repos
from rpg.infrastructure.db.mysql.atomic_persistence import save_character_and_world_atomic
from rpg.infrastructure.db.mysql.repos import MysqlCharacterRepository


class ProgressionUnlockAtomicityTests(unittest.TestCase):
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
                        hp_max INTEGER NOT NULL,
                        armour_class INTEGER,
                        armor INTEGER,
                        attack_bonus INTEGER,
                        damage_die TEXT,
                        speed INTEGER
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
                        flags TEXT,
                        rng_seed INTEGER DEFAULT 1
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE character_progression_unlock (
                        character_progression_unlock_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        character_id INTEGER NOT NULL,
                        unlock_kind TEXT NOT NULL,
                        unlock_key TEXT NOT NULL,
                        unlocked_level INTEGER NOT NULL,
                        created_turn INTEGER NOT NULL DEFAULT 0,
                        UNIQUE(character_id, unlock_kind, unlock_key)
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO world (world_id, name, current_turn, threat_level, flags, rng_seed)
                    VALUES (1, 'Default World', 0, 0, '{}', 1)
                    """
                )
            )

        self.atomic_patcher = mock.patch.object(atomic_persistence, "SessionLocal", self.SessionLocal)
        self.repos_patcher = mock.patch.object(mysql_repos, "SessionLocal", self.SessionLocal)
        self.atomic_patcher.start()
        self.repos_patcher.start()

    def tearDown(self) -> None:
        self.atomic_patcher.stop()
        self.repos_patcher.stop()
        self.engine.dispose()

    def test_progression_unlock_operation_commits_in_atomic_transaction(self) -> None:
        character = Character(id=20, name="UnlockHero", level=2, xp=30, money=1, location_id=1)
        world = World(id=1, name="Default World", current_turn=5, threat_level=1, flags={})
        char_repo = MysqlCharacterRepository()

        unlock_op = char_repo.build_progression_unlock_operation(
            character_id=20,
            unlock_kind="growth_choice",
            unlock_key="level_2_feat",
            unlocked_level=2,
            created_turn=5,
        )

        save_character_and_world_atomic(character, world, operations=[unlock_op])

        with self.SessionLocal() as session:
            unlock_count = session.execute(
                text("SELECT COUNT(*) FROM character_progression_unlock WHERE character_id = 20")
            ).scalar_one()
            self.assertEqual(1, int(unlock_count))


if __name__ == "__main__":
    unittest.main()
