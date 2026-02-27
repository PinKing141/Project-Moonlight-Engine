from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class Race:
    name: str
    bonuses: Dict[str, int] = field(default_factory=dict)
    speed: int = 30
    traits: List[str] = field(default_factory=list)
    playable: bool = True


@dataclass(frozen=True)
class Subrace:
    name: str
    parent_race: str
    bonuses: Dict[str, int] = field(default_factory=dict)
    speed_bonus: int = 0
    traits: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class Background:
    name: str
    proficiencies: List[str] = field(default_factory=list)
    feature: Optional[str] = None
    faction: Optional[str] = None
    contacts: List[str] = field(default_factory=list)
    starting_money: int = 0


@dataclass(frozen=True)
class DifficultyPreset:
    slug: str
    name: str
    description: str = ""
    hp_multiplier: float = 1.0
    outgoing_damage_multiplier: float = 1.0
    incoming_damage_multiplier: float = 1.0
    threat_modifier: float = 1.0
