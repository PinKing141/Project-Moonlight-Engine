from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class EncounterSlot:
    """A single ingredient in an encounter definition."""

    entity_id: int
    monster_slug: Optional[str] = None
    min_count: int = 1
    max_count: int = 1
    weight: int = 1


@dataclass
class EncounterDefinition:
    """Blueprint describing how an encounter should be assembled."""

    id: str
    name: str
    level_min: int = 1
    level_max: int = 20
    faction_id: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    slots: List[EncounterSlot] = field(default_factory=list)
    base_threat: float = 1.0
    location_ids: List[int] = field(default_factory=list)

    def matches_level(self, level: int) -> bool:
        return self.level_min <= level <= self.level_max

    def applies_to_location(self, location_id: int) -> bool:
        return not self.location_ids or location_id in self.location_ids

    def weighted_slots(self) -> List[EncounterSlot]:
        expanded: list[EncounterSlot] = []
        for slot in self.slots:
            expanded.extend([slot] * max(slot.weight, 1))
        return expanded
