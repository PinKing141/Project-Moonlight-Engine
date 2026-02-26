from dataclasses import dataclass, field
from typing import List, Optional


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
    biome: str = "wilderness"
    base_level: int = 1
    recommended_level: int = 1
    factions: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    encounters: List[EncounterTableEntry] = field(default_factory=list)
