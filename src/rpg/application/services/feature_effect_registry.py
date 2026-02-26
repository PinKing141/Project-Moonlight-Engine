from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict

from rpg.domain.models.feature import Feature


@dataclass(frozen=True)
class FeatureEffectContext:
    trigger_key: str
    round_number: int
    is_crit: bool = False


@dataclass(frozen=True)
class FeatureEffectOutcome:
    initiative_bonus: int = 0
    attack_bonus: int = 0
    bonus_damage: int = 0


FeatureEffectHandler = Callable[[Feature, FeatureEffectContext], FeatureEffectOutcome]


class FeatureEffectRegistry:
    def __init__(self) -> None:
        self._handlers: Dict[str, FeatureEffectHandler] = {}

    def register(self, effect_kind: str, handler: FeatureEffectHandler) -> None:
        key = str(effect_kind or "").strip().lower()
        if not key:
            return
        self._handlers[key] = handler

    def apply(self, feature: Feature, context: FeatureEffectContext) -> FeatureEffectOutcome:
        key = str(feature.effect_kind or "").strip().lower()
        handler = self._handlers.get(key)
        if handler is None:
            return FeatureEffectOutcome()
        return handler(feature, context)


def _bonus_damage_handler(feature: Feature, _context: FeatureEffectContext) -> FeatureEffectOutcome:
    return FeatureEffectOutcome(bonus_damage=int(feature.effect_value or 0))


def _initiative_bonus_handler(feature: Feature, _context: FeatureEffectContext) -> FeatureEffectOutcome:
    return FeatureEffectOutcome(initiative_bonus=int(feature.effect_value or 0))


def _attack_bonus_handler(feature: Feature, _context: FeatureEffectContext) -> FeatureEffectOutcome:
    return FeatureEffectOutcome(attack_bonus=int(feature.effect_value or 0))


def default_feature_effect_registry() -> FeatureEffectRegistry:
    registry = FeatureEffectRegistry()
    registry.register("bonus_damage", _bonus_damage_handler)
    registry.register("initiative_bonus", _initiative_bonus_handler)
    registry.register("attack_bonus", _attack_bonus_handler)
    return registry
