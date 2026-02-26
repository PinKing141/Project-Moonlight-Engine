from dataclasses import dataclass, field
from typing import List, Optional

from rpg.domain.models.stats import CombatStats


@dataclass
class Entity:
    id: int
    name: str
    level: int
    hp: int = 6
    hp_current: int = 0
    hp_max: int = 0
    armour_class: int = 10
    attack_bonus: int = 2
    damage_die: str = "d4"
    attack_min: int = 1
    attack_max: int = 3
    armor: int = 0
    faction_id: Optional[str] = None
    kind: str = "beast"
    tags: List[str] = field(default_factory=list)
    traits: List[str] = field(default_factory=list)
    loot_tags: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.hp_max <= 0:
            self.hp_max = self.hp
        if self.hp_current <= 0:
            self.hp_current = self.hp_max

    @property
    def combat_stats(self) -> CombatStats:
        """Return a reusable combat stats wrapper for the entity."""

        return CombatStats(
            hp=self.hp,
            attack_min=self.attack_min,
            attack_max=self.attack_max,
            armor=self.armor,
            armour_class=self.armour_class,
            attack_bonus=self.attack_bonus,
            damage_die=self.damage_die,
            tags=list(self.tags),
        )

    @property
    def threat_rating(self) -> float:
        """Expose the combat threat rating for encounter planning."""

        return self.combat_stats.threat_rating
