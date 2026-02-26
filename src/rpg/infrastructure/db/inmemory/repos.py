from typing import Dict, List, Optional

from rpg.domain.models.character import Character
from rpg.domain.models.character_class import CharacterClass
from rpg.domain.models.entity import Entity
from rpg.domain.models.location import Location
from rpg.domain.models.world import World
from rpg.domain.repositories import (
    CharacterRepository,
    ClassRepository,
    EntityRepository,
    LocationRepository,
    WorldRepository,
)


class InMemoryWorldRepository(WorldRepository):
    _WORLD_HISTORY_MAX = 500

    def __init__(self, seed: int = 1) -> None:
        self._world = World(id=1, name="Default World", rng_seed=seed)
        self._world_flags: dict[str, str] = {}
        self._world_history: list[dict[str, object]] = []

    def load_default(self) -> Optional[World]:
        if not isinstance(getattr(self._world, "flags", None), dict):
            self._world.flags = {}
        self._world.flags["world_flags"] = dict(self._world_flags)
        return self._world

    def save(self, world: World) -> None:
        if isinstance(getattr(world, "flags", None), dict):
            stored = world.flags.get("world_flags")
            if isinstance(stored, dict):
                self._world_flags = {str(key): str(value) for key, value in stored.items()}
        self._world = world

    def list_world_flags(self, world_id: int | None = None) -> dict[str, str]:
        _ = world_id
        return dict(self._world_flags)

    def set_world_flag(
        self,
        *,
        world_id: int,
        flag_key: str,
        flag_value: str | None,
        changed_turn: int,
        reason: str,
    ) -> None:
        _ = world_id
        previous = self._world_flags.get(str(flag_key))
        if flag_value is None:
            self._world_flags.pop(str(flag_key), None)
        else:
            self._world_flags[str(flag_key)] = str(flag_value)
        self._world_history.append(
            {
                "flag_key": str(flag_key),
                "old_value": previous,
                "new_value": None if flag_value is None else str(flag_value),
                "changed_turn": int(changed_turn),
                "reason": str(reason),
            }
        )
        if len(self._world_history) > self._WORLD_HISTORY_MAX:
            del self._world_history[:-self._WORLD_HISTORY_MAX]

    def build_set_world_flag_operation(
        self,
        *,
        world_id: int,
        flag_key: str,
        flag_value: str | None,
        changed_turn: int,
        reason: str,
    ):
        def _operation(_session: object) -> None:
            self.set_world_flag(
                world_id=world_id,
                flag_key=flag_key,
                flag_value=flag_value,
                changed_turn=changed_turn,
                reason=reason,
            )

        return _operation


class InMemoryCharacterRepository(CharacterRepository):
    _PROGRESSION_UNLOCKS_MAX = 500

    def __init__(self, initial: Dict[int, Character]) -> None:
        self._characters = dict(initial)
        self._progression_unlocks: list[dict[str, object]] = []

    def get(self, character_id: int) -> Character | None:
        return self._characters.get(character_id)

    def list_all(self) -> List[Character]:
        return list(self._characters.values())

    def save(self, character: Character) -> None:
        self._characters[character.id] = character

    def find_by_location(self, location_id: int) -> List[Character]:
        return [c for c in self._characters.values() if c.location_id == location_id]

    def create(self, character: Character, location_id: int) -> Character:
        next_id = max(self._characters.keys(), default=0) + 1
        character.id = next_id
        character.location_id = location_id
        self._characters[next_id] = character
        return character

    def list_progression_unlocks(self, character_id: int) -> list[dict[str, object]]:
        return [
            dict(row)
            for row in self._progression_unlocks
            if int(row.get("character_id", 0)) == int(character_id)
        ]

    def record_progression_unlock(
        self,
        *,
        character_id: int,
        unlock_kind: str,
        unlock_key: str,
        unlocked_level: int,
        created_turn: int,
    ) -> None:
        key = str(unlock_key)
        kind = str(unlock_kind)
        existing = next(
            (
                row
                for row in self._progression_unlocks
                if int(row.get("character_id", 0)) == int(character_id)
                and str(row.get("unlock_kind", "")) == kind
                and str(row.get("unlock_key", "")) == key
            ),
            None,
        )
        if existing is not None:
            existing["unlocked_level"] = int(unlocked_level)
            existing["created_turn"] = int(created_turn)
            return
        self._progression_unlocks.append(
            {
                "character_id": int(character_id),
                "unlock_kind": kind,
                "unlock_key": key,
                "unlocked_level": int(unlocked_level),
                "created_turn": int(created_turn),
            }
        )
        if len(self._progression_unlocks) > self._PROGRESSION_UNLOCKS_MAX:
            del self._progression_unlocks[:-self._PROGRESSION_UNLOCKS_MAX]

    def build_progression_unlock_operation(
        self,
        *,
        character_id: int,
        unlock_kind: str,
        unlock_key: str,
        unlocked_level: int,
        created_turn: int,
    ):
        def _operation(_session: object) -> None:
            self.record_progression_unlock(
                character_id=character_id,
                unlock_kind=unlock_kind,
                unlock_key=unlock_key,
                unlocked_level=unlocked_level,
                created_turn=created_turn,
            )

        return _operation


class InMemoryEntityRepository(EntityRepository):
    def __init__(self, entities: List[Entity]) -> None:
        self._entities = list(entities)
        self._by_location: Dict[int, List[int]] = {}

    def get(self, entity_id: int) -> Entity | None:
        for entity in self._entities:
            if entity.id == entity_id:
                return entity
        return None

    def get_many(self, entity_ids: List[int]) -> List[Entity]:
        if not entity_ids:
            return []
        ids = set(entity_ids)
        return [e for e in self._entities if e.id in ids]

    def list_for_level(self, target_level: int, tolerance: int = 2) -> List[Entity]:
        lower = target_level - tolerance
        upper = target_level + tolerance
        return [e for e in self._entities if lower <= e.level <= upper]

    def list_by_location(self, location_id: int) -> List[Entity]:
        ids = self._by_location.get(location_id, [])
        return [e for e in self._entities if e.id in ids]

    def set_location_entities(self, location_id: int, entity_ids: List[int]) -> None:
        self._by_location[location_id] = entity_ids

    def list_by_level_band(self, level_min: int, level_max: int) -> List[Entity]:
        return [e for e in self._entities if level_min <= e.level <= level_max]


class InMemoryLocationRepository(LocationRepository):
    def __init__(self, locations: Dict[int, Location]) -> None:
        self._locations = dict(locations)

    def get(self, location_id: int) -> Location | None:
        return self._locations.get(location_id)

    def list_all(self) -> List[Location]:
        return list(self._locations.values())

    def get_starting_location(self) -> Optional[Location]:
        if not self._locations:
            return None
        first_id = sorted(self._locations.keys())[0]
        return self._locations[first_id]


class InMemoryClassRepository(ClassRepository):
    def __init__(self, classes: List[CharacterClass]) -> None:
        self._classes = list(classes)

    def list_playable(self) -> List[CharacterClass]:
        return sorted(self._classes, key=lambda cls: cls.name.lower())

    def get_by_slug(self, slug: str) -> Optional[CharacterClass]:
        slug_key = slug.lower().strip()
        for cls in self._classes:
            if cls.slug.lower() == slug_key:
                return cls
        return None
