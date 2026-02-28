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
    condition_effects: tuple["ConditionEffect", ...] = ()


@dataclass(frozen=True)
class ConditionEffect:
    status_id: str
    rounds: int = 1
    potency: int = 1
    target: str = "target"


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
        if handler is None and key.startswith("condition_"):
            return _condition_handler(feature, context)
        if handler is None and key.startswith("condition_self_"):
            return _condition_self_handler(feature, context)
        if handler is None and key.startswith("condition_target_"):
            return _condition_target_handler(feature, context)
        if handler is None:
            return FeatureEffectOutcome()
        return handler(feature, context)


def _bonus_damage_handler(feature: Feature, _context: FeatureEffectContext) -> FeatureEffectOutcome:
    return FeatureEffectOutcome(bonus_damage=int(feature.effect_value or 0))


def _initiative_bonus_handler(feature: Feature, _context: FeatureEffectContext) -> FeatureEffectOutcome:
    return FeatureEffectOutcome(initiative_bonus=int(feature.effect_value or 0))


def _attack_bonus_handler(feature: Feature, _context: FeatureEffectContext) -> FeatureEffectOutcome:
    return FeatureEffectOutcome(attack_bonus=int(feature.effect_value or 0))


def _condition_outcome(*, feature: Feature, prefix: str, target: str) -> FeatureEffectOutcome:
    key = str(feature.effect_kind or "").strip().lower()
    status_id = key[len(prefix) :].strip().lower()
    if not status_id:
        return FeatureEffectOutcome()
    rounds = max(1, int(feature.effect_value or 1))
    return FeatureEffectOutcome(
        condition_effects=(
            ConditionEffect(
                status_id=status_id,
                rounds=rounds,
                potency=1,
                target=target,
            ),
        )
    )


def _condition_handler(feature: Feature, _context: FeatureEffectContext) -> FeatureEffectOutcome:
    return _condition_outcome(feature=feature, prefix="condition_", target="target")


def _condition_self_handler(feature: Feature, _context: FeatureEffectContext) -> FeatureEffectOutcome:
    return _condition_outcome(feature=feature, prefix="condition_self_", target="self")


def _condition_target_handler(feature: Feature, _context: FeatureEffectContext) -> FeatureEffectOutcome:
    return _condition_outcome(feature=feature, prefix="condition_target_", target="target")


def default_feature_effect_registry() -> FeatureEffectRegistry:
    registry = FeatureEffectRegistry()
    registry.register("bonus_damage", _bonus_damage_handler)
    registry.register("initiative_bonus", _initiative_bonus_handler)
    registry.register("attack_bonus", _attack_bonus_handler)
    registry.register("condition_blinded", _condition_handler)
    registry.register("condition_paralysed", _condition_handler)
    registry.register("condition_restrained", _condition_handler)
    registry.register("condition_exhaustion", _condition_handler)
    registry.register("condition_self_blinded", _condition_self_handler)
    registry.register("condition_self_paralysed", _condition_self_handler)
    registry.register("condition_self_restrained", _condition_self_handler)
    registry.register("condition_self_exhaustion", _condition_self_handler)
    return registry
