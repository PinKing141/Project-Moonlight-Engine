import sys
from pathlib import Path
import unittest
from unittest import mock

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.domain.models.entity import Entity
from rpg.infrastructure.db.mysql import repos as mysql_repos
from rpg.infrastructure.db.mysql.repos import MysqlEntityRepository, MysqlWorldRepository


def _bootstrap_entity_schema(engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE entity_type (
                    entity_type_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE entity (
                    entity_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entity_type_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    level INTEGER,
                    armour_class INTEGER,
                    attack_bonus INTEGER,
                    damage_dice TEXT,
                    hp_max INTEGER,
                    kind TEXT
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE location (
                    location_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    x INTEGER,
                    y INTEGER,
                    place_id INTEGER
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE entity_location (
                    entity_location_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entity_id INTEGER NOT NULL,
                    location_id INTEGER NOT NULL,
                    UNIQUE(entity_id)
                )
                """
            )
        )
        conn.execute(text("INSERT INTO location (location_id, x, y, place_id) VALUES (1, 0, 0, 1), (2, 1, 0, 1)"))


def _bootstrap_world_schema(engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE world (
                    world_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    current_turn INTEGER DEFAULT 0,
                    threat_level INTEGER DEFAULT 0,
                    flags TEXT
                )
                """
            )
        )


class MysqlEntityRepositoryIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:", future=True)
        _bootstrap_entity_schema(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.session_patcher = mock.patch.object(mysql_repos, "SessionLocal", self.SessionLocal)
        self.session_patcher.start()
        self.repo = MysqlEntityRepository()

    def tearDown(self) -> None:
        self.session_patcher.stop()
        self.engine.dispose()

    def test_upsert_creates_updates_and_relocates_entities(self) -> None:
        goblin = Entity(id=0, name="Goblin", level=1, hp=6, armour_class=12, attack_bonus=3, damage_die="1d6+1")

        first = self.repo.upsert_entities([goblin], location_id=1)
        self.assertEqual((1, 0, 1), (first.created, first.updated, first.attached))

        stronger = Entity(id=0, name="Goblin", level=2, hp=9, armour_class=13, attack_bonus=4, damage_die="1d8+2")
        second = self.repo.upsert_entities([stronger], location_id=2)
        self.assertEqual((0, 1, 1), (second.created, second.updated, second.attached))

        with self.SessionLocal() as session:
            row = session.execute(
                text(
                    """
                    SELECT entity_id, level, armour_class, attack_bonus, damage_dice, hp_max, kind
                    FROM entity
                    WHERE name = 'Goblin'
                    """
                )
            ).first()
            self.assertIsNotNone(row)
            self.assertEqual(2, row.level)
            self.assertEqual("1d8+2", row.damage_dice)
            self.assertEqual(9, row.hp_max)

            location_id = session.execute(
                text(
                    """
                    SELECT location_id
                    FROM entity_location
                    WHERE entity_id = :entity_id
                    """
                ),
                {"entity_id": row.entity_id},
            ).scalar()
            self.assertEqual(2, location_id)


class MysqlWorldRepositoryIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:", future=True)
        _bootstrap_world_schema(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.session_patcher = mock.patch.object(mysql_repos, "SessionLocal", self.SessionLocal)
        self.session_patcher.start()
        self.repo = MysqlWorldRepository()

    def tearDown(self) -> None:
        self.session_patcher.stop()
        self.engine.dispose()

    def test_load_default_seeds_when_missing_and_save_persists_changes(self) -> None:
        world = self.repo.load_default()
        self.assertEqual("Default World", world.name)
        self.assertEqual(0, world.current_turn)

        world.advance_turns(5)
        world.threat_level = 3
        world.flags = {"season": "winter"}
        self.repo.save(world)

        with self.SessionLocal() as session:
            row = session.execute(
                text(
                    """
                    SELECT name, current_turn, threat_level, flags
                    FROM world
                    WHERE world_id = :wid
                    """
                ),
                {"wid": world.id},
            ).first()
            self.assertEqual(5, row.current_turn)
            self.assertEqual(3, row.threat_level)
            self.assertEqual('{"season": "winter"}', row.flags)

    def test_load_default_recovers_from_malformed_flags_payload(self) -> None:
        with self.SessionLocal() as session:
            session.execute(
                text(
                    """
                    INSERT INTO world (name, current_turn, threat_level, flags)
                    VALUES ('Broken World', 4, 2, 'not-json')
                    """
                )
            )
            session.commit()

        world = self.repo.load_default()

        self.assertEqual("Broken World", world.name)
        self.assertEqual(4, world.current_turn)
        self.assertEqual(2, world.threat_level)
        self.assertEqual({}, world.flags)


if __name__ == "__main__":
    unittest.main()
