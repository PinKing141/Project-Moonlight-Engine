from __future__ import annotations

from typing import List

from rpg.domain.models.encounter_definition import EncounterDefinition, EncounterSlot
from rpg.domain.repositories import EncounterDefinitionRepository


class InMemoryEncounterDefinitionRepository(EncounterDefinitionRepository):
    def __init__(self) -> None:
        self._definitions: List[EncounterDefinition] = [
            EncounterDefinition(
                id="goblin_scouts",
                name="Goblin Scouts",
                level_min=1,
                level_max=3,
                faction_id="wild",
                base_threat=1.2,
                location_ids=[1],
                slots=[EncounterSlot(entity_id=1, min_count=1, max_count=2, weight=2)],
                tags=["humanoid", "skirmish"],
            ),
            EncounterDefinition(
                id="wolf_pack",
                name="Wolf Pack",
                level_min=1,
                level_max=4,
                faction_id="wild",
                base_threat=1.1,
                location_ids=[1],
                slots=[EncounterSlot(entity_id=2, min_count=1, max_count=3, weight=3)],
                tags=["beast"],
            ),
            EncounterDefinition(
                id="restless_dead",
                name="Restless Dead",
                level_min=2,
                level_max=6,
                faction_id="undead",
                base_threat=1.4,
                location_ids=[],
                slots=[EncounterSlot(entity_id=3, min_count=1, max_count=2, weight=2)],
                tags=["undead"],
            ),
        ]

    def list_for_location(self, location_id: int) -> List[EncounterDefinition]:
        return [
            definition
            for definition in self._definitions
            if definition.applies_to_location(location_id)
        ]

    def list_global(self) -> List[EncounterDefinition]:
        return list(self._definitions)
