import json
from typing import Dict, List, Optional, Sequence

from sqlalchemy import bindparam, text

from rpg.domain.models.character import Character
from rpg.domain.models.character_class import CharacterClass
from rpg.domain.models.entity import Entity
from rpg.domain.models.location import Location
from rpg.domain.models.world import World
from rpg.domain.models.spell import Spell
from rpg.domain.repositories import (
    CharacterRepository,
    ClassRepository,
    EntityRepository,
    LocationRepository,
    WorldRepository,
    SpellRepository,
)
from rpg.infrastructure.db.mysql.open5e_monster_importer import UpsertResult
from .connection import SessionLocal


DEFAULT_CLASS_BASE_ATTRIBUTES: Dict[str, Dict[str, int]] = {
    "barbarian": {"STR": 15, "DEX": 12, "CON": 14, "INT": 8, "WIS": 10, "CHA": 10},
    "bard": {"STR": 10, "DEX": 12, "CON": 12, "INT": 12, "WIS": 10, "CHA": 15},
    "cleric": {"STR": 12, "DEX": 10, "CON": 13, "INT": 10, "WIS": 15, "CHA": 11},
    "druid": {"STR": 10, "DEX": 12, "CON": 13, "INT": 12, "WIS": 15, "CHA": 10},
    "fighter": {"STR": 15, "DEX": 12, "CON": 14, "INT": 10, "WIS": 10, "CHA": 10},
    "monk": {"STR": 12, "DEX": 15, "CON": 12, "INT": 10, "WIS": 14, "CHA": 10},
    "paladin": {"STR": 15, "DEX": 10, "CON": 14, "INT": 10, "WIS": 12, "CHA": 14},
    "ranger": {"STR": 13, "DEX": 15, "CON": 13, "INT": 10, "WIS": 12, "CHA": 10},
    "rogue": {"STR": 10, "DEX": 16, "CON": 12, "INT": 12, "WIS": 10, "CHA": 12},
    "sorcerer": {"STR": 8, "DEX": 12, "CON": 12, "INT": 12, "WIS": 10, "CHA": 16},
    "warlock": {"STR": 10, "DEX": 12, "CON": 12, "INT": 12, "WIS": 12, "CHA": 16},
    "wizard": {"STR": 8, "DEX": 12, "CON": 12, "INT": 16, "WIS": 12, "CHA": 10},
}


def _row_to_spell(row) -> Spell:
    classes = None
    if getattr(row, "classes_json", None):
        if isinstance(row.classes_json, str):
            try:
                classes = json.loads(row.classes_json)
            except Exception:
                classes = None
        elif isinstance(row.classes_json, list):
            classes = row.classes_json

    return Spell(
        slug=row.slug,
        name=row.name,
        level_int=row.level_int,
        school=row.school,
        casting_time=row.casting_time,
        range_text=row.range_text,
        duration=row.duration,
        components=row.components,
        concentration=bool(row.concentration),
        ritual=bool(row.ritual),
        desc_text=row.desc_text,
        higher_level=row.higher_level,
        classes=classes,
    )


def _default_stats_for_level(level: int) -> tuple[int, int, int, int]:
    scaled_level = max(level, 1)
    hp = 6 + scaled_level * 3
    attack_min = 1 + scaled_level // 2
    attack_max = 2 + scaled_level
    armor = max(scaled_level // 3, 0)
    return hp, attack_min, attack_max, armor


def _default_combat_fields(level: int) -> tuple[int, int, str]:
    ac = max(10, 10 + level // 2)
    attack_bonus = 2 + level // 2
    damage_die = "d6" if level < 3 else "d8"
    return ac, attack_bonus, damage_die


class MysqlClassRepository(ClassRepository):
    def list_playable(self) -> List[CharacterClass]:
        with SessionLocal() as session:
            rows = session.execute(
                text(
                    """
                    SELECT class_id, name, open5e_slug, hit_die, primary_ability, source
                    FROM class
                    ORDER BY name
                    """
                )
            ).all()

            classes: List[CharacterClass] = []
            for row in rows:
                slug = row.open5e_slug or row.name.lower()
                classes.append(
                    CharacterClass(
                        id=row.class_id,
                        name=row.name,
                        slug=slug,
                        hit_die=row.hit_die,
                        primary_ability=row.primary_ability,
                        base_attributes=DEFAULT_CLASS_BASE_ATTRIBUTES.get(slug, {}),
                    )
                )
            return classes

    def get_by_slug(self, slug: str) -> Optional[CharacterClass]:
        slug_key = slug.lower().strip()
        with SessionLocal() as session:
            row = session.execute(
                text(
                    """
                    SELECT class_id, name, open5e_slug, hit_die, primary_ability, source
                    FROM class
                    WHERE LOWER(open5e_slug) = :slug OR LOWER(name) = :slug
                    LIMIT 1
                    """
                ),
                {"slug": slug_key},
            ).first()

            if not row:
                return None

            return CharacterClass(
                id=row.class_id,
                name=row.name,
                slug=row.open5e_slug or row.name.lower(),
                hit_die=row.hit_die,
                primary_ability=row.primary_ability,
                base_attributes=DEFAULT_CLASS_BASE_ATTRIBUTES.get(slug_key, {}),
            )


class MysqlCharacterRepository(CharacterRepository):
    def get(self, character_id: int) -> Optional[Character]:
        with SessionLocal() as session:
            row = session.execute(
                text(
                    """
                    SELECT c.character_id, c.name, c.alive, c.level, c.xp, c.money,
                           c.character_type_id, c.hp_current, c.hp_max,
                           cl.location_id, cls.name AS class_name
                    FROM `character` c
                    LEFT JOIN character_location cl ON cl.character_id = c.character_id
                    LEFT JOIN character_class cc ON cc.character_id = c.character_id
                    LEFT JOIN class cls ON cls.class_id = cc.class_id
                    WHERE c.character_id = :cid
                    """
                ),
                {"cid": character_id},
            ).first()

            if not row:
                return None

            attributes = self._load_attributes(session, row.character_id)

            return Character(
                id=row.character_id,
                name=row.name,
                alive=bool(row.alive),
                level=row.level,
                xp=row.xp,
                money=row.money,
                character_type_id=row.character_type_id,
                location_id=row.location_id or 0,
                hp_current=row.hp_current,
                hp_max=row.hp_max,
                class_name=row.class_name,
                attributes=attributes,
            )

    def list_all(self) -> List[Character]:
        with SessionLocal() as session:
            rows = session.execute(
                text(
                    """
                    SELECT c.character_id, c.name, c.alive, c.level, c.xp, c.money,
                           c.character_type_id, c.hp_current, c.hp_max, cl.location_id
                    FROM `character` c
                    LEFT JOIN character_location cl ON cl.character_id = c.character_id
                    ORDER BY c.character_id
                    """
                )
            ).all()

            return [
                Character(
                    id=row.character_id,
                    name=row.name,
                    alive=bool(row.alive),
                    level=row.level,
                    xp=row.xp,
                    money=row.money,
                    character_type_id=row.character_type_id,
                    location_id=row.location_id or 0,
                    hp_current=row.hp_current,
                    hp_max=row.hp_max,
                )
                for row in rows
            ]

    def save(self, character: Character) -> None:
        with SessionLocal() as session:
            session.execute(
                text(
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
                ),
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
            # Upsert location mapping
            session.execute(
                text(
                    """
                    INSERT INTO character_location (character_id, location_id)
                    VALUES (:cid, :loc)
                    ON DUPLICATE KEY UPDATE location_id = VALUES(location_id)
                    """
                ),
                {"cid": character.id, "loc": character.location_id},
            )
            session.commit()

    def find_by_location(self, location_id: int) -> List[Character]:
        with SessionLocal() as session:
            rows = session.execute(
                text(
                    """
                    SELECT c.character_id, c.name, c.alive, c.level, c.xp, c.money,
                           c.character_type_id, c.hp_current, c.hp_max,
                           cl.location_id, cls.name AS class_name
                    FROM `character` c
                    INNER JOIN character_location cl ON cl.character_id = c.character_id
                    LEFT JOIN character_class cc ON cc.character_id = c.character_id
                    LEFT JOIN class cls ON cls.class_id = cc.class_id
                    WHERE cl.location_id = :loc
                    """
                ),
                {"loc": location_id},
            ).all()

            characters: List[Character] = []
            for row in rows:
                attributes = self._load_attributes(session, row.character_id)
                characters.append(
                    Character(
                        id=row.character_id,
                        name=row.name,
                        alive=bool(row.alive),
                        level=row.level,
                        xp=row.xp,
                        money=row.money,
                        character_type_id=row.character_type_id,
                        location_id=row.location_id,
                        hp_current=row.hp_current,
                        hp_max=row.hp_max,
                        class_name=row.class_name,
                        attributes=attributes,
                    )
                )
            return characters

    def create(self, character: Character, location_id: int) -> Character:
        with SessionLocal() as session:
            ctype_id = self._resolve_character_type_id(session)
            result = session.execute(
                text(
                    """
                    INSERT INTO `character` (character_type_id, name, alive, level, xp, money, hp_current, hp_max)
                    VALUES (:ctype, :name, 1, :level, :xp, :money, :hp_current, :hp_max)
                    """
                ),
                {
                    "ctype": ctype_id,
                    "name": character.name,
                    "level": character.level,
                    "xp": character.xp,
                    "money": character.money,
                    "hp_current": character.hp_current,
                    "hp_max": character.hp_max,
                },
            )
            character_id = result.lastrowid

            class_id = self._resolve_class_id(session, character.class_name or "fighter")
            session.execute(
                text(
                    """
                    INSERT INTO character_class (character_id, class_id)
                    VALUES (:cid, :class_id)
                    """
                ),
                {"cid": character_id, "class_id": class_id},
            )

            for attr_name, value in (character.attributes or {}).items():
                attr_id = self._resolve_attribute_id(session, attr_name)
                if attr_id is None:
                    continue
                session.execute(
                    text(
                        """
                        INSERT INTO character_attribute (character_id, attribute_id, value)
                        VALUES (:cid, :aid, :val)
                        ON DUPLICATE KEY UPDATE value = VALUES(value)
                        """
                    ),
                    {"cid": character_id, "aid": attr_id, "val": value},
                )

            session.execute(
                text(
                    """
                    INSERT INTO character_location (character_id, location_id)
                    VALUES (:cid, :loc)
                    """
                ),
                {"cid": character_id, "loc": location_id},
            )

            session.commit()
            character.id = character_id
            character.location_id = location_id
            character.character_type_id = ctype_id
            return character

    def _load_attributes(self, session, character_id: int) -> dict[str, int]:
        rows = session.execute(
            text(
                """
                SELECT a.name AS attr_name, ca.value
                FROM character_attribute ca
                INNER JOIN attribute a ON a.attribute_id = ca.attribute_id
                WHERE ca.character_id = :cid
                """
            ),
            {"cid": character_id},
        ).all()
        return {row.attr_name: row.value for row in rows}

    def _resolve_class_id(self, session, class_name: str) -> int:
        existing = session.execute(
            text(
                """
                SELECT class_id
                FROM class
                WHERE LOWER(open5e_slug) = :slug OR LOWER(name) = :slug
                LIMIT 1
                """
            ),
            {"slug": class_name.lower()},
        ).scalar()
        if existing:
            return existing

        result = session.execute(
            text(
                """
                INSERT INTO class (name, open5e_slug, source)
                VALUES (:name, :slug, 'local')
                ON DUPLICATE KEY UPDATE name = VALUES(name)
                """
            ),
            {"name": class_name, "slug": class_name.lower()},
        )
        session.flush()
        return result.lastrowid

    def _resolve_attribute_id(self, session, attr_name: str) -> Optional[int]:
        return session.execute(
            text("SELECT attribute_id FROM attribute WHERE name = :name LIMIT 1"),
            {"name": attr_name},
        ).scalar()

    def _resolve_character_type_id(self, session) -> int:
        existing = session.execute(
            text("SELECT character_type_id FROM character_type WHERE name = 'player' LIMIT 1")
        ).scalar()
        if existing:
            return existing
        result = session.execute(
            text("INSERT INTO character_type (name) VALUES ('player')")
        )
        session.flush()
        return result.lastrowid


class MysqlEntityRepository(EntityRepository):
    def get(self, entity_id: int) -> Optional[Entity]:
        results = self.get_many([entity_id])
        return results[0] if results else None

    def get_default_location_id(self) -> Optional[int]:
        with SessionLocal() as session:
            return session.execute(
                text(
                    """
                    SELECT location_id
                    FROM location
                    ORDER BY location_id
                    LIMIT 1
                    """
                )
            ).scalar()

    def upsert_entities(self, entities: Sequence[Entity], location_id: Optional[int] = None) -> UpsertResult:
        if not entities:
            return UpsertResult()

        created = 0
        updated = 0
        attached = 0

        with SessionLocal.begin() as session:
            monster_type_id = self._ensure_entity_type(session, "monster")

            for entity in entities:
                payload = {
                    "entity_type_id": monster_type_id,
                    "name": entity.name,
                    "level": entity.level,
                    "armour_class": entity.armour_class,
                    "attack_bonus": entity.attack_bonus,
                    "damage_dice": entity.damage_die,
                    "hp_max": entity.hp_max,
                    "kind": entity.kind,
                }

                existing_id = session.execute(
                    text(
                        """
                        SELECT entity_id
                        FROM entity
                        WHERE LOWER(name) = :name
                        LIMIT 1
                        """
                    ),
                    {"name": entity.name.lower()},
                ).scalar()

                if existing_id:
                    session.execute(
                        text(
                            """
                            UPDATE entity
                            SET level = :level,
                                armour_class = :armour_class,
                                attack_bonus = :attack_bonus,
                                damage_dice = :damage_dice,
                                hp_max = :hp_max,
                                kind = :kind
                            WHERE entity_id = :entity_id
                            """
                        ),
                        payload | {"entity_id": existing_id},
                    )
                    entity_id = existing_id
                    updated += 1
                else:
                    result = session.execute(
                        text(
                            """
                            INSERT INTO entity (entity_type_id, name, level, armour_class, attack_bonus, damage_dice, hp_max, kind)
                            VALUES (:entity_type_id, :name, :level, :armour_class, :attack_bonus, :damage_dice, :hp_max, :kind)
                            """
                        ),
                        payload,
                    )
                    entity_id = result.lastrowid
                    created += 1

                if location_id is not None:
                    attached_now = self._attach_location(session, entity_id, location_id)
                    attached += 1 if attached_now else 0

        return UpsertResult(created=created, updated=updated, attached=attached)

    @staticmethod
    def _ensure_entity_type(session, name: str) -> int:
        row = session.execute(
            text(
                """
                SELECT entity_type_id
                FROM entity_type
                WHERE LOWER(name) = :name
                LIMIT 1
                """
            ),
            {"name": name.lower()},
        ).first()
        if row:
            return row.entity_type_id

        result = session.execute(text("INSERT INTO entity_type (name) VALUES (:name)"), {"name": name})
        return result.lastrowid

    @staticmethod
    def _attach_location(session, entity_id: int, location_id: int) -> bool:
        current_location = session.execute(
            text(
                """
                SELECT location_id
                FROM entity_location
                WHERE entity_id = :entity_id
                LIMIT 1
                """
            ),
            {"entity_id": entity_id},
        ).scalar()

        if current_location is None:
            session.execute(
                text(
                    """
                    INSERT INTO entity_location (entity_id, location_id)
                    VALUES (:entity_id, :location_id)
                    """
                ),
                {"entity_id": entity_id, "location_id": location_id},
            )
            return True

        if current_location != location_id:
            session.execute(
                text(
                    """
                    UPDATE entity_location
                    SET location_id = :location_id
                    WHERE entity_id = :entity_id
                    """
                ),
                {"entity_id": entity_id, "location_id": location_id},
            )
            return True

        return False

    def list_for_level(self, target_level: int, tolerance: int = 2) -> List[Entity]:
        lower = target_level - tolerance
        upper = target_level + tolerance
        return self.list_by_level_band(lower, upper)

    def list_by_level_band(self, level_min: int, level_max: int) -> List[Entity]:
        with SessionLocal() as session:
            rows = session.execute(
                text(
                    """
                    SELECT entity_id, name, level, armour_class, attack_bonus, damage_dice, hp_max, kind
                    FROM entity
                    WHERE level BETWEEN :low AND :high
                    """
                ),
                {"low": level_min, "high": level_max},
            ).all()
            entities: List[Entity] = []
            for row in rows:
                level = row.level or 1
                hp, attack_min, attack_max, armor = _default_stats_for_level(level)
                ac, attack_bonus, damage_die = _default_combat_fields(level)
                if row.hp_max:
                    hp = row.hp_max
                if row.armour_class:
                    ac = row.armour_class
                if row.attack_bonus:
                    attack_bonus = row.attack_bonus
                if row.damage_dice:
                    damage_die = row.damage_dice
                entities.append(
                    Entity(
                        id=row.entity_id,
                        name=row.name,
                        level=level,
                        hp=hp,
                        hp_current=hp,
                        hp_max=hp,
                        attack_min=attack_min,
                        attack_max=attack_max,
                        armor=armor,
                        armour_class=ac,
                        attack_bonus=attack_bonus,
                        damage_die=damage_die,
                        kind=row.kind or "beast",
                        tags=[],
                    )
                )
            return entities

    def list_by_location(self, location_id: int) -> List[Entity]:
        with SessionLocal() as session:
            rows = session.execute(
                text(
                    """
                    SELECT e.entity_id, e.name, e.level, e.entity_type_id, e.armour_class, e.attack_bonus, e.damage_dice, e.hp_max, e.kind
                    FROM entity e
                    JOIN entity_location el ON el.entity_id = e.entity_id
                    WHERE el.location_id = :loc
                    """
                ),
                {"loc": location_id},
            ).all()

            entities: List[Entity] = []
            for row in rows:
                level = row.level or 1
                hp, attack_min, attack_max, armor = _default_stats_for_level(level)
                ac, attack_bonus, damage_die = _default_combat_fields(level)
                if row.hp_max:
                    hp = row.hp_max
                if row.armour_class:
                    ac = row.armour_class
                if row.attack_bonus:
                    attack_bonus = row.attack_bonus
                if row.damage_dice:
                    damage_die = row.damage_dice
                entities.append(
                    Entity(
                        id=row.entity_id,
                        name=row.name,
                        level=level,
                        hp=hp,
                        hp_current=hp,
                        hp_max=hp,
                        attack_min=attack_min,
                        attack_max=attack_max,
                        armor=armor,
                        armour_class=ac,
                        attack_bonus=attack_bonus,
                        damage_die=damage_die,
                        kind=row.kind or "beast",
                        tags=[],
                    )
                )
            return entities

    def get_many(self, entity_ids: List[int]) -> List[Entity]:
        if not entity_ids:
            return []

        with SessionLocal() as session:
            rows = session.execute(
                text(
                    """
                    SELECT entity_id, name, level, armour_class, attack_bonus, damage_dice, hp_max, kind
                    FROM entity
                    WHERE entity_id IN :ids
                    """
                ).bindparams(bindparam("ids", expanding=True)),
                {"ids": entity_ids},
            ).all()

            entities: List[Entity] = []
            for row in rows:
                level = row.level or 1
                hp, attack_min, attack_max, armor = _default_stats_for_level(level)
                ac, attack_bonus, damage_die = _default_combat_fields(level)
                if row.hp_max:
                    hp = row.hp_max
                if row.armour_class:
                    ac = row.armour_class
                if row.attack_bonus:
                    attack_bonus = row.attack_bonus
                if row.damage_dice:
                    damage_die = row.damage_dice
                entities.append(
                    Entity(
                        id=row.entity_id,
                        name=row.name,
                        level=level,
                        hp=hp,
                        hp_current=hp,
                        hp_max=hp,
                        attack_min=attack_min,
                        attack_max=attack_max,
                        armor=armor,
                        armour_class=ac,
                        attack_bonus=attack_bonus,
                        damage_die=damage_die,
                        kind=row.kind or "beast",
                        tags=[],
                    )
                )
            return entities


class MysqlWorldRepository(WorldRepository):
    def load_default(self) -> Optional[World]:
        with SessionLocal() as session:
            row = session.execute(
                text(
                    """
                    SELECT world_id, name, current_turn, threat_level, flags, 1 as rng_seed
                    FROM world
                    ORDER BY world_id
                    LIMIT 1
                    """
                )
            ).first()
            if not row:
                session.execute(text("INSERT INTO world (name) VALUES ('Default World')"))
                session.commit()
                inserted_id = 1
                return World(
                    id=inserted_id,
                    name="Default World",
                    current_turn=0,
                    threat_level=0,
                    flags={},
                    rng_seed=1,
                )
            try:
                flags = json.loads(row.flags) if isinstance(row.flags, str) else (row.flags or {})
            except (TypeError, ValueError, json.JSONDecodeError):
                flags = {}
            return World(
                id=row.world_id,
                name=row.name,
                current_turn=row.current_turn,
                threat_level=row.threat_level,
                flags=flags if isinstance(flags, dict) else {},
                rng_seed=1,
            )

    def save(self, world: World) -> None:
        with SessionLocal() as session:
            if isinstance(world.flags, str):
                payload_flags = world.flags
            elif isinstance(world.flags, dict):
                payload_flags = json.dumps(world.flags)
            else:
                payload_flags = "{}"
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
                {"turn": world.current_turn, "threat": world.threat_level, "flags": payload_flags, "wid": world.id},
            )
            session.commit()


class MysqlLocationRepository(LocationRepository):
    def get(self, location_id: int) -> Optional[Location]:
        with SessionLocal() as session:
            row = session.execute(
                text(
                    """
                    SELECT l.location_id, l.x, l.y, p.name AS place_name
                    FROM location l
                    INNER JOIN place p ON p.place_id = l.place_id
                    WHERE l.location_id = :loc
                    """
                ),
                {"loc": location_id},
            ).first()
            if not row:
                return None
            return Location(id=row.location_id, name=row.place_name, base_level=1)

    def list_all(self) -> List[Location]:
        with SessionLocal() as session:
            rows = session.execute(
                text(
                    """
                    SELECT l.location_id, l.x, l.y, p.name AS place_name
                    FROM location l
                    INNER JOIN place p ON p.place_id = l.place_id
                    ORDER BY l.location_id
                    """
                )
            ).all()
            return [Location(id=row.location_id, name=row.place_name, base_level=1) for row in rows]

    def get_starting_location(self) -> Optional[Location]:
        with SessionLocal() as session:
            row = session.execute(
                text(
                    """
                    SELECT l.location_id, l.x, l.y, p.name AS place_name
                    FROM location l
                    INNER JOIN place p ON p.place_id = l.place_id
                    ORDER BY l.location_id
                    LIMIT 1
                    """
                )
            ).first()
            if not row:
                return None
            return Location(id=row.location_id, name=row.place_name, base_level=1)


class MysqlSpellRepository(SpellRepository):
    def get_by_slug(self, slug: str) -> Optional[Spell]:
        with SessionLocal() as session:
            row = session.execute(
                text(
                    """
                    SELECT slug, name, level_int, school, casting_time, range_text, duration,
                           components, concentration, ritual, desc_text, higher_level, classes_json
                    FROM spell
                    WHERE slug = :slug
                    """
                ),
                {"slug": slug},
            ).mappings().first()
            return _row_to_spell(row) if row else None

    def list_by_class(self, class_slug: str, max_level: int) -> Sequence[Spell]:
        class_name = class_slug.title()
        with SessionLocal() as session:
            rows = session.execute(
                text(
                    """
                    SELECT slug, name, level_int, school, casting_time, range_text, duration,
                           components, concentration, ritual, desc_text, higher_level, classes_json
                    FROM spell
                    WHERE level_int <= :max_level
                      AND (
                        classes_json IS NULL
                        OR JSON_CONTAINS(classes_json, JSON_QUOTE(:class_name))
                      )
                    ORDER BY level_int ASC, name ASC
                    """
                ),
                {"max_level": max_level, "class_name": class_name},
            ).mappings().all()
            return [_row_to_spell(r) for r in rows]
