import json
import importlib
import importlib.util
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

hypothesis_module = importlib.util.find_spec("hypothesis")
if hypothesis_module is not None:
    hypothesis = importlib.import_module("hypothesis")
    given = getattr(hypothesis, "given", None)
    settings = getattr(hypothesis, "settings", None)
    st = importlib.import_module("hypothesis.strategies")
    HYPOTHESIS_AVAILABLE = given is not None and settings is not None and st is not None
else:
    HYPOTHESIS_AVAILABLE = False
    given = None
    settings = None
    st = None


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


if HYPOTHESIS_AVAILABLE and settings is not None and given is not None and st is not None:
    class SqliteRoundTripParityPropertyTests(unittest.TestCase):
        def setUp(self) -> None:
            self.engine = create_engine("sqlite:///:memory:", future=True)
            _bootstrap_character_schema(self.engine)
            session_local = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
            self.session_patcher = mock.patch.object(mysql_repos, "SessionLocal", session_local)
            self.session_patcher.start()
            self.repo = MysqlCharacterRepository()

        def tearDown(self) -> None:
            self.session_patcher.stop()
            self.engine.dispose()

        @settings(max_examples=40, deadline=None)
        @given(
            name=st.text(min_size=1, max_size=24, alphabet=st.characters(min_codepoint=97, max_codepoint=122)),
            level=st.integers(min_value=1, max_value=20),
            xp=st.integers(min_value=0, max_value=100000),
            money=st.integers(min_value=0, max_value=100000),
            hp_max=st.integers(min_value=1, max_value=250),
            armour_class=st.integers(min_value=8, max_value=25),
            armor=st.integers(min_value=0, max_value=10),
            attack_bonus=st.integers(min_value=0, max_value=12),
            speed=st.integers(min_value=20, max_value=60),
            damage_die=st.sampled_from(["d4", "d6", "d8", "d10", "d12"]),
            inventory=st.lists(st.text(min_size=1, max_size=12, alphabet=st.characters(min_codepoint=97, max_codepoint=122)), min_size=0, max_size=6),
            alignment=st.sampled_from(
                [
                    "lawful_good",
                    "neutral_good",
                    "chaotic_good",
                    "lawful_neutral",
                    "true_neutral",
                    "chaotic_neutral",
                    "lawful_evil",
                    "neutral_evil",
                    "chaotic_evil",
                ]
            ),
            difficulty=st.sampled_from(["easy", "normal", "hard"]),
        )
        def test_character_round_trip_sqlite_backend(
            self,
            *,
            name,
            level,
            xp,
            money,
            hp_max,
            armour_class,
            armor,
            attack_bonus,
            speed,
            damage_die,
            inventory,
            alignment,
            difficulty,
        ) -> None:
            hp_current = min(hp_max, max(1, hp_max - 1))
            flags = {
                "alignment": alignment,
                "difficulty": difficulty,
                "travel_prep": {"rations": len(inventory)},
                "meta": {"seed": level * 13 + attack_bonus},
            }

            created = self.repo.create(
                Character(
                    id=None,
                    name=name,
                    class_name="fighter",
                    level=level,
                    xp=xp,
                    money=money,
                    hp_current=hp_current,
                    hp_max=hp_max,
                    armour_class=armour_class,
                    armor=armor,
                    attack_bonus=attack_bonus,
                    damage_die=damage_die,
                    speed=speed,
                    inventory=inventory,
                    flags=flags,
                    attributes={},
                ),
                location_id=1,
            )

            loaded = self.repo.get(int(created.id or 0))
            self.assertIsNotNone(loaded)
            assert loaded is not None

            self.assertEqual(name, loaded.name)
            self.assertEqual(level, loaded.level)
            self.assertEqual(xp, loaded.xp)
            self.assertEqual(money, loaded.money)
            self.assertEqual(hp_current, loaded.hp_current)
            self.assertEqual(hp_max, loaded.hp_max)
            self.assertEqual(armour_class, loaded.armour_class)
            self.assertEqual(armor, loaded.armor)
            self.assertEqual(attack_bonus, loaded.attack_bonus)
            self.assertEqual(damage_die, loaded.damage_die)
            self.assertEqual(speed, loaded.speed)
            self.assertEqual(inventory, loaded.inventory)

            expected_flags = json.loads(json.dumps(flags))
            self.assertEqual(expected_flags.get("alignment"), loaded.flags.get("alignment"))
            self.assertEqual(expected_flags.get("difficulty"), loaded.flags.get("difficulty"))
            self.assertEqual(expected_flags.get("travel_prep"), loaded.flags.get("travel_prep"))
else:
    @unittest.skip("Hypothesis is required for property-based parity audit")
    class SqliteRoundTripParityPropertyTestsMissingHypothesis(unittest.TestCase):
        def test_hypothesis_dependency_missing(self) -> None:
            self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
