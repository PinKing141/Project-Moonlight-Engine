import sys
from pathlib import Path
import unittest
from unittest import mock

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.domain.models.character import Character
from rpg.infrastructure.db.mysql import repos as mysql_repos
from rpg.infrastructure.db.mysql.repos import MysqlCharacterRepository


def _bootstrap_character_schema(engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE character_type (
                    character_type_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE
                )
                """
            )
        )
        conn.execute(text("INSERT INTO character_type (character_type_id, name) VALUES (1, 'player')"))

        conn.execute(
            text(
                """
                CREATE TABLE class (
                    class_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    open5e_slug TEXT,
                    hit_die TEXT,
                    primary_ability TEXT,
                    source TEXT
                )
                """
            )
        )
        conn.execute(text("INSERT INTO class (class_id, name, open5e_slug, source) VALUES (1, 'Fighter', 'fighter', 'seed')"))

        conn.execute(
            text(
                """
                CREATE TABLE character (
                    character_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    character_type_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    alive INTEGER NOT NULL,
                    level INTEGER NOT NULL,
                    xp INTEGER NOT NULL,
                    money INTEGER NOT NULL,
                    inventory_json TEXT,
                    flags_json TEXT,
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
                CREATE TABLE location (
                    location_id INTEGER PRIMARY KEY,
                    x INTEGER,
                    y INTEGER,
                    place_id INTEGER
                )
                """
            )
        )
        conn.execute(text("INSERT INTO location (location_id, x, y, place_id) VALUES (1, 0, 0, 1)"))

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
                CREATE TABLE character_class (
                    character_class_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    character_id INTEGER NOT NULL,
                    class_id INTEGER NOT NULL
                )
                """
            )
        )

        conn.execute(
            text(
                """
                CREATE TABLE attribute (
                    attribute_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    "desc" TEXT
                )
                """
            )
        )
        for index, name in enumerate(["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"], start=1):
            conn.execute(text("INSERT INTO attribute (attribute_id, name, \"desc\") VALUES (:id, :name, '')"), {"id": index, "name": name})

        conn.execute(
            text(
                """
                CREATE TABLE character_attribute (
                    character_attribute_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    character_id INTEGER NOT NULL,
                    attribute_id INTEGER NOT NULL,
                    value INTEGER NOT NULL,
                    UNIQUE(character_id, attribute_id)
                )
                """
            )
        )


class MysqlCharacterRepositoryStatsIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:", future=True)
        _bootstrap_character_schema(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.session_patcher = mock.patch.object(mysql_repos, "SessionLocal", self.SessionLocal)
        self.session_patcher.start()
        self.repo = MysqlCharacterRepository()

    def tearDown(self) -> None:
        self.session_patcher.stop()
        self.engine.dispose()

    def test_create_and_get_round_trip_character_combat_stats(self) -> None:
        created = self.repo.create(
            Character(
                id=None,
                name="Arin",
                class_name="fighter",
                level=2,
                hp_current=18,
                hp_max=20,
                armour_class=16,
                armor=2,
                attack_bonus=5,
                damage_die="d10",
                speed=25,
                inventory=["Healing Potion", "Whetstone"],
                flags={"equipment": {"weapon": "Longsword"}},
                attributes={},
            ),
            location_id=1,
        )
        self.assertIsNotNone(created.id)
        created_id = created.id
        assert created_id is not None
        loaded = self.repo.get(int(created_id))

        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(16, loaded.armour_class)
        self.assertEqual(2, loaded.armor)
        self.assertEqual(5, loaded.attack_bonus)
        self.assertEqual("d10", loaded.damage_die)
        self.assertEqual(25, loaded.speed)
        self.assertEqual(["Healing Potion", "Whetstone"], loaded.inventory)
        self.assertEqual({"equipment": {"weapon": "Longsword"}}, loaded.flags)

    def test_save_updates_character_combat_stats(self) -> None:
        created = self.repo.create(
            Character(id=None, name="Bryn", class_name="fighter", hp_current=10, hp_max=10, attributes={}),
            location_id=1,
        )
        self.assertIsNotNone(created.id)
        created.armour_class = 18
        created.armor = 3
        created.attack_bonus = 6
        created.damage_die = "d12"
        created.speed = 35
        created.inventory = ["Focus Potion"]
        created.flags = {"travel_prep": {"rations": 2}}

        self.repo.save(created)
        created_id = created.id
        assert created_id is not None
        loaded = self.repo.get(int(created_id))
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(18, loaded.armour_class)
        self.assertEqual(3, loaded.armor)
        self.assertEqual(6, loaded.attack_bonus)
        self.assertEqual("d12", loaded.damage_die)
        self.assertEqual(35, loaded.speed)
        self.assertEqual(["Focus Potion"], loaded.inventory)
        self.assertEqual({"travel_prep": {"rations": 2}}, loaded.flags)


if __name__ == "__main__":
    unittest.main()
