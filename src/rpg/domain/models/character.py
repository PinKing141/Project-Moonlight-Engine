from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


DEFAULT_ATTRIBUTES: Dict[str, int] = {
    "strength": 10,
    "constitution": 10,
    "dexterity": 10,
    "intelligence": 10,
    "wisdom": 10,
    "charisma": 10,
    "might": 1,
    "agility": 1,
    "wit": 1,
    "spirit": 1,
}


@dataclass
class Character:
    id: Optional[int]
    name: str
    level: int = 1
    xp: int = 0
    money: int = 0
    hp_max: int = 10
    hp_current: int = 10
    class_name: Optional[str] = None
    base_attributes: Dict[str, int] = field(default_factory=dict)
    location_id: Optional[int] = None
    attack_min: int = 2
    attack_max: int = 4
    attack_bonus: int = 2
    damage_die: str = "d6"
    armour_class: int = 10
    armor: int = 0
    alive: bool = True
    character_type_id: int = 1
    attributes: Dict[str, int] = field(default_factory=lambda: dict(DEFAULT_ATTRIBUTES))
    faction_id: Optional[str] = None
    inventory: List[str] = field(default_factory=list)
    race: Optional[str] = None
    race_traits: List[str] = field(default_factory=list)
    speed: int = 30
    background: Optional[str] = None
    background_features: List[str] = field(default_factory=list)
    proficiencies: List[str] = field(default_factory=list)
    difficulty: str = "normal"
    flags: Dict[str, Any] = field(default_factory=dict)
    incoming_damage_multiplier: float = 1.0
    outgoing_damage_multiplier: float = 1.0
    spell_slots_max: int = 0
    spell_slots_current: int = 0
    cantrips: List[str] = field(default_factory=list)
    known_spells: List[str] = field(default_factory=list)
