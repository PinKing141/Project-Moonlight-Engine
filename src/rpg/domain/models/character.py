from dataclasses import dataclass, field
from enum import Enum
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
    class_levels: Dict[str, int] = field(default_factory=dict)
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
    alignment: str = "true_neutral"

    def __post_init__(self) -> None:
        flags = self.flags if isinstance(self.flags, dict) else {}
        if flags is not self.flags:
            self.flags = flags

        alignment_raw = str(self.alignment or "").strip().lower()
        if not alignment_raw:
            alignment_raw = str(flags.get("alignment", "") or "").strip().lower()
        normalized_alignment = CharacterAlignment.normalize(alignment_raw)
        self.alignment = normalized_alignment
        flags["alignment"] = normalized_alignment

        normalized: Dict[str, int] = {}

        if isinstance(self.class_levels, dict):
            for raw_slug, raw_level in self.class_levels.items():
                slug = str(raw_slug or "").strip().lower()
                if not slug:
                    continue
                try:
                    level_value = int(raw_level)
                except Exception:
                    continue
                if level_value <= 0:
                    continue
                normalized[slug] = normalized.get(slug, 0) + level_value

        if not normalized:
            stored = flags.get("class_levels")
            if isinstance(stored, dict):
                for raw_slug, raw_level in stored.items():
                    slug = str(raw_slug or "").strip().lower()
                    if not slug:
                        continue
                    try:
                        level_value = int(raw_level)
                    except Exception:
                        continue
                    if level_value <= 0:
                        continue
                    normalized[slug] = normalized.get(slug, 0) + level_value

        primary_slug = str(self.class_name or "").strip().lower()
        if not normalized and primary_slug:
            try:
                baseline_level = max(1, int(self.level or 1))
            except Exception:
                baseline_level = 1
            normalized[primary_slug] = baseline_level

        self.class_levels = normalized

        if not primary_slug and self.class_levels:
            self.class_name = max(self.class_levels.items(), key=lambda item: (int(item[1]), item[0]))[0]

        if self.class_levels:
            self.level = sum(int(value) for value in self.class_levels.values())
            flags["class_levels"] = dict(self.class_levels)


class CharacterAlignment(str, Enum):
    LAWFUL_GOOD = "lawful_good"
    NEUTRAL_GOOD = "neutral_good"
    CHAOTIC_GOOD = "chaotic_good"
    LAWFUL_NEUTRAL = "lawful_neutral"
    TRUE_NEUTRAL = "true_neutral"
    CHAOTIC_NEUTRAL = "chaotic_neutral"
    LAWFUL_EVIL = "lawful_evil"
    NEUTRAL_EVIL = "neutral_evil"
    CHAOTIC_EVIL = "chaotic_evil"

    @classmethod
    def normalize(cls, value: str | None) -> str:
        raw = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
        aliases = {
            "neutral": cls.TRUE_NEUTRAL.value,
            "good": cls.NEUTRAL_GOOD.value,
            "evil": cls.NEUTRAL_EVIL.value,
            "lawful": cls.LAWFUL_NEUTRAL.value,
            "chaotic": cls.CHAOTIC_NEUTRAL.value,
        }
        resolved = aliases.get(raw, raw)
        valid = {item.value for item in cls}
        return resolved if resolved in valid else cls.TRUE_NEUTRAL.value
