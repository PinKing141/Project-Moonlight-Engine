from __future__ import annotations

import random
from typing import Callable, Optional

from rpg.application.dtos import EncounterPlan
from rpg.application.services.seed_policy import derive_seed
from rpg.domain.models.entity import Entity
from rpg.domain.repositories import (
    EncounterDefinitionRepository,
    EntityRepository,
    FactionRepository,
)
from rpg.domain.services.encounter_planner import EncounterPlanner


class EncounterService:
    def __init__(
        self,
        entity_repo: EntityRepository,
        definition_repo: EncounterDefinitionRepository | None = None,
        faction_repo: FactionRepository | None = None,
        rng_factory: Callable[[int], random.Random] | None = None,
    ) -> None:
        self.entity_repo = entity_repo
        self.definition_repo = definition_repo
        self.faction_repo = faction_repo
        self.planner = EncounterPlanner(entity_repo)
        self.rng_factory = rng_factory or (lambda seed: random.Random(seed))

    def _weighted_pick(
        self,
        pool: list[Entity],
        count: int,
        faction_bias: str | None,
        rng: random.Random,
    ) -> list[Entity]:
        if not pool:
            return []
        if count <= 1:
            if faction_bias:
                weights = [2 if entity.faction_id == faction_bias else 1 for entity in pool]
                return [rng.choices(pool, weights=weights, k=1)[0]]
            return [rng.choice(pool)]

        remaining = list(pool)
        picks: list[Entity] = []
        for _ in range(count):
            if not remaining:
                break
            if faction_bias:
                weights = [2 if entity.faction_id == faction_bias else 1 for entity in remaining]
                chosen = rng.choices(remaining, weights=weights, k=1)[0]
            else:
                chosen = rng.choice(remaining)
            picks.append(chosen)
            remaining = [entity for entity in remaining if entity.id != chosen.id]
        return picks

    def generate_plan(
        self,
        location_id: int,
        player_level: int,
        world_turn: int,
        faction_bias: str | None = None,
        max_enemies: int = 1,
    ) -> EncounterPlan:
        """Return a deterministic encounter plan for the given context."""

        seed = derive_seed(
            namespace="encounter.plan",
            context={
                "location_id": location_id,
                "player_level": player_level,
                "world_turn": world_turn,
                "faction_bias": faction_bias,
                "max_enemies": max_enemies,
            },
        )
        rng = self.rng_factory(seed)

        if self.definition_repo:
            definitions = self.definition_repo.list_for_location(location_id)
            if not definitions:
                definitions = self.definition_repo.list_global()
            chosen, enemies = self.planner.plan_encounter(
                definitions=definitions,
                player_level=player_level,
                location_id=location_id,
                seed=seed,
                faction_bias=faction_bias,
                max_enemies=max_enemies,
            )
            if enemies:
                return EncounterPlan(
                    enemies=enemies,
                    definition_id=chosen.id if chosen else None,
                    faction_bias=faction_bias,
                    source="definition",
                )

        by_location = self.entity_repo.list_by_location(location_id)
        if by_location:
            count = min(max(1, max_enemies), len(by_location))
            enemies = self._weighted_pick(by_location, count, faction_bias, rng)
            return EncounterPlan(enemies=enemies, faction_bias=faction_bias, source="location")

        level_min = max(1, player_level - 1)
        level_max = player_level + 2
        candidates = getattr(self.entity_repo, "list_by_level_band", None)
        if callable(candidates):
            band = self.entity_repo.list_by_level_band(level_min, level_max)
        else:
            mid = (level_min + level_max) // 2
            band = self.entity_repo.list_for_level(mid, tolerance=level_max - mid)

        if not band:
            return EncounterPlan(enemies=[], faction_bias=faction_bias, source="empty")

        count = min(max(1, max_enemies), len(band))
        enemies = self._weighted_pick(band, count, faction_bias, rng)
        return EncounterPlan(enemies=enemies, faction_bias=faction_bias, source="level-band")

    def generate(
        self,
        location_id: int,
        player_level: int,
        world_turn: int,
        faction_bias: str | None = None,
        max_enemies: int = 1,
    ) -> list[Entity]:
        """Return a small list of entities for an encounter, deterministic per turn."""

        return self.generate_plan(
            location_id=location_id,
            player_level=player_level,
            world_turn=world_turn,
            faction_bias=faction_bias,
            max_enemies=max_enemies,
        ).enemies

    def find_encounter(self, location_id: int, character_level: int) -> Optional[Entity]:
        """Legacy helper for callers; wraps generate using a deterministic world_turn of 0."""
        generated = self.generate(location_id, character_level, world_turn=0, max_enemies=1)
        if not generated:
            return None

        return generated[0]
