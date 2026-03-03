import sys
from pathlib import Path
import unittest
from unittest import mock

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rpg.infrastructure.db.mysql import repos as mysql_repos
from rpg.infrastructure.db.mysql.repos import (
    MysqlCharacterRepository,
    MysqlClassRepository,
    MysqlEntityRepository,
    MysqlQuestTemplateRepository,
)
from rpg.domain.services.class_progression_catalog import progression_rows_for_class
from rpg.infrastructure.inmemory.inmemory_quest_template_repo import InMemoryQuestTemplateRepository


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


class MysqlClassRepositoryProgressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:", future=True)
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE class (
                        class_id INTEGER PRIMARY KEY,
                        name TEXT NOT NULL,
                        open5e_slug TEXT,
                        hit_die TEXT,
                        primary_ability TEXT,
                        source TEXT
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE class_progression_row (
                        class_progression_row_id INTEGER PRIMARY KEY,
                        class_id INTEGER NOT NULL,
                        level INTEGER NOT NULL,
                        gains TEXT NOT NULL
                    )
                    """
                )
            )

        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.session_patcher = mock.patch.object(mysql_repos, "SessionLocal", self.SessionLocal)
        self.session_patcher.start()
        self.repo = MysqlClassRepository()

    def tearDown(self) -> None:
        self.session_patcher.stop()
        self.engine.dispose()

    def test_list_progression_rows_reads_sql_when_table_present(self) -> None:
        with self.SessionLocal.begin() as session:
            session.execute(
                text(
                    """
                    INSERT INTO class (class_id, name, open5e_slug, hit_die, primary_ability, source)
                    VALUES (1, 'Fighter', 'fighter', 'd10', 'strength', 'seed')
                    """
                )
            )
            session.execute(
                text(
                    """
                    INSERT INTO class_progression_row (class_progression_row_id, class_id, level, gains)
                    VALUES
                        (1, 1, 1, 'Fighting Style, Second Wind'),
                        (2, 1, 2, 'Action Surge')
                    """
                )
            )

        rows = self.repo.list_progression_rows("fighter")

        self.assertEqual(2, len(rows))
        self.assertEqual(1, rows[0].level)
        self.assertIn("Fighting Style", rows[0].gains)
        self.assertEqual(2, rows[1].level)
        self.assertIn("Action Surge", rows[1].gains)

    def test_list_progression_rows_falls_back_when_sql_table_missing(self) -> None:
        with self.engine.begin() as conn:
            conn.execute(text("DROP TABLE class_progression_row"))

        rows = self.repo.list_progression_rows("wizard")

        self.assertEqual(progression_rows_for_class("wizard"), rows)


class MysqlCharacterRepositoryGuildHistoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:", future=True)
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE "character" (
                        character_id INTEGER PRIMARY KEY,
                        name TEXT,
                        flags_json TEXT
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE character_guild_history (
                        character_guild_history_id INTEGER PRIMARY KEY,
                        character_id INTEGER NOT NULL,
                        event_kind TEXT NOT NULL,
                        old_value TEXT NOT NULL,
                        new_value TEXT NOT NULL,
                        changed_turn INTEGER NOT NULL,
                        reason TEXT NOT NULL,
                        metadata_json TEXT NOT NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO "character" (character_id, name, flags_json)
                    VALUES (1, 'Mira', '{}')
                    """
                )
            )

        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.session_patcher = mock.patch.object(mysql_repos, "SessionLocal", self.SessionLocal)
        self.session_patcher.start()
        self.repo = MysqlCharacterRepository()

    def tearDown(self) -> None:
        self.session_patcher.stop()
        self.engine.dispose()

    def test_record_and_list_guild_history_via_table(self) -> None:
        self.repo.record_guild_history(
            character_id=1,
            event_kind="rank_change",
            old_value="bronze",
            new_value="silver",
            changed_turn=14,
            reason="promotion",
            metadata_json='{"eligible": true}',
        )

        rows = self.repo.list_guild_history(1)

        self.assertEqual(1, len(rows))
        self.assertEqual("rank_change", rows[0]["event_kind"])
        self.assertEqual("bronze", rows[0]["old_value"])
        self.assertEqual("silver", rows[0]["new_value"])

    def test_record_guild_history_falls_back_to_flags_when_table_missing(self) -> None:
        with self.engine.begin() as conn:
            conn.execute(text("DROP TABLE character_guild_history"))

        self.repo.record_guild_history(
            character_id=1,
            event_kind="conduct_change",
            old_value="50",
            new_value="42",
            changed_turn=15,
            reason="contract_failure",
            metadata_json='{"contract_id": "guild_livelihood_patrol"}',
        )

        rows = self.repo.list_guild_history(1)
        self.assertEqual(1, len(rows))
        self.assertEqual("conduct_change", rows[0]["event_kind"])


class MysqlQuestTemplateRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:", future=True)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.session_patcher = mock.patch.object(mysql_repos, "SessionLocal", self.SessionLocal)
        self.session_patcher.start()

    def tearDown(self) -> None:
        self.session_patcher.stop()
        self.engine.dispose()

    def test_sql_and_inmemory_filtering_parity(self) -> None:
        payload_rows = [
            {
                "template_version": "quest_template_v1",
                "slug": "river_escort",
                "title": "River Escort",
                "objective": {"kind": "travel", "target_key": "route_leg", "target_count": 2},
                "tags": ["escort", "river"],
                "cataclysm_pushback": False,
            },
            {
                "template_version": "quest_template_v1",
                "slug": "cataclysm_breach",
                "title": "Cataclysm Breach",
                "objective": {"kind": "hunt", "target_key": "any_hostile", "target_count": 3},
                "tags": ["hunt", "cataclysm"],
                "cataclysm_pushback": True,
            },
        ]

        mysql_repo = MysqlQuestTemplateRepository(payload_rows=payload_rows)
        inmemory_repo = InMemoryQuestTemplateRepository(payload_rows=payload_rows)

        mysql_standard = mysql_repo.list_templates(include_cataclysm=False, required_tags=["escort"])
        inmemory_standard = inmemory_repo.list_templates(include_cataclysm=False, required_tags=["escort"])
        mysql_cataclysm = mysql_repo.list_templates(include_cataclysm=True, forbidden_tags=["escort"])
        inmemory_cataclysm = inmemory_repo.list_templates(include_cataclysm=True, forbidden_tags=["escort"])

        self.assertEqual([row.slug for row in inmemory_standard], [row.slug for row in mysql_standard])
        self.assertEqual([row.slug for row in inmemory_cataclysm], [row.slug for row in mysql_cataclysm])

    def test_read_path_seeds_defaults_when_table_missing(self) -> None:
        repo = MysqlQuestTemplateRepository()

        first_hunt = repo.get_template("first_hunt")
        standard = repo.list_templates(include_cataclysm=False)

        self.assertIsNotNone(first_hunt)
        self.assertTrue(any(row.slug == "first_hunt" for row in standard))


if __name__ == "__main__":
    unittest.main()
