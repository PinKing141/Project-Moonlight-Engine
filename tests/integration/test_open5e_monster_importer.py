import sys
from pathlib import Path
import unittest
from unittest import mock

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.infrastructure.db.mysql import repos as mysql_repos
from rpg.infrastructure.db.mysql.open5e_monster_importer import Open5eMonsterImporter
from rpg.infrastructure.db.mysql.repos import MysqlEntityRepository


class FakeOpen5eClient:
    def __init__(self, pages):
        self.pages = pages

    def list_monsters(self, page: int = 1) -> dict:
        return {"results": self.pages.get(page, [])}

    def close(self) -> None:
        pass


def _bootstrap_schema(engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE entity_type (
                    entity_type_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL
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
        conn.execute(
            text(
                """
                INSERT INTO location (location_id, x, y, place_id)
                VALUES (1, 0, 0, 1), (2, 1, 0, 1)
                """
            )
        )


class Open5eMonsterImporterIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:", future=True)
        _bootstrap_schema(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.session_patcher = mock.patch.object(mysql_repos, "SessionLocal", self.SessionLocal)
        self.session_patcher.start()
        self.repo = MysqlEntityRepository()

    def tearDown(self) -> None:
        self.session_patcher.stop()
        self.engine.dispose()

    def test_importer_persists_monsters_and_locations(self) -> None:
        client = FakeOpen5eClient(
            pages={
                1: [
                    {
                        "name": "Dire Wolf",
                        "challenge_rating": "2",
                        "armor_class": 14,
                        "hit_points": 37,
                        "type": "beast",
                        "actions": [{"name": "Bite", "desc": "+5 to hit, (2d6+3) piercing damage."}],
                    }
                ]
            }
        )
        importer = Open5eMonsterImporter(repository=self.repo, client=client)

        result = importer.import_monsters(pages=1, start_page=1, location_id=None)

        self.assertEqual(1, result.created)
        self.assertEqual(0, result.updated)
        self.assertEqual(1, result.attached)

        with self.SessionLocal() as session:
            row = session.execute(
                text(
                    """
                    SELECT entity_id, name, level, armour_class, attack_bonus, damage_dice, hp_max, kind
                    FROM entity
                    WHERE name = 'Dire Wolf'
                    """
                )
            ).first()
            self.assertIsNotNone(row)
            self.assertEqual(2, row.level)
            self.assertEqual(14, row.armour_class)
            self.assertEqual(5, row.attack_bonus)
            self.assertEqual("2d6+3", row.damage_dice)
            self.assertEqual(37, row.hp_max)
            self.assertEqual("beast", row.kind)

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

            self.assertEqual(1, location_id)

    def test_importer_is_idempotent_and_updates_existing_rows(self) -> None:
        client = FakeOpen5eClient(
            pages={
                1: [
                    {
                        "name": "Bandit Captain",
                        "challenge_rating": "3",
                        "armor_class": 15,
                        "hit_points": 65,
                        "type": "humanoid",
                        "actions": [{"name": "Scimitar", "desc": "+5 to hit, (1d6+3) slashing damage."}],
                    }
                ]
            }
        )
        importer = Open5eMonsterImporter(repository=self.repo, client=client)

        first_result = importer.import_monsters(pages=1, start_page=1, location_id=1)
        self.assertEqual(1, first_result.created)

        client.pages = {
            1: [
                {
                    "name": "Bandit Captain",
                    "challenge_rating": "4",
                    "armor_class": 16,
                    "hit_points": 85,
                    "type": "humanoid",
                    "actions": [{"name": "Scimitar", "desc": "+6 to hit, (1d8+4) slashing damage."}],
                }
            ]
        }

        second_result = importer.import_monsters(pages=1, start_page=1, location_id=2)

        self.assertEqual(0, second_result.created)
        self.assertEqual(1, second_result.updated)
        self.assertEqual(1, second_result.attached)

        with self.SessionLocal() as session:
            total_entities = session.execute(text("SELECT COUNT(*) FROM entity")).scalar()
            self.assertEqual(1, total_entities)

            row = session.execute(
                text(
                    """
                    SELECT entity_id, level, armour_class, attack_bonus, damage_dice, hp_max, kind
                    FROM entity
                    WHERE name = 'Bandit Captain'
                    """
                )
            ).first()

            self.assertEqual(4, row.level)
            self.assertEqual(16, row.armour_class)
            self.assertEqual(6, row.attack_bonus)
            self.assertEqual("1d8+4", row.damage_dice)
            self.assertEqual(85, row.hp_max)
            self.assertEqual("humanoid", row.kind)

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


if __name__ == "__main__":
    unittest.main()
