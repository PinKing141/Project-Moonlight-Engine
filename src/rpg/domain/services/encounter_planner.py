from __future__ import annotations

import random
from typing import Iterable, List, Optional, Sequence

from rpg.domain.models.encounter_definition import EncounterDefinition, EncounterSlot
from rpg.domain.models.entity import Entity
from rpg.domain.repositories import EntityRepository


class EncounterPlanner:
    """Deterministic encounter assembler driven by reusable definitions."""

    def __init__(self, entity_repo: EntityRepository) -> None:
        self.entity_repo = entity_repo

    def _load_entities(self, definitions: Sequence[EncounterDefinition]) -> dict[int, Entity]:
        ids: set[int] = set()
        for definition in definitions:
            for slot in definition.slots:
                ids.add(slot.entity_id)
        if not ids:
            return {}
        loaded = self.entity_repo.get_many(list(ids))
        return {entity.id: entity for entity in loaded}

    def _score_definition(
        self, definition: EncounterDefinition, player_level: int, faction_bias: Optional[str]
    ) -> float:
        base = definition.base_threat
        # Prefer definitions closer to the player level
        if player_level < definition.level_min:
            base *= 0.5
        elif player_level > definition.level_max:
            base *= 0.75
        else:
            base *= 1.25
        if faction_bias and definition.faction_id == faction_bias:
            base *= 1.3
        return max(base, 0.1)

    def _pick_definition(
        self,
        definitions: Sequence[EncounterDefinition],
        player_level: int,
        faction_bias: Optional[str],
        rng: random.Random,
    ) -> Optional[EncounterDefinition]:
        if not definitions:
            return None
        weights = [self._score_definition(defn, player_level, faction_bias) for defn in definitions]
        return rng.choices(list(definitions), weights=weights, k=1)[0]

    def _pick_count(self, slot: EncounterSlot, rng: random.Random) -> int:
        if slot.min_count >= slot.max_count:
            return max(1, slot.min_count)
        return rng.randint(slot.min_count, slot.max_count)

    def _assemble_for_definition(
        self,
        definition: EncounterDefinition,
        entity_lookup: dict[int, Entity],
        rng: random.Random,
        target_threat: float,
    ) -> List[Entity]:
        planned: list[Entity] = []
        budget = target_threat * 1.1  # small leeway to keep encounters varied
        slots: Iterable[EncounterSlot] = definition.weighted_slots() or definition.slots

        for slot in slots:
            entity = entity_lookup.get(slot.entity_id)
            if entity is None:
                continue

            count = self._pick_count(slot, rng)
            for _ in range(count):
                if planned:
                    accumulated_threat = sum(e.threat_rating for e in planned)
                    if accumulated_threat >= budget:
                        break
                planned.append(entity)

        if planned:
            return planned

        # Fallback: if everything was filtered out return at least one entity to avoid empty encounters
        entity = entity_lookup.get(definition.slots[0].entity_id) if definition.slots else None
        return [entity] if entity else []

    def plan_encounter(
        self,
        definitions: Sequence[EncounterDefinition],
        player_level: int,
        location_id: int,
        seed: int,
        faction_bias: Optional[str] = None,
        max_enemies: int = 3,
    ) -> tuple[Optional[EncounterDefinition], List[Entity]]:
        """Select a deterministic set of entities matching the provided constraints."""

        applicable = [
            definition
            for definition in definitions
            if definition.matches_level(player_level)
            and definition.applies_to_location(location_id)
        ]
        rng = random.Random(seed)

        if not applicable:
            return None, []

        entity_lookup = self._load_entities(applicable)
        chosen = self._pick_definition(applicable, player_level, faction_bias, rng)
        if not chosen:
            return None, []

        threat_budget = max(player_level * 7, 5)
        enemies = self._assemble_for_definition(chosen, entity_lookup, rng, threat_budget)
        return chosen, enemies[:max_enemies]
