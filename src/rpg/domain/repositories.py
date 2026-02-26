from abc import ABC, abstractmethod
from typing import List, Optional

from rpg.domain.models.character import Character
from rpg.domain.models.entity import Entity
from rpg.domain.models.faction import Faction
from rpg.domain.models.encounter_definition import EncounterDefinition
from rpg.domain.models.location import Location
from rpg.domain.models.quest import QuestState, QuestTemplate
from rpg.domain.models.spell import Spell
from rpg.domain.models.feature import Feature
from rpg.domain.models.world import World
from rpg.domain.models.character_class import CharacterClass


class CharacterRepository(ABC):
    @abstractmethod
    def get(self, character_id: int) -> Optional[Character]:
        raise NotImplementedError

    @abstractmethod
    def list_all(self) -> List[Character]:
        raise NotImplementedError

    @abstractmethod
    def save(self, character: Character) -> None:
        raise NotImplementedError

    @abstractmethod
    def find_by_location(self, location_id: int) -> List[Character]:
        raise NotImplementedError

    @abstractmethod
    def create(self, character: Character, location_id: int) -> Character:
        raise NotImplementedError


class WorldRepository(ABC):
    @abstractmethod
    def load_default(self) -> Optional[World]:
        raise NotImplementedError

    @abstractmethod
    def save(self, world: World) -> None:
        raise NotImplementedError

    def get_default(self) -> Optional[World]:
        """Convenience alias for load_default to align with UI expectations."""
        return self.load_default()


class EntityRepository(ABC):
    @abstractmethod
    def get(self, entity_id: int) -> Optional[Entity]:
        raise NotImplementedError

    @abstractmethod
    def get_many(self, entity_ids: List[int]) -> List[Entity]:
        raise NotImplementedError

    @abstractmethod
    def list_for_level(self, target_level: int, tolerance: int = 2) -> List[Entity]:
        raise NotImplementedError

    @abstractmethod
    def list_by_location(self, location_id: int) -> List[Entity]:
        raise NotImplementedError

    def list_by_level_band(self, level_min: int, level_max: int) -> List[Entity]:
        """Optional helper; default falls back to list_for_level with midpoint."""
        target = (level_min + level_max) // 2
        tolerance = max(level_max - target, 0)
        return self.list_for_level(target_level=target, tolerance=tolerance)


class LocationRepository(ABC):
    @abstractmethod
    def get(self, location_id: int) -> Optional[Location]:
        raise NotImplementedError

    @abstractmethod
    def list_all(self) -> List[Location]:
        raise NotImplementedError

    @abstractmethod
    def get_starting_location(self) -> Optional[Location]:
        raise NotImplementedError


class ClassRepository(ABC):
    @abstractmethod
    def list_playable(self) -> List[CharacterClass]:
        raise NotImplementedError


class EncounterDefinitionRepository(ABC):
    @abstractmethod
    def list_for_location(self, location_id: int) -> List[EncounterDefinition]:
        raise NotImplementedError

    def list_global(self) -> List[EncounterDefinition]:
        return []


class FactionRepository(ABC):
    @abstractmethod
    def get(self, faction_id: str) -> Optional[Faction]:
        raise NotImplementedError

    @abstractmethod
    def list_all(self) -> List[Faction]:
        raise NotImplementedError

    @abstractmethod
    def save(self, faction: Faction) -> None:
        raise NotImplementedError


class SpellRepository(ABC):
    @abstractmethod
    def get_by_slug(self, slug: str) -> Optional[Spell]:
        raise NotImplementedError

    @abstractmethod
    def list_by_class(self, class_slug: str, max_level: int):
        raise NotImplementedError


class FeatureRepository(ABC):
    @abstractmethod
    def list_for_character(self, character_id: int) -> List[Feature]:
        raise NotImplementedError

    @abstractmethod
    def grant_feature_by_slug(self, character_id: int, feature_slug: str) -> bool:
        raise NotImplementedError


class CharacterReputationRepository(ABC):
    @abstractmethod
    def get_reputation(self, *, character_id: int, faction_id: str) -> int:
        raise NotImplementedError

    @abstractmethod
    def set_reputation(
        self,
        *,
        character_id: int,
        faction_id: str,
        new_score: int,
        changed_turn: int,
        reason: str,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_for_character(self, *, character_id: int) -> dict[str, int]:
        raise NotImplementedError


class QuestStateRepository(ABC):
    @abstractmethod
    def list_definitions(self) -> List[QuestTemplate]:
        raise NotImplementedError

    @abstractmethod
    def list_active_for_character(self, *, character_id: int) -> List[QuestState]:
        raise NotImplementedError

    @abstractmethod
    def save_active(
        self,
        *,
        character_id: int,
        state: QuestState,
        target_count: int,
        seed_key: str,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def append_history(
        self,
        *,
        character_id: int,
        template_slug: str,
        action: str,
        action_turn: int,
        payload_json: str,
    ) -> None:
        raise NotImplementedError


class LocationStateRepository(ABC):
    @abstractmethod
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
        raise NotImplementedError
