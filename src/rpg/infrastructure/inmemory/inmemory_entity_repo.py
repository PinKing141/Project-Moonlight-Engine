from __future__ import annotations

from typing import Dict, List

from rpg.domain.models.entity import Entity
from rpg.domain.repositories import EntityRepository
from rpg.infrastructure.db.mysql.open5e_monster_importer import UpsertResult


class InMemoryEntityRepository(EntityRepository):
    def __init__(self, name_generator=None) -> None:
        self._entities: List[Entity] = [
            Entity(
                id=1,
                name="Goblin",
                level=1,
                hp=7,
                attack_bonus=3,
                damage_die="d6",
                armour_class=12,
                kind="humanoid",
            ),
            Entity(
                id=2,
                name="Wolf",
                level=1,
                hp=8,
                attack_bonus=3,
                damage_die="d6",
                armour_class=12,
                kind="beast",
            ),
            Entity(
                id=3,
                name="Skeleton",
                level=2,
                hp=11,
                attack_bonus=4,
                damage_die="d6",
                armour_class=13,
                kind="undead",
            ),
        ]
        self._by_location: Dict[int, List[int]] = {1: [1, 2]}
        self._apply_generated_names(name_generator)

    def _apply_generated_names(self, name_generator) -> None:
        if name_generator is None:
            return

        for entity in self._entities:
            try:
                generated = name_generator.generate_entity_name(
                    default_name=entity.name,
                    kind=entity.kind,
                    faction_id=entity.faction_id,
                    entity_id=entity.id,
                    level=entity.level,
                )
            except Exception:
                continue

            if generated and generated.strip():
                entity.name = generated.strip()

    def get(self, entity_id: int) -> Entity | None:
        for entity in self._entities:
            if entity.id == entity_id:
                return entity
        return None

    def get_many(self, entity_ids: List[int]) -> List[Entity]:
        if not entity_ids:
            return []
        ids = set(entity_ids)
        return [entity for entity in self._entities if entity.id in ids]

    def list_for_level(self, target_level: int, tolerance: int = 2) -> List[Entity]:
        lower = target_level - tolerance
        upper = target_level + tolerance
        return [entity for entity in self._entities if lower <= entity.level <= upper]

    def list_by_location(self, location_id: int) -> List[Entity]:
        ids = self._by_location.get(location_id, [])
        return [entity for entity in self._entities if entity.id in ids]

    def list_by_level_band(self, level_min: int, level_max: int) -> List[Entity]:
        return [entity for entity in self._entities if level_min <= entity.level <= level_max]

    def upsert_entities(self, entities: List[Entity], location_id: int | None = None) -> UpsertResult:
        next_id = max((entity.id for entity in self._entities), default=0) + 1
        created = 0
        updated = 0
        attached = 0

        for entity in entities:
            existing = next((e for e in self._entities if e.name.lower() == entity.name.lower()), None)
            if existing:
                existing.level = entity.level
                existing.armour_class = entity.armour_class
                existing.attack_bonus = entity.attack_bonus
                existing.damage_die = entity.damage_die
                existing.hp = entity.hp
                existing.hp_max = entity.hp_max
                existing.kind = entity.kind
                existing.tags = list(entity.tags or [])
                existing.resistances = list(entity.resistances or [])
                updated += 1
                entity_id = existing.id
            else:
                entity.id = next_id
                next_id += 1
                self._entities.append(entity)
                created += 1
                entity_id = entity.id

            if location_id is not None:
                self._by_location.setdefault(location_id, [])
                if entity_id not in self._by_location[location_id]:
                    self._by_location[location_id].append(entity_id)
                    attached += 1

        return UpsertResult(created=created, updated=updated, attached=attached)

    def get_default_location_id(self) -> int | None:
        return next(iter(self._by_location.keys()), None)
