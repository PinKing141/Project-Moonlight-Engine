from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class Biome(str, Enum):
    WILDERNESS = "wilderness"
    TUNDRA = "tundra"
    DESERT = "desert"
    SWAMP = "swamp"
    FOREST = "forest"
    MOUNTAIN = "mountain"
    COAST = "coast"


@dataclass(frozen=True)
class HazardProfile:
    key: str = "standard"
    severity: int = 1
    environmental_flags: List[str] = field(default_factory=list)


@dataclass
class EncounterTableEntry:
    entity_id: int
    weight: int = 1
    min_level: int = 1
    max_level: int = 20
    tags: List[str] = field(default_factory=list)
    faction_bias: Optional[str] = None


@dataclass
class Location:
    id: int
    name: str
    biome: Biome | str = Biome.WILDERNESS.value
    base_level: int = 1
    recommended_level: int = 1
    factions: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    encounters: List[EncounterTableEntry] = field(default_factory=list)
    hazard_profile: HazardProfile = field(default_factory=HazardProfile)
