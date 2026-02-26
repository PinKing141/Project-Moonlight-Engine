import json
import sys
from pathlib import Path
import unittest
from unittest import mock

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.game_service import GameService
from rpg.infrastructure.db.mysql import atomic_persistence
from rpg.infrastructure.db.mysql import repos as mysql_repos
from rpg.infrastructure.db.mysql.atomic_persistence import save_character_and_world_atomic
from rpg.infrastructure.db.mysql.repos import (
    MysqlCharacterRepository,
    MysqlFactionRepository,
    MysqlNarrativeStateRepository,
    MysqlWorldRepository,
)


class _FailingNarrativeStateRepository(MysqlNarrativeStateRepository):
    def build_save_active_with_history_operation(self, **_kwargs):
        def _operation(_session) -> None:
            raise RuntimeError("forced narrative operation failure")

        return _operation


def _bootstrap_schema(engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE world (
                    world_id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    current_turn INTEGER NOT NULL,
                    threat_level INTEGER NOT NULL,
                    flags TEXT,
                    rng_seed INTEGER NOT NULL DEFAULT 1
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO world (world_id, name, current_turn, threat_level, flags, rng_seed)
                VALUES (1, 'Default World', 5, 2, :flags, 99)
                """
            ),
            {
                "flags": json.dumps(
                    {
                        "quests": {
                            "first_hunt": {
                                "status": "ready_to_turn_in",
                                "owner_character_id": 1,
                                "reward_xp": 25,
                                "reward_money": 11,
                                "progress": 1,
                                "target": 1,
                                "accepted_turn": 3,
                                "seed_key": "quest:first_hunt:12345",
                            }
                        }
                    }
                )
            },
        )

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
                INSERT INTO "character" (
                    character_id, name, alive, level, xp, money, character_type_id,
                    hp_current, hp_max, armour_class, armor, attack_bonus, damage_die, speed
                )
                VALUES (1, 'AtomicRunner', 1, 2, 10, 5, 1, 12, 12, 13, 1, 3, 'd8', 30)
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
        conn.execute(text("INSERT INTO character_location (character_id, location_id) VALUES (1, 1)"))

        conn.execute(
            text(
                """
                CREATE TABLE class (
                    class_id INTEGER PRIMARY KEY,
                    name TEXT,
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
                CREATE TABLE character_class (
                    character_class_id INTEGER PRIMARY KEY,
                    character_id INTEGER,
                    class_id INTEGER
                )
                """
            )
        )

        conn.execute(
            text(
                """
                CREATE TABLE attribute (
                    attribute_id INTEGER PRIMARY KEY,
                    name TEXT,
                    "desc" TEXT
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE character_attribute (
                    character_attribute_id INTEGER PRIMARY KEY,
                    character_id INTEGER,
                    attribute_id INTEGER,
                    value INTEGER,
                    UNIQUE(character_id, attribute_id)
                )
                """
            )
        )

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
                INSERT INTO faction (name, slug, alignment, influence)
                VALUES ('Wardens', 'wardens', 'neutral', 3)
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
                CREATE TABLE quest_history (
                    quest_history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    character_id INTEGER NOT NULL,
                    quest_definition_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    action_turn INTEGER NOT NULL,
                    payload_json TEXT
                )
                """
            )
        )


class GameServiceTurnInAtomicRollbackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:", future=True)
        _bootstrap_schema(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)

        self.repos_session_patcher = mock.patch.object(mysql_repos, "SessionLocal", self.SessionLocal)
        self.atomic_session_patcher = mock.patch.object(atomic_persistence, "SessionLocal", self.SessionLocal)
        self.repos_session_patcher.start()
        self.atomic_session_patcher.start()

        self.service = GameService(
            character_repo=MysqlCharacterRepository(),
            world_repo=MysqlWorldRepository(),
            faction_repo=MysqlFactionRepository(),
            quest_state_repo=_FailingNarrativeStateRepository(),
            atomic_state_persistor=save_character_and_world_atomic,
        )

    def tearDown(self) -> None:
        self.repos_session_patcher.stop()
        self.atomic_session_patcher.stop()
        self.engine.dispose()

    def test_turn_in_rolls_back_character_world_and_narrative_writes_on_failing_operation(self) -> None:
        with self.assertRaises(RuntimeError):
            self.service.turn_in_quest_intent(character_id=1, quest_id="first_hunt")

        character_repo = MysqlCharacterRepository()
        world_repo = MysqlWorldRepository()
        character = character_repo.get(1)
        world = world_repo.load_default()

        self.assertIsNotNone(character)
        assert character is not None
        self.assertEqual(10, int(character.xp))
        self.assertEqual(5, int(character.money))

        self.assertIsNotNone(world)
        assert world is not None
        quest = (world.flags or {}).get("quests", {}).get("first_hunt", {})
        self.assertEqual("ready_to_turn_in", quest.get("status"))
        self.assertNotIn("quest_world_flags", world.flags or {})

        with self.SessionLocal() as session:
            active_count = session.execute(text("SELECT COUNT(*) FROM character_active_quest")).scalar_one()
            history_count = session.execute(text("SELECT COUNT(*) FROM quest_history")).scalar_one()
            rep_count = session.execute(text("SELECT COUNT(*) FROM character_reputation")).scalar_one()
            rep_history_count = session.execute(text("SELECT COUNT(*) FROM reputation_history")).scalar_one()

            self.assertEqual(0, int(active_count))
            self.assertEqual(0, int(history_count))
            self.assertEqual(0, int(rep_count))
            self.assertEqual(0, int(rep_history_count))


if __name__ == "__main__":
    unittest.main()
