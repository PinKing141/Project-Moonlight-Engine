from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Any


def ability_modifier(score: int | None) -> int:
    try:
        return (int(score) - 10) // 2
    except Exception:
        return 0


@dataclass(frozen=True)
class AbilityScores:
    strength: int = 10
    dexterity: int = 10
    constitution: int = 10
    intelligence: int = 10
    wisdom: int = 10
    charisma: int = 10

    @property
    def strength_mod(self) -> int:
        return ability_modifier(self.strength)

    @property
    def dexterity_mod(self) -> int:
        return ability_modifier(self.dexterity)

    @property
    def constitution_mod(self) -> int:
        return ability_modifier(self.constitution)

    @property
    def intelligence_mod(self) -> int:
        return ability_modifier(self.intelligence)

    @property
    def wisdom_mod(self) -> int:
        return ability_modifier(self.wisdom)

    @property
    def charisma_mod(self) -> int:
        return ability_modifier(self.charisma)

    @property
    def initiative(self) -> int:
        return self.dexterity_mod


@dataclass(frozen=True)
class DerivedCombatStats:
    armour_class: int
    initiative: int
    speed: int


def ability_scores_from_mapping(attributes: Mapping[str, Any] | None) -> AbilityScores:
    attrs = attributes or {}

    def _score(primary: str, legacy: str | None = None) -> int:
        raw = attrs.get(primary)
        legacy_raw = attrs.get(legacy) if legacy is not None else None
        if raw is None and legacy is not None:
            raw = legacy_raw
        if raw is not None and legacy_raw is not None:
            try:
                primary_int = int(raw)
            except Exception:
                primary_int = 10
            try:
                legacy_int = int(legacy_raw)
            except Exception:
                legacy_int = 10
            if primary_int == 10 and legacy_int > 1:
                raw = legacy_raw
        try:
            return int(raw) if raw is not None else 10
        except Exception:
            return 10

    return AbilityScores(
        strength=_score("strength", "might"),
        dexterity=_score("dexterity", "agility"),
        constitution=_score("constitution"),
        intelligence=_score("intelligence", "wit"),
        wisdom=_score("wisdom"),
        charisma=_score("charisma", "spirit"),
    )


def derive_combat_stats(*, scores: AbilityScores, base_armour_class: int = 10, armour_bonus: int = 0, speed: int = 30) -> DerivedCombatStats:
    armour_class = max(int(base_armour_class) + int(armour_bonus) + scores.dexterity_mod, 10)
    return DerivedCombatStats(
        armour_class=armour_class,
        initiative=scores.initiative,
        speed=max(int(speed), 0),
    )


@dataclass
class CombatStats:
    """Immutable container describing combat-relevant stats.

    Combat numbers are frequently sprinkled across entities and characters. This
    wrapper keeps them in one place and provides a cheap "threat" heuristic for
    encounter planning without coupling to any particular RNG implementation.
    """

    hp: int
    attack_min: int
    attack_max: int
    armor: int = 0
    armour_class: int = 10
    attack_bonus: int = 0
    damage_die: str = "d4"
    speed: int = 30
    tags: list[str] = field(default_factory=list)

    @property
    def threat_rating(self) -> float:
        """Return a lightweight danger score used by encounter planners.

        The formula intentionally favours survivability slightly more than burst
        damage so that "tanky" enemies don't overwhelm low-level parties.
        """

        avg_damage = (self.attack_min + self.attack_max) / 2
        mitigation = self.armor + (self.armour_class - 10) * 0.2
        return max(self.hp / 2 + avg_damage + mitigation + self.attack_bonus * 0.5, 1.0)

    def with_bonus(self, hp_bonus: int = 0, damage_bonus: int = 0) -> "CombatStats":
        """Return a shallow copy with additional bonuses applied."""

        return CombatStats(
            hp=self.hp + hp_bonus,
            attack_min=self.attack_min + damage_bonus,
            attack_max=self.attack_max + damage_bonus,
            armor=self.armor,
            armour_class=self.armour_class,
            attack_bonus=self.attack_bonus,
            damage_die=self.damage_die,
            speed=self.speed,
            tags=list(self.tags),
        )
