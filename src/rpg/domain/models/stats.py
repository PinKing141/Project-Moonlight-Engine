from __future__ import annotations

from dataclasses import dataclass, field


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
