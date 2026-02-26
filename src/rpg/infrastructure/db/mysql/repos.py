import json
from collections.abc import Callable
from typing import Dict, List, Optional, Sequence

from sqlalchemy import bindparam, text

from rpg.domain.models.character import Character
from rpg.domain.models.character_class import CharacterClass
from rpg.domain.models.entity import Entity
from rpg.domain.models.feature import Feature
from rpg.domain.models.faction import Faction
from rpg.domain.models.encounter_definition import EncounterDefinition, EncounterSlot
from rpg.domain.models.location import HazardProfile, Location
from rpg.domain.models.quest import QuestObjective, QuestObjectiveKind, QuestState, QuestTemplate
from rpg.domain.models.world import World
from rpg.domain.models.spell import Spell
from rpg.domain.repositories import (
    CharacterRepository,
    LocationStateRepository,
    ClassRepository,
    EncounterDefinitionRepository,
    EntityRepository,
    FeatureRepository,
    FactionRepository,
    LocationRepository,
    QuestStateRepository,
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


def _parse_json_list(raw_value) -> list[str]:
    if raw_value is None:
        return []
    if isinstance(raw_value, list):
        return [str(item).strip() for item in raw_value if str(item).strip()]
    if isinstance(raw_value, str):
        text_value = raw_value.strip()
        if not text_value:
            return []
        try:
            parsed = json.loads(text_value)
        except Exception:
            parsed = [segment.strip() for segment in text_value.split(",") if segment.strip()]
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
        return [str(parsed).strip()] if str(parsed).strip() else []
    return []


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
                              c.armour_class, c.armor, c.attack_bonus, c.damage_die, c.speed,
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
                armour_class=row.armour_class if row.armour_class is not None else 10,
                armor=row.armor if row.armor is not None else 0,
                attack_bonus=row.attack_bonus if row.attack_bonus is not None else 2,
                damage_die=row.damage_die if row.damage_die is not None else "d6",
                speed=row.speed if row.speed is not None else 30,
                class_name=row.class_name,
                attributes=attributes,
            )

    def list_all(self) -> List[Character]:
        with SessionLocal() as session:
            rows = session.execute(
                text(
                    """
                    SELECT c.character_id, c.name, c.alive, c.level, c.xp, c.money,
                              c.character_type_id, c.hp_current, c.hp_max,
                              c.armour_class, c.armor, c.attack_bonus, c.damage_die, c.speed,
                              cl.location_id
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
                    armour_class=row.armour_class if row.armour_class is not None else 10,
                    armor=row.armor if row.armor is not None else 0,
                    attack_bonus=row.attack_bonus if row.attack_bonus is not None else 2,
                    damage_die=row.damage_die if row.damage_die is not None else "d6",
                    speed=row.speed if row.speed is not None else 30,
                )
                for row in rows
            ]

    def save(self, character: Character) -> None:
        with SessionLocal() as session:
            dialect = session.bind.dialect.name if session.bind is not None else "mysql"
            if dialect == "mysql":
                character_statement = text(
                    """
                    INSERT INTO `character` (character_id, name, alive, level, xp, money, character_type_id, hp_current, hp_max, armour_class, armor, attack_bonus, damage_die, speed)
                    VALUES (:cid, :name, :alive, :level, :xp, :money, :ctype, :hp_current, :hp_max, :armour_class, :armor, :attack_bonus, :damage_die, :speed)
                    ON DUPLICATE KEY UPDATE
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
                )
                location_statement = text(
                    """
                    INSERT INTO character_location (character_id, location_id)
                    VALUES (:cid, :loc)
                    ON DUPLICATE KEY UPDATE location_id = VALUES(location_id)
                    """
                )
            else:
                character_statement = text(
                    """
                    INSERT INTO "character" (character_id, name, alive, level, xp, money, character_type_id, hp_current, hp_max, armour_class, armor, attack_bonus, damage_die, speed)
                    VALUES (:cid, :name, :alive, :level, :xp, :money, :ctype, :hp_current, :hp_max, :armour_class, :armor, :attack_bonus, :damage_die, :speed)
                    ON CONFLICT(character_id) DO UPDATE SET
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
                )
                location_statement = text(
                    """
                    INSERT INTO character_location (character_id, location_id)
                    VALUES (:cid, :loc)
                    ON CONFLICT(character_id) DO UPDATE SET location_id = excluded.location_id
                    """
                )

            session.execute(
                character_statement,
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
                },
            )
            # Upsert location mapping
            session.execute(
                location_statement,
                {"cid": character.id, "loc": character.location_id},
            )

            for attr_name, value in (character.attributes or {}).items():
                attr_id = self._resolve_attribute_id(session, str(attr_name))
                if attr_id is None:
                    continue
                if dialect == "mysql":
                    attr_statement = text(
                        """
                        INSERT INTO character_attribute (character_id, attribute_id, value)
                        VALUES (:cid, :aid, :val)
                        ON DUPLICATE KEY UPDATE value = VALUES(value)
                        """
                    )
                else:
                    attr_statement = text(
                        """
                        INSERT INTO character_attribute (character_id, attribute_id, value)
                        VALUES (:cid, :aid, :val)
                        ON CONFLICT(character_id, attribute_id) DO UPDATE SET value = excluded.value
                        """
                    )
                session.execute(
                    attr_statement,
                    {"cid": character.id, "aid": attr_id, "val": int(value)},
                )
            session.commit()

    def find_by_location(self, location_id: int) -> List[Character]:
        with SessionLocal() as session:
            rows = session.execute(
                text(
                    """
                    SELECT c.character_id, c.name, c.alive, c.level, c.xp, c.money,
                              c.character_type_id, c.hp_current, c.hp_max,
                              c.armour_class, c.armor, c.attack_bonus, c.damage_die, c.speed,
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
                        armour_class=row.armour_class if row.armour_class is not None else 10,
                        armor=row.armor if row.armor is not None else 0,
                        attack_bonus=row.attack_bonus if row.attack_bonus is not None else 2,
                        damage_die=row.damage_die if row.damage_die is not None else "d6",
                        speed=row.speed if row.speed is not None else 30,
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
                    INSERT INTO `character` (character_type_id, name, alive, level, xp, money, hp_current, hp_max, armour_class, armor, attack_bonus, damage_die, speed)
                    VALUES (:ctype, :name, 1, :level, :xp, :money, :hp_current, :hp_max, :armour_class, :armor, :attack_bonus, :damage_die, :speed)
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
                    "armour_class": character.armour_class,
                    "armor": character.armor,
                    "attack_bonus": character.attack_bonus,
                    "damage_die": character.damage_die,
                    "speed": character.speed,
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
                dialect = session.bind.dialect.name if session.bind is not None else "mysql"
                if dialect == "mysql":
                    attr_statement = text(
                        """
                        INSERT INTO character_attribute (character_id, attribute_id, value)
                        VALUES (:cid, :aid, :val)
                        ON DUPLICATE KEY UPDATE value = VALUES(value)
                        """
                    )
                else:
                    attr_statement = text(
                        """
                        INSERT INTO character_attribute (character_id, attribute_id, value)
                        VALUES (:cid, :aid, :val)
                        ON CONFLICT(character_id, attribute_id) DO UPDATE SET value = excluded.value
                        """
                    )
                session.execute(
                    attr_statement,
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

    def record_progression_unlock(
        self,
        *,
        character_id: int,
        unlock_kind: str,
        unlock_key: str,
        unlocked_level: int,
        created_turn: int,
    ) -> None:
        with SessionLocal.begin() as session:
            operation = self.build_progression_unlock_operation(
                character_id=character_id,
                unlock_kind=unlock_kind,
                unlock_key=unlock_key,
                unlocked_level=unlocked_level,
                created_turn=created_turn,
            )
            operation(session)

    def build_progression_unlock_operation(
        self,
        *,
        character_id: int,
        unlock_kind: str,
        unlock_key: str,
        unlocked_level: int,
        created_turn: int,
    ):
        def _operation(session) -> None:
            if session is None:
                with SessionLocal.begin() as internal_session:
                    self.build_progression_unlock_operation(
                        character_id=character_id,
                        unlock_kind=unlock_kind,
                        unlock_key=unlock_key,
                        unlocked_level=unlocked_level,
                        created_turn=created_turn,
                    )(internal_session)
                return

            dialect = session.bind.dialect.name if session.bind is not None else "mysql"
            if dialect == "mysql":
                statement = text(
                    """
                    INSERT INTO character_progression_unlock (character_id, unlock_kind, unlock_key, unlocked_level, created_turn)
                    VALUES (:character_id, :unlock_kind, :unlock_key, :unlocked_level, :created_turn)
                    ON DUPLICATE KEY UPDATE
                        unlocked_level = VALUES(unlocked_level),
                        created_turn = VALUES(created_turn)
                    """
                )
            else:
                statement = text(
                    """
                    INSERT INTO character_progression_unlock (character_id, unlock_kind, unlock_key, unlocked_level, created_turn)
                    VALUES (:character_id, :unlock_kind, :unlock_key, :unlocked_level, :created_turn)
                    ON CONFLICT(character_id, unlock_kind, unlock_key) DO UPDATE SET
                        unlocked_level = excluded.unlocked_level,
                        created_turn = excluded.created_turn
                    """
                )

            session.execute(
                statement,
                {
                    "character_id": int(character_id),
                    "unlock_kind": str(unlock_kind),
                    "unlock_key": str(unlock_key),
                    "unlocked_level": int(unlocked_level),
                    "created_turn": int(created_turn),
                },
            )

        return _operation

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

    def list_shop_items(self, *, character_id: int, max_items: int = 8) -> list[dict[str, object]]:
        with SessionLocal() as session:
            level = session.execute(
                text("SELECT level FROM `character` WHERE character_id = :cid LIMIT 1"),
                {"cid": int(character_id)},
            ).scalar()
            safe_level = max(1, int(level or 1))
            limit = max(1, int(max_items))
            rows = session.execute(
                text(
                    """
                    SELECT i.item_id, i.name, COALESCE(i.required_level, 1) AS required_level,
                           COALESCE(it.name, 'equipment') AS item_type_name
                    FROM item i
                    LEFT JOIN item_type it ON it.item_type_id = i.item_type_id
                    WHERE COALESCE(i.required_level, 1) <= :level
                    ORDER BY COALESCE(i.required_level, 1) ASC, i.item_id ASC
                    LIMIT :lim
                    """
                ),
                {"level": safe_level, "lim": limit},
            ).all()

            output: list[dict[str, object]] = []
            for row in rows:
                req = int(row.required_level or 1)
                output.append(
                    {
                        "id": f"canonical_item_{int(row.item_id)}",
                        "name": str(row.name),
                        "description": f"Canonical {str(row.item_type_name or 'equipment')} (Req Lv {req}).",
                        "base_price": max(3, req * 4),
                    }
                )
            return output


class MysqlFeatureRepository(FeatureRepository):
    def list_for_character(self, character_id: int) -> List[Feature]:
        with SessionLocal() as session:
            rows = session.execute(
                text(
                    """
                    SELECT DISTINCT a.ability_id,
                           COALESCE(a.slug, LOWER(REPLACE(a.name, ' ', '_'))) AS feature_slug,
                           a.name,
                           COALESCE(a.trigger_key, '') AS trigger_key,
                           COALESCE(a.effect_kind, '') AS effect_kind,
                           COALESCE(a.effect_value, 0) AS effect_value,
                           COALESCE(a.source, 'db') AS source
                    FROM ability a
                    INNER JOIN class_ability ca ON ca.ability_id = a.ability_id
                    INNER JOIN character_class cc ON cc.class_id = ca.class_id
                    WHERE cc.character_id = :cid

                    UNION

                    SELECT DISTINCT a.ability_id,
                           COALESCE(a.slug, LOWER(REPLACE(a.name, ' ', '_'))) AS feature_slug,
                           a.name,
                           COALESCE(a.trigger_key, '') AS trigger_key,
                           COALESCE(a.effect_kind, '') AS effect_kind,
                           COALESCE(a.effect_value, 0) AS effect_value,
                           COALESCE(a.source, 'db') AS source
                    FROM ability a
                    INNER JOIN character_feature cf ON cf.ability_id = a.ability_id
                    WHERE cf.character_id = :cid
                    """
                ),
                {"cid": int(character_id)},
            ).all()

            features: list[Feature] = []
            for row in rows:
                features.append(
                    Feature(
                        id=row.ability_id,
                        slug=str(row.feature_slug),
                        name=str(row.name),
                        trigger_key=str(row.trigger_key),
                        effect_kind=str(row.effect_kind),
                        effect_value=int(row.effect_value or 0),
                        source=str(row.source),
                    )
                )
            return features

    def grant_feature_by_slug(self, character_id: int, feature_slug: str) -> bool:
        slug = str(feature_slug or "").strip().lower()
        if not slug:
            return False

        with SessionLocal() as session:
            ability_id = session.execute(
                text("SELECT ability_id FROM ability WHERE LOWER(COALESCE(slug, '')) = :slug LIMIT 1"),
                {"slug": slug},
            ).scalar()

            if not ability_id:
                return False

            dialect = session.bind.dialect.name if session.bind is not None else "mysql"
            if dialect == "mysql":
                statement = text(
                    """
                    INSERT INTO character_feature (character_id, ability_id)
                    VALUES (:cid, :aid)
                    ON DUPLICATE KEY UPDATE ability_id = VALUES(ability_id)
                    """
                )
            else:
                statement = text(
                    """
                    INSERT INTO character_feature (character_id, ability_id)
                    VALUES (:cid, :aid)
                    ON CONFLICT(character_id, ability_id) DO NOTHING
                    """
                )

            before = session.execute(
                text("SELECT COUNT(*) FROM character_feature WHERE character_id = :cid AND ability_id = :aid"),
                {"cid": int(character_id), "aid": int(ability_id)},
            ).scalar() or 0

            session.execute(statement, {"cid": int(character_id), "aid": int(ability_id)})
            session.commit()

            after = session.execute(
                text("SELECT COUNT(*) FROM character_feature WHERE character_id = :cid AND ability_id = :aid"),
                {"cid": int(character_id), "aid": int(ability_id)},
            ).scalar() or 0

            return int(after) > int(before)

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
                    "tags_json": json.dumps(list(entity.tags or [])),
                    "resistances_json": json.dumps(list(entity.resistances or [])),
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
                                kind = :kind,
                                tags_json = :tags_json,
                                resistances_json = :resistances_json
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
                            INSERT INTO entity (entity_type_id, name, level, armour_class, attack_bonus, damage_dice, hp_max, kind, tags_json, resistances_json)
                            VALUES (:entity_type_id, :name, :level, :armour_class, :attack_bonus, :damage_dice, :hp_max, :kind, :tags_json, :resistances_json)
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
                              , tags_json, resistances_json
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
                        tags=_parse_json_list(getattr(row, "tags_json", None)),
                        resistances=_parse_json_list(getattr(row, "resistances_json", None)),
                    )
                )
            return entities

    def list_by_location(self, location_id: int) -> List[Entity]:
        with SessionLocal() as session:
            rows = session.execute(
                text(
                    """
                    SELECT e.entity_id, e.name, e.level, e.entity_type_id, e.armour_class, e.attack_bonus, e.damage_dice, e.hp_max, e.kind
                              , e.tags_json, e.resistances_json
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
                        tags=_parse_json_list(getattr(row, "tags_json", None)),
                        resistances=_parse_json_list(getattr(row, "resistances_json", None)),
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
                          SELECT entity_id, name, level, armour_class, attack_bonus, damage_dice, hp_max, kind,
                              tags_json, resistances_json
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
                        tags=_parse_json_list(getattr(row, "tags_json", None)),
                        resistances=_parse_json_list(getattr(row, "resistances_json", None)),
                    )
                )
            return entities


class MysqlEncounterDefinitionRepository(EncounterDefinitionRepository):
    _TABLE_BLUEPRINTS: tuple[dict[str, object], ...] = (
        {
            "id": "forest_patrol_table",
            "name": "Forest Patrol Table",
            "faction_id": "the_crown",
            "base_threat": 1.15,
            "level_min": 1,
            "level_max": 4,
            "location_ids": (1,),
            "tags": ("forest", "patrol"),
            "slots": (
                {"monster_slug": "goblin", "candidates": ("Goblin",), "min_count": 1, "max_count": 2, "weight": 3},
                {"monster_slug": "wolf", "candidates": ("Wolf", "Dire Wolf"), "min_count": 1, "max_count": 2, "weight": 2},
            ),
        },
        {
            "id": "ruins_ambush_table",
            "name": "Ruins Ambush Table",
            "faction_id": "thieves_guild",
            "base_threat": 1.25,
            "level_min": 2,
            "level_max": 6,
            "location_ids": (2,),
            "tags": ("ruins", "ambush"),
            "slots": (
                {"monster_slug": "bandit", "candidates": ("Bandit", "Bandit Captain"), "min_count": 1, "max_count": 3, "weight": 3},
                {"monster_slug": "skeleton", "candidates": ("Skeleton",), "min_count": 1, "max_count": 2, "weight": 2},
            ),
        },
        {
            "id": "caves_depths_table",
            "name": "Caves Depths Table",
            "faction_id": "arcane_syndicate",
            "base_threat": 1.35,
            "level_min": 3,
            "level_max": 8,
            "location_ids": (3,),
            "tags": ("caves", "depths"),
            "slots": (
                {"monster_slug": "giant_rat", "candidates": ("Giant Rat", "Rat", "Dire Rat"), "min_count": 1, "max_count": 3, "weight": 2},
                {"monster_slug": "ghoul", "candidates": ("Ghoul", "Skeleton"), "min_count": 1, "max_count": 2, "weight": 3},
            ),
        },
    )

    @staticmethod
    def _resolve_entity_id(session, candidates: Sequence[str]) -> int | None:
        lowered = [str(name).strip().lower() for name in candidates if str(name).strip()]
        if not lowered:
            return None
        return session.execute(
            text(
                """
                SELECT entity_id
                FROM entity
                WHERE LOWER(name) IN :names
                ORDER BY entity_id
                LIMIT 1
                """
            ).bindparams(bindparam("names", expanding=True)),
            {"names": lowered},
        ).scalar()

    def _build_definitions(self, location_id: int | None = None) -> list[EncounterDefinition]:
        definitions: list[EncounterDefinition] = []
        with SessionLocal() as session:
            for row in self._TABLE_BLUEPRINTS:
                row_location_ids = [int(value) for value in row["location_ids"]]
                if location_id is not None and row_location_ids and int(location_id) not in row_location_ids:
                    continue

                slots: list[EncounterSlot] = []
                for slot_row in row["slots"]:
                    entity_id = self._resolve_entity_id(session, slot_row["candidates"])
                    if entity_id is None:
                        continue
                    slots.append(
                        EncounterSlot(
                            entity_id=int(entity_id),
                            monster_slug=str(slot_row["monster_slug"]),
                            min_count=int(slot_row["min_count"]),
                            max_count=int(slot_row["max_count"]),
                            weight=int(slot_row["weight"]),
                        )
                    )

                if not slots:
                    continue

                definitions.append(
                    EncounterDefinition(
                        id=str(row["id"]),
                        name=str(row["name"]),
                        level_min=int(row["level_min"]),
                        level_max=int(row["level_max"]),
                        faction_id=str(row["faction_id"]),
                        tags=[str(value) for value in row["tags"]],
                        slots=slots,
                        base_threat=float(row["base_threat"]),
                        location_ids=row_location_ids,
                    )
                )
        return definitions

    def list_for_location(self, location_id: int) -> List[EncounterDefinition]:
        return self._build_definitions(location_id=location_id)

    def list_global(self) -> List[EncounterDefinition]:
        return self._build_definitions(location_id=None)


class MysqlFactionRepository(FactionRepository):
    @staticmethod
    def _slugify(value: str) -> str:
        lowered = str(value or "").strip().lower()
        if not lowered:
            return ""
        return "_".join(lowered.replace("-", " ").split())

    def _load_reputation(self, session, faction_pk: int) -> dict[str, int]:
        rows = session.execute(
            text(
                """
                SELECT character_id, reputation_score
                FROM character_reputation
                WHERE faction_id = :faction_id
                """
            ),
            {"faction_id": int(faction_pk)},
        ).all()
        return {f"character:{int(row.character_id)}": int(row.reputation_score) for row in rows}

    def get(self, faction_id: str) -> Optional[Faction]:
        key = str(faction_id or "").strip().lower()
        if not key:
            return None
        with SessionLocal() as session:
            row = session.execute(
                text(
                    """
                    SELECT faction_id, name, COALESCE(slug, LOWER(REPLACE(name, ' ', '_'))) AS slug,
                           COALESCE(alignment, 'neutral') AS alignment,
                           COALESCE(influence, 0) AS influence
                    FROM faction
                    WHERE LOWER(COALESCE(slug, '')) = :key OR LOWER(name) = :key
                    LIMIT 1
                    """
                ),
                {"key": key},
            ).first()
            if not row:
                return None
            reputation = self._load_reputation(session, int(row.faction_id))
            return Faction(
                id=str(row.slug),
                name=str(row.name),
                influence=int(row.influence),
                alignment=str(row.alignment),
                reputation=reputation,
            )

    def list_all(self) -> List[Faction]:
        with SessionLocal() as session:
            rows = session.execute(
                text(
                    """
                    SELECT faction_id, name, COALESCE(slug, LOWER(REPLACE(name, ' ', '_'))) AS slug,
                           COALESCE(alignment, 'neutral') AS alignment,
                           COALESCE(influence, 0) AS influence
                    FROM faction
                    ORDER BY faction_id
                    """
                )
            ).all()
            factions: list[Faction] = []
            for row in rows:
                factions.append(
                    Faction(
                        id=str(row.slug),
                        name=str(row.name),
                        influence=int(row.influence),
                        alignment=str(row.alignment),
                        reputation=self._load_reputation(session, int(row.faction_id)),
                    )
                )
            return factions

    def save(self, faction: Faction) -> None:
        slug = self._slugify(faction.id) or self._slugify(faction.name)
        with SessionLocal.begin() as session:
            row = session.execute(
                text(
                    """
                    SELECT faction_id
                    FROM faction
                    WHERE LOWER(COALESCE(slug, '')) = :slug OR LOWER(name) = :name
                    LIMIT 1
                    """
                ),
                {"slug": slug, "name": str(faction.name).strip().lower()},
            ).first()

            if row is None:
                result = session.execute(
                    text(
                        """
                        INSERT INTO faction (name, slug, alignment, influence)
                        VALUES (:name, :slug, :alignment, :influence)
                        """
                    ),
                    {
                        "name": faction.name,
                        "slug": slug,
                        "alignment": str(faction.alignment or "neutral"),
                        "influence": int(faction.influence),
                    },
                )
                faction_pk = int(result.lastrowid)
            else:
                faction_pk = int(row.faction_id)
                session.execute(
                    text(
                        """
                        UPDATE faction
                        SET name = :name,
                            slug = :slug,
                            alignment = :alignment,
                            influence = :influence
                        WHERE faction_id = :faction_id
                        """
                    ),
                    {
                        "name": faction.name,
                        "slug": slug,
                        "alignment": str(faction.alignment or "neutral"),
                        "influence": int(faction.influence),
                        "faction_id": faction_pk,
                    },
                )

            existing = {
                int(row.character_id): int(row.reputation_score)
                for row in session.execute(
                    text(
                        """
                        SELECT character_id, reputation_score
                        FROM character_reputation
                        WHERE faction_id = :faction_id
                        """
                    ),
                    {"faction_id": faction_pk},
                ).all()
            }

            dialect = session.bind.dialect.name if session.bind is not None else "mysql"
            if dialect == "mysql":
                rep_statement = text(
                    """
                    INSERT INTO character_reputation (character_id, faction_id, reputation_score, updated_turn)
                    VALUES (:character_id, :faction_id, :reputation_score, :updated_turn)
                    ON DUPLICATE KEY UPDATE
                        reputation_score = VALUES(reputation_score),
                        updated_turn = VALUES(updated_turn)
                    """
                )
            else:
                rep_statement = text(
                    """
                    INSERT INTO character_reputation (character_id, faction_id, reputation_score, updated_turn)
                    VALUES (:character_id, :faction_id, :reputation_score, :updated_turn)
                    ON CONFLICT(character_id, faction_id) DO UPDATE SET
                        reputation_score = excluded.reputation_score,
                        updated_turn = excluded.updated_turn
                    """
                )

            for target, score in (faction.reputation or {}).items():
                key = str(target)
                if not key.startswith("character:"):
                    continue
                try:
                    character_id = int(key.split(":", 1)[1])
                except Exception:
                    continue

                after = int(score)
                before = int(existing.get(character_id, 0))

                session.execute(
                    rep_statement,
                    {
                        "character_id": character_id,
                        "faction_id": faction_pk,
                        "reputation_score": after,
                        "updated_turn": 0,
                    },
                )

                if after != before:
                    session.execute(
                        text(
                            """
                            INSERT INTO reputation_history (character_id, faction_id, delta, score_before, score_after, reason, changed_turn)
                            VALUES (:character_id, :faction_id, :delta, :before, :after, :reason, :changed_turn)
                            """
                        ),
                        {
                            "character_id": character_id,
                            "faction_id": faction_pk,
                            "delta": after - before,
                            "before": before,
                            "after": after,
                            "reason": "faction_sync",
                            "changed_turn": 0,
                        },
                    )

    @staticmethod
    def build_reputation_delta_operation(
        *,
        faction_id: str,
        character_id: int,
        delta: int,
        reason: str,
        changed_turn: int,
    ) -> Callable[[object], None]:
        def _operation(session) -> None:
            key = str(faction_id or "").strip().lower()
            if not key:
                return

            faction_row = session.execute(
                text(
                    """
                    SELECT faction_id
                    FROM faction
                    WHERE LOWER(COALESCE(slug, '')) = :key OR LOWER(name) = :key
                    LIMIT 1
                    """
                ),
                {"key": key},
            ).first()
            if faction_row is None:
                return

            faction_pk = int(faction_row.faction_id)
            row = session.execute(
                text(
                    """
                    SELECT reputation_score
                    FROM character_reputation
                    WHERE character_id = :character_id AND faction_id = :faction_id
                    LIMIT 1
                    """
                ),
                {"character_id": int(character_id), "faction_id": faction_pk},
            ).first()

            before = int(row.reputation_score) if row else 0
            after = before + int(delta)

            dialect = session.bind.dialect.name if session.bind is not None else "mysql"
            if dialect == "mysql":
                statement = text(
                    """
                    INSERT INTO character_reputation (character_id, faction_id, reputation_score, updated_turn)
                    VALUES (:character_id, :faction_id, :reputation_score, :updated_turn)
                    ON DUPLICATE KEY UPDATE
                        reputation_score = VALUES(reputation_score),
                        updated_turn = VALUES(updated_turn)
                    """
                )
            else:
                statement = text(
                    """
                    INSERT INTO character_reputation (character_id, faction_id, reputation_score, updated_turn)
                    VALUES (:character_id, :faction_id, :reputation_score, :updated_turn)
                    ON CONFLICT(character_id, faction_id) DO UPDATE SET
                        reputation_score = excluded.reputation_score,
                        updated_turn = excluded.updated_turn
                    """
                )

            session.execute(
                statement,
                {
                    "character_id": int(character_id),
                    "faction_id": faction_pk,
                    "reputation_score": after,
                    "updated_turn": int(changed_turn),
                },
            )

            session.execute(
                text(
                    """
                    UPDATE faction
                    SET influence = CASE
                        WHEN :delta < 0 THEN GREATEST(0, COALESCE(influence, 0) - 1)
                        WHEN :delta > 0 THEN COALESCE(influence, 0) + 1
                        ELSE COALESCE(influence, 0)
                    END
                    WHERE faction_id = :faction_id
                    """
                ),
                {"delta": int(delta), "faction_id": faction_pk},
            )

            session.execute(
                text(
                    """
                    INSERT INTO reputation_history (character_id, faction_id, delta, score_before, score_after, reason, changed_turn)
                    VALUES (:character_id, :faction_id, :delta, :score_before, :score_after, :reason, :changed_turn)
                    """
                ),
                {
                    "character_id": int(character_id),
                    "faction_id": faction_pk,
                    "delta": int(delta),
                    "score_before": int(before),
                    "score_after": int(after),
                    "reason": str(reason or "reputation_change"),
                    "changed_turn": int(changed_turn),
                },
            )

        return _operation


class MysqlNarrativeStateRepository(QuestStateRepository, LocationStateRepository):
    def list_definitions(self) -> List[QuestTemplate]:
        with SessionLocal() as session:
            rows = session.execute(
                text(
                    """
                    SELECT q.quest_slug, q.title, q.objective_kind, q.target_count,
                           q.reward_xp, q.reward_money, f.slug AS faction_slug
                    FROM quest_definition q
                    LEFT JOIN faction f ON f.faction_id = q.faction_id
                    ORDER BY q.quest_definition_id
                    """
                )
            ).all()
            templates: list[QuestTemplate] = []
            for row in rows:
                kind_raw = str(row.objective_kind or "hunt").strip().lower()
                kind = QuestObjectiveKind(kind_raw) if kind_raw in {item.value for item in QuestObjectiveKind} else QuestObjectiveKind.HUNT
                templates.append(
                    QuestTemplate(
                        slug=str(row.quest_slug),
                        title=str(row.title),
                        objective=QuestObjective(kind=kind, target_key=str(row.quest_slug), target_count=int(row.target_count or 1)),
                        reward_xp=int(row.reward_xp or 0),
                        reward_money=int(row.reward_money or 0),
                        faction_id=str(row.faction_slug) if row.faction_slug else None,
                    )
                )
            return templates

    def list_active_for_character(self, *, character_id: int) -> List[QuestState]:
        with SessionLocal() as session:
            rows = session.execute(
                text(
                    """
                    SELECT q.quest_slug,
                           c.status,
                           c.progress,
                           c.accepted_turn,
                           c.completed_turn,
                           c.seed_key
                    FROM character_active_quest c
                    INNER JOIN quest_definition q ON q.quest_definition_id = c.quest_definition_id
                    WHERE c.character_id = :character_id
                    ORDER BY c.character_active_quest_id
                    """
                ),
                {"character_id": int(character_id)},
            ).all()
            return [
                QuestState(
                    template_slug=str(row.quest_slug),
                    status=str(row.status),
                    progress=int(row.progress or 0),
                    accepted_turn=int(row.accepted_turn or 0),
                    completed_turn=int(row.completed_turn) if row.completed_turn is not None else None,
                    metadata={"seed_key": str(row.seed_key or "")},
                )
                for row in rows
            ]

    def _resolve_definition_id(self, session, template_slug: str) -> int:
        slug = str(template_slug or "").strip().lower()
        row = session.execute(
            text(
                """
                SELECT quest_definition_id
                FROM quest_definition
                WHERE LOWER(quest_slug) = :slug
                LIMIT 1
                """
            ),
            {"slug": slug},
        ).scalar()
        if row:
            return int(row)

        result = session.execute(
            text(
                """
                INSERT INTO quest_definition (quest_slug, title, objective_kind, target_count, reward_xp, reward_money, source)
                VALUES (:slug, :title, 'hunt', 1, 0, 0, 'runtime')
                """
            ),
            {"slug": slug, "title": slug.replace("_", " ").title()},
        )
        return int(result.lastrowid)

    def save_active(
        self,
        *,
        character_id: int,
        state: QuestState,
        target_count: int,
        seed_key: str,
    ) -> None:
        with SessionLocal.begin() as session:
            definition_id = self._resolve_definition_id(session, state.template_slug)
            dialect = session.bind.dialect.name if session.bind is not None else "mysql"
            if dialect == "mysql":
                statement = text(
                    """
                    INSERT INTO character_active_quest (
                        character_id,
                        quest_definition_id,
                        status,
                        progress,
                        target_count,
                        accepted_turn,
                        completed_turn,
                        seed_key
                    )
                    VALUES (
                        :character_id,
                        :quest_definition_id,
                        :status,
                        :progress,
                        :target_count,
                        :accepted_turn,
                        :completed_turn,
                        :seed_key
                    )
                    ON DUPLICATE KEY UPDATE
                        status = VALUES(status),
                        progress = VALUES(progress),
                        target_count = VALUES(target_count),
                        accepted_turn = VALUES(accepted_turn),
                        completed_turn = VALUES(completed_turn),
                        seed_key = VALUES(seed_key)
                    """
                )
            else:
                statement = text(
                    """
                    INSERT INTO character_active_quest (
                        character_id,
                        quest_definition_id,
                        status,
                        progress,
                        target_count,
                        accepted_turn,
                        completed_turn,
                        seed_key
                    )
                    VALUES (
                        :character_id,
                        :quest_definition_id,
                        :status,
                        :progress,
                        :target_count,
                        :accepted_turn,
                        :completed_turn,
                        :seed_key
                    )
                    ON CONFLICT(character_id, quest_definition_id) DO UPDATE SET
                        status = excluded.status,
                        progress = excluded.progress,
                        target_count = excluded.target_count,
                        accepted_turn = excluded.accepted_turn,
                        completed_turn = excluded.completed_turn,
                        seed_key = excluded.seed_key
                    """
                )

            session.execute(
                statement,
                {
                    "character_id": int(character_id),
                    "quest_definition_id": int(definition_id),
                    "status": str(state.status),
                    "progress": int(state.progress),
                    "target_count": max(1, int(target_count)),
                    "accepted_turn": int(state.accepted_turn),
                    "completed_turn": int(state.completed_turn) if state.completed_turn is not None else None,
                    "seed_key": str(seed_key or ""),
                },
            )

    def append_history(
        self,
        *,
        character_id: int,
        template_slug: str,
        action: str,
        action_turn: int,
        payload_json: str,
    ) -> None:
        with SessionLocal.begin() as session:
            definition_id = self._resolve_definition_id(session, template_slug)
            session.execute(
                text(
                    """
                    INSERT INTO quest_history (character_id, quest_definition_id, action, action_turn, payload_json)
                    VALUES (:character_id, :quest_definition_id, :action, :action_turn, :payload_json)
                    """
                ),
                {
                    "character_id": int(character_id),
                    "quest_definition_id": int(definition_id),
                    "action": str(action),
                    "action_turn": int(action_turn),
                    "payload_json": payload_json,
                },
            )

    def save_active_with_history(
        self,
        *,
        character_id: int,
        state: QuestState,
        target_count: int,
        seed_key: str,
        action: str,
        action_turn: int,
        payload_json: str,
    ) -> None:
        with SessionLocal.begin() as session:
            definition_id = self._resolve_definition_id(session, state.template_slug)
            dialect = session.bind.dialect.name if session.bind is not None else "mysql"
            if dialect == "mysql":
                active_statement = text(
                    """
                    INSERT INTO character_active_quest (
                        character_id,
                        quest_definition_id,
                        status,
                        progress,
                        target_count,
                        accepted_turn,
                        completed_turn,
                        seed_key
                    )
                    VALUES (
                        :character_id,
                        :quest_definition_id,
                        :status,
                        :progress,
                        :target_count,
                        :accepted_turn,
                        :completed_turn,
                        :seed_key
                    )
                    ON DUPLICATE KEY UPDATE
                        status = VALUES(status),
                        progress = VALUES(progress),
                        target_count = VALUES(target_count),
                        accepted_turn = VALUES(accepted_turn),
                        completed_turn = VALUES(completed_turn),
                        seed_key = VALUES(seed_key)
                    """
                )
            else:
                active_statement = text(
                    """
                    INSERT INTO character_active_quest (
                        character_id,
                        quest_definition_id,
                        status,
                        progress,
                        target_count,
                        accepted_turn,
                        completed_turn,
                        seed_key
                    )
                    VALUES (
                        :character_id,
                        :quest_definition_id,
                        :status,
                        :progress,
                        :target_count,
                        :accepted_turn,
                        :completed_turn,
                        :seed_key
                    )
                    ON CONFLICT(character_id, quest_definition_id) DO UPDATE SET
                        status = excluded.status,
                        progress = excluded.progress,
                        target_count = excluded.target_count,
                        accepted_turn = excluded.accepted_turn,
                        completed_turn = excluded.completed_turn,
                        seed_key = excluded.seed_key
                    """
                )

            session.execute(
                active_statement,
                {
                    "character_id": int(character_id),
                    "quest_definition_id": int(definition_id),
                    "status": str(state.status),
                    "progress": int(state.progress),
                    "target_count": max(1, int(target_count)),
                    "accepted_turn": int(state.accepted_turn),
                    "completed_turn": int(state.completed_turn) if state.completed_turn is not None else None,
                    "seed_key": str(seed_key or ""),
                },
            )

            session.execute(
                text(
                    """
                    INSERT INTO quest_history (character_id, quest_definition_id, action, action_turn, payload_json)
                    VALUES (:character_id, :quest_definition_id, :action, :action_turn, :payload_json)
                    """
                ),
                {
                    "character_id": int(character_id),
                    "quest_definition_id": int(definition_id),
                    "action": str(action),
                    "action_turn": int(action_turn),
                    "payload_json": payload_json,
                },
            )

    def _save_active_with_history_in_session(
        self,
        *,
        session,
        character_id: int,
        state: QuestState,
        target_count: int,
        seed_key: str,
        action: str,
        action_turn: int,
        payload_json: str,
    ) -> None:
        definition_id = self._resolve_definition_id(session, state.template_slug)
        dialect = session.bind.dialect.name if session.bind is not None else "mysql"
        if dialect == "mysql":
            active_statement = text(
                """
                INSERT INTO character_active_quest (
                    character_id,
                    quest_definition_id,
                    status,
                    progress,
                    target_count,
                    accepted_turn,
                    completed_turn,
                    seed_key
                )
                VALUES (
                    :character_id,
                    :quest_definition_id,
                    :status,
                    :progress,
                    :target_count,
                    :accepted_turn,
                    :completed_turn,
                    :seed_key
                )
                ON DUPLICATE KEY UPDATE
                    status = VALUES(status),
                    progress = VALUES(progress),
                    target_count = VALUES(target_count),
                    accepted_turn = VALUES(accepted_turn),
                    completed_turn = VALUES(completed_turn),
                    seed_key = VALUES(seed_key)
                """
            )
        else:
            active_statement = text(
                """
                INSERT INTO character_active_quest (
                    character_id,
                    quest_definition_id,
                    status,
                    progress,
                    target_count,
                    accepted_turn,
                    completed_turn,
                    seed_key
                )
                VALUES (
                    :character_id,
                    :quest_definition_id,
                    :status,
                    :progress,
                    :target_count,
                    :accepted_turn,
                    :completed_turn,
                    :seed_key
                )
                ON CONFLICT(character_id, quest_definition_id) DO UPDATE SET
                    status = excluded.status,
                    progress = excluded.progress,
                    target_count = excluded.target_count,
                    accepted_turn = excluded.accepted_turn,
                    completed_turn = excluded.completed_turn,
                    seed_key = excluded.seed_key
                """
            )

        session.execute(
            active_statement,
            {
                "character_id": int(character_id),
                "quest_definition_id": int(definition_id),
                "status": str(state.status),
                "progress": int(state.progress),
                "target_count": max(1, int(target_count)),
                "accepted_turn": int(state.accepted_turn),
                "completed_turn": int(state.completed_turn) if state.completed_turn is not None else None,
                "seed_key": str(seed_key or ""),
            },
        )

        session.execute(
            text(
                """
                INSERT INTO quest_history (character_id, quest_definition_id, action, action_turn, payload_json)
                VALUES (:character_id, :quest_definition_id, :action, :action_turn, :payload_json)
                """
            ),
            {
                "character_id": int(character_id),
                "quest_definition_id": int(definition_id),
                "action": str(action),
                "action_turn": int(action_turn),
                "payload_json": payload_json,
            },
        )

    def build_save_active_with_history_operation(
        self,
        *,
        character_id: int,
        state: QuestState,
        target_count: int,
        seed_key: str,
        action: str,
        action_turn: int,
        payload_json: str,
    ) -> Callable[[object], None]:
        def _operation(session) -> None:
            self._save_active_with_history_in_session(
                session=session,
                character_id=character_id,
                state=state,
                target_count=target_count,
                seed_key=seed_key,
                action=action,
                action_turn=action_turn,
                payload_json=payload_json,
            )

        return _operation

    @staticmethod
    def build_location_flag_change_operation(
        *,
        location_id: int,
        changed_turn: int,
        flag_key: str,
        old_value: str | None,
        new_value: str | None,
        reason: str,
    ) -> Callable[[object], None]:
        def _operation(session) -> None:
            session.execute(
                text(
                    """
                    INSERT INTO location_history (location_id, changed_turn, flag_key, old_value, new_value, reason)
                    VALUES (:location_id, :changed_turn, :flag_key, :old_value, :new_value, :reason)
                    """
                ),
                {
                    "location_id": int(location_id),
                    "changed_turn": int(changed_turn),
                    "flag_key": str(flag_key),
                    "old_value": old_value,
                    "new_value": new_value,
                    "reason": str(reason),
                },
            )

        return _operation

    def record_flag_change(
        self,
        *,
        location_id: int,
        changed_turn: int,
        flag_key: str,
        old_value: str | None,
        new_value: str | None,
        reason: str,
    ) -> None:
        with SessionLocal.begin() as session:
            session.execute(
                text(
                    """
                    INSERT INTO location_history (location_id, changed_turn, flag_key, old_value, new_value, reason)
                    VALUES (:location_id, :changed_turn, :flag_key, :old_value, :new_value, :reason)
                    """
                ),
                {
                    "location_id": int(location_id),
                    "changed_turn": int(changed_turn),
                    "flag_key": str(flag_key),
                    "old_value": old_value,
                    "new_value": new_value,
                    "reason": str(reason),
                },
            )


class MysqlWorldRepository(WorldRepository):
    @staticmethod
    def _coerce_flag_payload(value: object) -> str | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    def list_world_flags(self, world_id: int | None = None) -> dict[str, str]:
        with SessionLocal() as session:
            target_world_id = world_id
            if target_world_id is None:
                row = session.execute(text("SELECT world_id FROM world ORDER BY world_id LIMIT 1")).first()
                if not row:
                    return {}
                target_world_id = int(row.world_id)
            try:
                rows = session.execute(
                    text(
                        """
                        SELECT flag_key, flag_value
                        FROM world_flag
                        WHERE world_id = :wid
                        """
                    ),
                    {"wid": int(target_world_id)},
                ).all()
            except Exception:
                return {}
            return {
                str(row.flag_key): str(row.flag_value)
                for row in rows
                if getattr(row, "flag_key", None) is not None and getattr(row, "flag_value", None) is not None
            }

    def set_world_flag(
        self,
        *,
        world_id: int,
        flag_key: str,
        flag_value: str | None,
        changed_turn: int,
        reason: str,
    ) -> None:
        with SessionLocal.begin() as session:
            operation = self.build_set_world_flag_operation(
                world_id=world_id,
                flag_key=flag_key,
                flag_value=flag_value,
                changed_turn=changed_turn,
                reason=reason,
            )
            operation(session)

    def build_set_world_flag_operation(
        self,
        *,
        world_id: int,
        flag_key: str,
        flag_value: str | None,
        changed_turn: int,
        reason: str,
    ):
        def _operation(session) -> None:
            dialect = session.bind.dialect.name if session.bind is not None else "mysql"
            prior = None
            try:
                prior = session.execute(
                    text(
                        """
                        SELECT flag_value
                        FROM world_flag
                        WHERE world_id = :wid AND flag_key = :flag_key
                        """
                    ),
                    {"wid": int(world_id), "flag_key": str(flag_key)},
                ).first()
            except Exception:
                prior = None
            old_value = None if prior is None else prior.flag_value
            payload = self._coerce_flag_payload(flag_value)

            if dialect == "mysql":
                session.execute(
                    text(
                        """
                        INSERT INTO world_flag (world_id, flag_key, flag_value, changed_turn, reason)
                        VALUES (:wid, :flag_key, :flag_value, :changed_turn, :reason)
                        ON DUPLICATE KEY UPDATE
                            flag_value = VALUES(flag_value),
                            changed_turn = VALUES(changed_turn),
                            reason = VALUES(reason)
                        """
                    ),
                    {
                        "wid": int(world_id),
                        "flag_key": str(flag_key),
                        "flag_value": payload,
                        "changed_turn": int(changed_turn),
                        "reason": str(reason),
                    },
                )
            else:
                session.execute(
                    text(
                        """
                        INSERT INTO world_flag (world_id, flag_key, flag_value, changed_turn, reason)
                        VALUES (:wid, :flag_key, :flag_value, :changed_turn, :reason)
                        ON CONFLICT(world_id, flag_key) DO UPDATE SET
                            flag_value = excluded.flag_value,
                            changed_turn = excluded.changed_turn,
                            reason = excluded.reason
                        """
                    ),
                    {
                        "wid": int(world_id),
                        "flag_key": str(flag_key),
                        "flag_value": payload,
                        "changed_turn": int(changed_turn),
                        "reason": str(reason),
                    },
                )
            try:
                session.execute(
                    text(
                        """
                        INSERT INTO world_history (world_id, changed_turn, flag_key, old_value, new_value, reason)
                        VALUES (:wid, :changed_turn, :flag_key, :old_value, :new_value, :reason)
                        """
                    ),
                    {
                        "wid": int(world_id),
                        "changed_turn": int(changed_turn),
                        "flag_key": str(flag_key),
                        "old_value": None if old_value is None else str(old_value),
                        "new_value": payload,
                        "reason": str(reason),
                    },
                )
            except Exception:
                pass

        return _operation

    def load_default(self) -> Optional[World]:
        with SessionLocal() as session:
            row = session.execute(
                text(
                    """
                    SELECT world_id, name, current_turn, threat_level, flags, COALESCE(rng_seed, 1) AS rng_seed
                    FROM world
                    ORDER BY world_id
                    LIMIT 1
                    """
                )
            ).first()
            if not row:
                session.execute(text("INSERT INTO world (name, rng_seed) VALUES ('Default World', 1)"))
                session.commit()
                inserted_id = 1
                world = World(
                    id=inserted_id,
                    name="Default World",
                    current_turn=0,
                    threat_level=0,
                    flags={},
                    rng_seed=1,
                )
                self._merge_stored_world_flags(world)
                return world
            try:
                flags = json.loads(row.flags) if isinstance(row.flags, str) else (row.flags or {})
            except (TypeError, ValueError, json.JSONDecodeError):
                flags = {}
            world = World(
                id=row.world_id,
                name=row.name,
                current_turn=row.current_turn,
                threat_level=row.threat_level,
                flags=flags if isinstance(flags, dict) else {},
                rng_seed=int(row.rng_seed or 1),
            )
            self._merge_stored_world_flags(world)
            return world

    def _merge_stored_world_flags(self, world: World) -> None:
        stored = self.list_world_flags(world_id=int(getattr(world, "id", 1) or 1))
        if not stored:
            return
        if not isinstance(getattr(world, "flags", None), dict):
            world.flags = {}
        world.flags["world_flags"] = dict(stored)

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
                        flags = :flags,
                        rng_seed = :rng_seed
                    WHERE world_id = :wid
                    """
                ),
                {
                    "turn": world.current_turn,
                    "threat": world.threat_level,
                    "flags": payload_flags,
                    "rng_seed": int(getattr(world, "rng_seed", 1) or 1),
                    "wid": world.id,
                },
            )
            session.commit()


class MysqlLocationRepository(LocationRepository):
    def get(self, location_id: int) -> Optional[Location]:
        with SessionLocal() as session:
            row = session.execute(
                text(
                    """
                    SELECT l.location_id, l.x, l.y, p.name AS place_name,
                           COALESCE(l.biome_key, 'wilderness') AS biome_key,
                           COALESCE(l.hazard_profile_key, 'standard') AS hazard_profile_key,
                           l.environmental_flags
                    FROM location l
                    INNER JOIN place p ON p.place_id = l.place_id
                    WHERE l.location_id = :loc
                    """
                ),
                {"loc": location_id},
            ).first()
            if not row:
                return None
            flags_raw = row.environmental_flags
            if isinstance(flags_raw, str):
                try:
                    parsed = json.loads(flags_raw)
                except Exception:
                    parsed = []
            else:
                parsed = flags_raw if isinstance(flags_raw, list) else []
            env_flags = [str(item) for item in parsed] if isinstance(parsed, list) else []
            return Location(
                id=row.location_id,
                name=row.place_name,
                biome=row.biome_key or "wilderness",
                base_level=1,
                hazard_profile=HazardProfile(
                    key=row.hazard_profile_key or "standard",
                    environmental_flags=env_flags,
                ),
            )

    def list_all(self) -> List[Location]:
        with SessionLocal() as session:
            rows = session.execute(
                text(
                    """
                    SELECT l.location_id, l.x, l.y, p.name AS place_name,
                           COALESCE(l.biome_key, 'wilderness') AS biome_key,
                           COALESCE(l.hazard_profile_key, 'standard') AS hazard_profile_key,
                           l.environmental_flags
                    FROM location l
                    INNER JOIN place p ON p.place_id = l.place_id
                    ORDER BY l.location_id
                    """
                )
            ).all()
            locations: list[Location] = []
            for row in rows:
                flags_raw = row.environmental_flags
                if isinstance(flags_raw, str):
                    try:
                        parsed = json.loads(flags_raw)
                    except Exception:
                        parsed = []
                else:
                    parsed = flags_raw if isinstance(flags_raw, list) else []
                env_flags = [str(item) for item in parsed] if isinstance(parsed, list) else []
                locations.append(
                    Location(
                        id=row.location_id,
                        name=row.place_name,
                        biome=row.biome_key or "wilderness",
                        base_level=1,
                        hazard_profile=HazardProfile(
                            key=row.hazard_profile_key or "standard",
                            environmental_flags=env_flags,
                        ),
                    )
                )
            return locations

    def get_starting_location(self) -> Optional[Location]:
        with SessionLocal() as session:
            row = session.execute(
                text(
                    """
                    SELECT l.location_id, l.x, l.y, p.name AS place_name,
                           COALESCE(l.biome_key, 'wilderness') AS biome_key,
                           COALESCE(l.hazard_profile_key, 'standard') AS hazard_profile_key,
                           l.environmental_flags
                    FROM location l
                    INNER JOIN place p ON p.place_id = l.place_id
                    ORDER BY l.location_id
                    LIMIT 1
                    """
                )
            ).first()
            if not row:
                return None
            flags_raw = row.environmental_flags
            if isinstance(flags_raw, str):
                try:
                    parsed = json.loads(flags_raw)
                except Exception:
                    parsed = []
            else:
                parsed = flags_raw if isinstance(flags_raw, list) else []
            env_flags = [str(item) for item in parsed] if isinstance(parsed, list) else []
            return Location(
                id=row.location_id,
                name=row.place_name,
                biome=row.biome_key or "wilderness",
                base_level=1,
                hazard_profile=HazardProfile(
                    key=row.hazard_profile_key or "standard",
                    environmental_flags=env_flags,
                ),
            )


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
