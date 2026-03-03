from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Mapping

from rpg.application.services.seed_policy import derive_seed


@dataclass(frozen=True)
class CheckResolutionOutcome:
    seed: int
    dc: int
    modifier: int
    flat_bonus: int
    roll_mode: str
    rolls: tuple[int, ...]
    selected_roll: int
    total: int
    success: bool
    margin: int
    difficulty_tier: str
    consequence_tag: str


class CheckResolutionService:
    def resolve(
        self,
        *,
        namespace: str,
        context: Mapping[str, Any],
        dc: int,
        modifier: int = 0,
        flat_bonus: int = 0,
        advantage: bool = False,
        disadvantage: bool = False,
        min_dc: int = 5,
        max_dc: int = 30,
    ) -> CheckResolutionOutcome:
        clamped_dc = max(int(min_dc), min(int(max_dc), int(dc)))
        seed = derive_seed(namespace=namespace, context=context)
        rng = random.Random(seed)

        adv_only = bool(advantage) and not bool(disadvantage)
        dis_only = bool(disadvantage) and not bool(advantage)
        if adv_only:
            first = rng.randint(1, 20)
            second = rng.randint(1, 20)
            selected = max(first, second)
            rolls = (first, second)
            roll_mode = "advantage"
        elif dis_only:
            first = rng.randint(1, 20)
            second = rng.randint(1, 20)
            selected = min(first, second)
            rolls = (first, second)
            roll_mode = "disadvantage"
        else:
            selected = rng.randint(1, 20)
            rolls = (selected,)
            roll_mode = "normal"

        resolved_modifier = int(modifier)
        resolved_bonus = int(flat_bonus)
        total = int(selected + resolved_modifier + resolved_bonus)
        success = bool(total >= clamped_dc)
        margin = int(total - clamped_dc)
        return CheckResolutionOutcome(
            seed=seed,
            dc=clamped_dc,
            modifier=resolved_modifier,
            flat_bonus=resolved_bonus,
            roll_mode=roll_mode,
            rolls=rolls,
            selected_roll=int(selected),
            total=total,
            success=success,
            margin=margin,
            difficulty_tier=self._difficulty_tier(clamped_dc),
            consequence_tag=self._consequence_tag(margin),
        )

    @staticmethod
    def _difficulty_tier(dc: int) -> str:
        value = int(dc)
        if value <= 8:
            return "trivial"
        if value <= 11:
            return "easy"
        if value <= 14:
            return "moderate"
        if value <= 17:
            return "hard"
        if value <= 20:
            return "very_hard"
        return "extreme"

    @staticmethod
    def _consequence_tag(margin: int) -> str:
        value = int(margin)
        if value >= 5:
            return "strong_success"
        if value >= 0:
            return "success"
        if value >= -2:
            return "near_miss"
        if value <= -5:
            return "major_failure"
        return "failure"
