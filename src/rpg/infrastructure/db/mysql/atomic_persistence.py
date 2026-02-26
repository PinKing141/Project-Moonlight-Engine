from __future__ import annotations

import json
from sqlalchemy import text

from rpg.domain.models.character import Character
from rpg.domain.models.world import World
from .connection import SessionLocal


def save_character_and_world_atomic(character: Character, world: World) -> None:
    """Persist character and world updates in one DB transaction."""
    with SessionLocal.begin() as session:
        _upsert_character_row(session, character)
        _upsert_character_location(session, character)
        _upsert_world_row(session, world)


def _upsert_character_row(session, character: Character) -> None:
    dialect = session.bind.dialect.name if session.bind is not None else "mysql"
    if dialect == "mysql":
        statement = text(
            """
            INSERT INTO `character` (character_id, name, alive, level, xp, money, character_type_id, hp_current, hp_max)
            VALUES (:cid, :name, :alive, :level, :xp, :money, :ctype, :hp_current, :hp_max)
            ON DUPLICATE KEY UPDATE
                name = VALUES(name),
                alive = VALUES(alive),
                level = VALUES(level),
                xp = VALUES(xp),
                money = VALUES(money),
                character_type_id = VALUES(character_type_id),
                hp_current = VALUES(hp_current),
                hp_max = VALUES(hp_max)
            """
        )
    else:
        statement = text(
            """
            INSERT INTO "character" (character_id, name, alive, level, xp, money, character_type_id, hp_current, hp_max)
            VALUES (:cid, :name, :alive, :level, :xp, :money, :ctype, :hp_current, :hp_max)
            ON CONFLICT(character_id) DO UPDATE SET
                name = excluded.name,
                alive = excluded.alive,
                level = excluded.level,
                xp = excluded.xp,
                money = excluded.money,
                character_type_id = excluded.character_type_id,
                hp_current = excluded.hp_current,
                hp_max = excluded.hp_max
            """
        )
    session.execute(
        statement,
        {
            "cid": character.id,
            "name": character.name,
            "alive": int(character.alive),
            "level": character.level,
            "xp": character.xp,
            "money": character.money,
            "ctype": character.character_type_id,
            "hp_current": character.hp_current,
            "hp_max": character.hp_max,
        },
    )


def _upsert_character_location(session, character: Character) -> None:
    dialect = session.bind.dialect.name if session.bind is not None else "mysql"
    if dialect == "mysql":
        statement = text(
            """
            INSERT INTO character_location (character_id, location_id)
            VALUES (:cid, :loc)
            ON DUPLICATE KEY UPDATE location_id = VALUES(location_id)
            """
        )
    else:
        statement = text(
            """
            INSERT INTO character_location (character_id, location_id)
            VALUES (:cid, :loc)
            ON CONFLICT(character_id) DO UPDATE SET location_id = excluded.location_id
            """
        )
    session.execute(
        statement,
        {"cid": character.id, "loc": character.location_id},
    )


def _upsert_world_row(session, world: World) -> None:
    flags_payload = world.flags if isinstance(world.flags, str) else "{}" if world.flags is None else json.dumps(world.flags)
    session.execute(
        text(
            """
            UPDATE world
            SET current_turn = :turn,
                threat_level = :threat,
                flags = :flags
            WHERE world_id = :wid
            """
        ),
        {
            "turn": world.current_turn,
            "threat": world.threat_level,
            "flags": flags_payload,
            "wid": world.id,
        },
    )
