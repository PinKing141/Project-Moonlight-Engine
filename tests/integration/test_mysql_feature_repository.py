import sys
from pathlib import Path
import unittest
from unittest import mock

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.infrastructure.db.mysql import repos as mysql_repos
from rpg.infrastructure.db.mysql.repos import MysqlFeatureRepository


def _bootstrap_feature_schema(engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE character (character_id INTEGER PRIMARY KEY, name TEXT NOT NULL)"))
        conn.execute(
            text(
                """
                CREATE TABLE class (
                    class_id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    open5e_slug TEXT
                )
                """
            )
        )
        conn.execute(text("CREATE TABLE character_class (character_class_id INTEGER PRIMARY KEY, character_id INTEGER NOT NULL, class_id INTEGER NOT NULL)"))
        conn.execute(text("CREATE TABLE ability (ability_id INTEGER PRIMARY KEY, name TEXT NOT NULL, slug TEXT, trigger_key TEXT, effect_kind TEXT, effect_value INTEGER, source TEXT)"))
        conn.execute(text("CREATE TABLE class_ability (class_ability_id INTEGER PRIMARY KEY, class_id INTEGER NOT NULL, ability_id INTEGER NOT NULL)"))
        conn.execute(
            text(
                """
                CREATE TABLE character_feature (
                    character_feature_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    character_id INTEGER NOT NULL,
                    ability_id INTEGER NOT NULL,
                    UNIQUE(character_id, ability_id)
                )
                """
            )
        )

        conn.execute(text("INSERT INTO character (character_id, name) VALUES (1, 'Vale')"))
        conn.execute(text("INSERT INTO class (class_id, name, open5e_slug) VALUES (5, 'Fighter', 'fighter'), (9, 'Rogue', 'rogue')"))
        conn.execute(text("INSERT INTO character_class (character_class_id, character_id, class_id) VALUES (1, 1, 9), (2, 1, 5)"))
        conn.execute(
            text(
                """
                INSERT INTO ability (ability_id, name, slug, trigger_key, effect_kind, effect_value, source)
                VALUES
                    (1, 'Sneak Attack', 'feature.sneak_attack', 'on_attack_hit', 'bonus_damage', 2, 'seed'),
                    (2, 'Darkvision', 'feature.darkvision', 'on_initiative', 'initiative_bonus', 2, 'seed'),
                    (3, 'Martial Precision', 'feature.martial_precision', 'on_attack_roll', 'attack_bonus', 2, 'seed')
                """
            )
        )
        conn.execute(text("INSERT INTO class_ability (class_ability_id, class_id, ability_id) VALUES (1, 9, 1), (2, 5, 3)"))


class MysqlFeatureRepositoryIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:", future=True)
        _bootstrap_feature_schema(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.session_patcher = mock.patch.object(mysql_repos, "SessionLocal", self.SessionLocal)
        self.session_patcher.start()
        self.repo = MysqlFeatureRepository()

    def tearDown(self) -> None:
        self.session_patcher.stop()
        self.engine.dispose()

    def test_list_for_character_includes_class_abilities(self) -> None:
        features = self.repo.list_for_character(1)
        slugs = {feature.slug for feature in features}
        self.assertIn("feature.sneak_attack", slugs)
        self.assertIn("feature.martial_precision", slugs)

    def test_grant_feature_by_slug_assigns_character_feature(self) -> None:
        granted = self.repo.grant_feature_by_slug(1, "feature.darkvision")
        self.assertTrue(granted)

        features = self.repo.list_for_character(1)
        slugs = {feature.slug for feature in features}
        self.assertIn("feature.darkvision", slugs)


if __name__ == "__main__":
    unittest.main()
