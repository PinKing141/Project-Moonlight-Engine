from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from sqlalchemy import text

from rpg.domain.models.character import Character
from rpg.domain.models.world import World
from .connection import SessionLocal


def _table_columns(session, table_name: str) -> set[str]:
    dialect = session.bind.dialect.name if session.bind is not None else "mysql"
    if dialect == "sqlite":
        rows = session.execute(text(f"PRAGMA table_info({table_name})")).all()
        return {str(row.name).lower() for row in rows}

    rows = session.execute(
        text(
            """
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = :table_name
            """
        ),
        {"table_name": str(table_name)},
    ).all()
    return {str(row.COLUMN_NAME).lower() for row in rows}


def save_character_and_world_atomic(
    character: Character,
    world: World,
    operations: Sequence[Callable[[object], None]] | None = None,
) -> None:
    """Persist character and world updates in one DB transaction."""
    with SessionLocal.begin() as session:
        _upsert_character_row(session, character)
        _upsert_character_attributes(session, character)
        _upsert_character_location(session, character)
        _upsert_world_row(session, world)
        for operation in operations or ():
            operation(session)


def _upsert_character_row(session, character: Character) -> None:
    dialect = session.bind.dialect.name if session.bind is not None else "mysql"
    columns = _table_columns(session, "character")
    has_inventory_json = "inventory_json" in columns
    has_flags_json = "flags_json" in columns

    character_columns = "character_id, name, alive, level, xp, money, character_type_id, hp_current, hp_max, armour_class, armor, attack_bonus, damage_die, speed"
    character_values = ":cid, :name, :alive, :level, :xp, :money, :ctype, :hp_current, :hp_max, :armour_class, :armor, :attack_bonus, :damage_die, :speed"
    update_mysql = """
                name = VALUES(name),
                alive = VALUES(alive),
                level = VALUES(level),
                xp = VALUES(xp),
                money = VALUES(money),
                character_type_id = VALUES(character_type_id),
                hp_current = VALUES(hp_current),
                hp_max = VALUES(hp_max),
                armour_class = VALUES(armour_class),
                armor = VALUES(armor),
                attack_bonus = VALUES(attack_bonus),
                damage_die = VALUES(damage_die),
                speed = VALUES(speed)
    """
    update_sqlite = """
                name = excluded.name,
                alive = excluded.alive,
                level = excluded.level,
                xp = excluded.xp,
                money = excluded.money,
                character_type_id = excluded.character_type_id,
                hp_current = excluded.hp_current,
                hp_max = excluded.hp_max,
                armour_class = excluded.armour_class,
                armor = excluded.armor,
                attack_bonus = excluded.attack_bonus,
                damage_die = excluded.damage_die,
                speed = excluded.speed
    """

    if has_inventory_json:
        character_columns += ", inventory_json"
        character_values += ", :inventory_json"
        update_mysql += ",\n                inventory_json = VALUES(inventory_json)"
        update_sqlite += ",\n                inventory_json = excluded.inventory_json"
    if has_flags_json:
        character_columns += ", flags_json"
        character_values += ", :flags_json"
        update_mysql += ",\n                flags_json = VALUES(flags_json)"
        update_sqlite += ",\n                flags_json = excluded.flags_json"

    if dialect == "mysql":
        statement = text(
            f"""
            INSERT INTO `character` ({character_columns})
            VALUES ({character_values})
            ON DUPLICATE KEY UPDATE
{update_mysql}
            """
        )
    else:
        statement = text(
            f"""
            INSERT INTO "character" ({character_columns})
            VALUES ({character_values})
            ON CONFLICT(character_id) DO UPDATE SET
{update_sqlite}
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
            "armour_class": character.armour_class,
            "armor": character.armor,
            "attack_bonus": character.attack_bonus,
            "damage_die": character.damage_die,
            "speed": character.speed,
            "inventory_json": json.dumps(list(getattr(character, "inventory", []) or [])),
            "flags_json": json.dumps(dict(getattr(character, "flags", {}) or {})),
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


def _upsert_character_attributes(session, character: Character) -> None:
    attrs = dict(getattr(character, "attributes", {}) or {})
    if not attrs:
        return

    names = [str(name) for name in attrs.keys()]
    bind_names = [f"name_{idx}" for idx in range(len(names))]
    params = {bind_name: names[idx] for idx, bind_name in enumerate(bind_names)}
    placeholders = ", ".join(f":{bind_name}" for bind_name in bind_names)

    rows = session.execute(
        text(
            f"""
            SELECT attribute_id, name
            FROM attribute
            WHERE name IN ({placeholders})
            """
        ),
        params,
    ).all()

    id_by_name = {str(row.name): int(row.attribute_id) for row in rows}
    if not id_by_name:
        return

    dialect = session.bind.dialect.name if session.bind is not None else "mysql"
    if dialect == "mysql":
        statement = text(
            """
            INSERT INTO character_attribute (character_id, attribute_id, value)
            VALUES (:cid, :aid, :val)
            ON DUPLICATE KEY UPDATE value = VALUES(value)
            """
        )
    else:
        statement = text(
            """
            INSERT INTO character_attribute (character_id, attribute_id, value)
            VALUES (:cid, :aid, :val)
            ON CONFLICT(character_id, attribute_id) DO UPDATE SET value = excluded.value
            """
        )

    for name, value in attrs.items():
        attr_id = id_by_name.get(str(name))
        if attr_id is None:
            continue
        session.execute(
            statement,
            {
                "cid": int(character.id or 0),
                "aid": int(attr_id),
                "val": int(value),
            },
        )


def _upsert_world_row(session, world: World) -> None:
    flags_payload = world.flags if isinstance(world.flags, str) else "{}" if world.flags is None else json.dumps(world.flags)
    dialect = session.bind.dialect.name if session.bind is not None else "mysql"
    if dialect == "mysql":
        statement = text(
            """
            INSERT INTO world (world_id, name, current_turn, threat_level, flags, rng_seed)
            VALUES (:wid, :name, :turn, :threat, :flags, :rng_seed)
            ON DUPLICATE KEY UPDATE
                name = VALUES(name),
                current_turn = VALUES(current_turn),
                threat_level = VALUES(threat_level),
                flags = VALUES(flags),
                rng_seed = VALUES(rng_seed)
            """
        )
    else:
        statement = text(
            """
            INSERT INTO world (world_id, name, current_turn, threat_level, flags, rng_seed)
            VALUES (:wid, :name, :turn, :threat, :flags, :rng_seed)
            ON CONFLICT(world_id) DO UPDATE SET
                name = excluded.name,
                current_turn = excluded.current_turn,
                threat_level = excluded.threat_level,
                flags = excluded.flags,
                rng_seed = excluded.rng_seed
            """
        )

    session.execute(
        statement,
        {
            "wid": int(getattr(world, "id", 1) or 1),
            "name": str(getattr(world, "name", "Default World") or "Default World"),
            "turn": int(getattr(world, "current_turn", 0) or 0),
            "threat": int(getattr(world, "threat_level", 0) or 0),
            "flags": flags_payload,
            "rng_seed": int(getattr(world, "rng_seed", 1) or 1),
        },
    )
