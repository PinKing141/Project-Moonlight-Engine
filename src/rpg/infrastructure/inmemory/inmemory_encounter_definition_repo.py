from __future__ import annotations

from typing import List

from rpg.domain.models.encounter_definition import EncounterDefinition, EncounterSlot
from rpg.domain.repositories import EncounterDefinitionRepository


class InMemoryEncounterDefinitionRepository(EncounterDefinitionRepository):
    def __init__(self) -> None:
        self._definitions: List[EncounterDefinition] = [
            EncounterDefinition(
                id="forest_patrol_table",
                name="Forest Patrol Table",
                level_min=1,
                level_max=4,
                faction_id="the_crown",
                base_threat=1.15,
                location_ids=[1],
                slots=[
                    EncounterSlot(entity_id=1, monster_slug="goblin", min_count=1, max_count=2, weight=3),
                    EncounterSlot(entity_id=2, monster_slug="wolf", min_count=1, max_count=2, weight=2),
                ],
                tags=["forest", "patrol"],
            ),
            EncounterDefinition(
                id="ruins_ambush_table",
                name="Ruins Ambush Table",
                level_min=2,
                level_max=6,
                faction_id="thieves_guild",
                base_threat=1.25,
                location_ids=[2],
                slots=[
                    EncounterSlot(entity_id=1, monster_slug="bandit", min_count=1, max_count=3, weight=3),
                    EncounterSlot(entity_id=3, monster_slug="skeleton", min_count=1, max_count=2, weight=2),
                ],
                tags=["ruins", "ambush"],
            ),
            EncounterDefinition(
                id="caves_depths_table",
                name="Caves Depths Table",
                level_min=3,
                level_max=8,
                faction_id="arcane_syndicate",
                base_threat=1.35,
                location_ids=[3],
                slots=[
                    EncounterSlot(entity_id=2, monster_slug="giant_rat", min_count=1, max_count=3, weight=2),
                    EncounterSlot(entity_id=3, monster_slug="ghoul", min_count=1, max_count=2, weight=3),
                ],
                tags=["caves", "depths"],
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
