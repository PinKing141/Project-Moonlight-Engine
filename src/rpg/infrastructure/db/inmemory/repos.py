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
    def __init__(self, seed: int = 1) -> None:
        self._world = World(id=1, name="Default World", rng_seed=seed)

    def load_default(self) -> Optional[World]:
        return self._world

    def save(self, world: World) -> None:
        self._world = world


class InMemoryCharacterRepository(CharacterRepository):
    def __init__(self, initial: Dict[int, Character]) -> None:
        self._characters = dict(initial)

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
