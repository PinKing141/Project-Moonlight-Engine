from typing import Dict, Optional

from rpg.domain.models.character import Character, DEFAULT_ATTRIBUTES
from rpg.domain.models.character_class import CharacterClass
from rpg.domain.models.character_options import Background, DifficultyPreset, Race
from rpg.domain.services.class_profiles import CLASS_COMBAT_PROFILE, DEFAULT_COMBAT_PROFILE


HIT_DIE_BASE_HP = {
    "d6": 6,
    "d8": 8,
    "d10": 10,
    "d12": 12,
}


ABILITY_ALIASES = {
    "str": "strength",
    "dex": "dexterity",
    "con": "constitution",
    "int": "intelligence",
    "wis": "wisdom",
    "cha": "charisma",
}


def _normalize_base_attributes(raw: Dict[str, int] | None) -> Dict[str, int]:
    if not raw:
        return {}

    normalized: Dict[str, int] = {}
    for key, value in raw.items():
        if key is None:
            continue
        attr_key = ABILITY_ALIASES.get(key.lower(), key.lower())
        try:
            normalized[attr_key] = int(value)
        except (TypeError, ValueError):
            continue
    return normalized


def _merge_with_defaults(base_attributes: Dict[str, int]) -> Dict[str, int]:
    merged = dict(DEFAULT_ATTRIBUTES)
    merged.update(base_attributes)
    return merged


def _apply_racial_bonuses(
    base_attributes: Dict[str, int], race: Optional[Race]
) -> Dict[str, int]:
    if not race:
        return dict(base_attributes)

    bonuses = _normalize_base_attributes(race.bonuses)
    merged = dict(base_attributes)
    for key, value in bonuses.items():
        merged[key] = merged.get(key, 0) + value
    return merged


def _apply_difficulty_to_hp(raw_hp: int, difficulty: Optional[DifficultyPreset]) -> int:
    multiplier = difficulty.hp_multiplier if difficulty else 1.0
    scaled = int(raw_hp * multiplier)
    return max(scaled, 1)


def _starting_spell_loadout(cls: CharacterClass) -> tuple[int, list[str], list[str]]:
    """Return (slot_count, cantrips, level_1_spells) for the class."""
    slug = (cls.slug or "").lower()
    full_casters = {"wizard", "sorcerer", "cleric", "bard", "druid"}
    half_casters = {"paladin", "ranger", "artificer"}
    pact_casters = {"warlock"}

    cantrips: list[str] = []
    spells: list[str] = []
    slots = 0

    if slug in full_casters:
        slots = 2
    elif slug in half_casters:
        slots = 1
    elif slug in pact_casters:
        slots = 1

    if slug == "wizard":
        cantrips = ["Fire Bolt", "Ray of Frost"]
        spells = ["Magic Missile", "Shield"]
    elif slug == "sorcerer":
        cantrips = ["Fire Bolt"]
        spells = ["Burning Hands", "Mage Armor"]
    elif slug == "cleric":
        cantrips = ["Sacred Flame"]
        spells = ["Cure Wounds", "Guiding Bolt"]
    elif slug == "bard":
        cantrips = ["Vicious Mockery"]
        spells = ["Healing Word", "Dissonant Whispers"]
    elif slug == "druid":
        cantrips = ["Produce Flame"]
        spells = ["Healing Word"]
    elif slug == "warlock":
        cantrips = ["Eldritch Blast"]
        spells = ["Hex"]
    elif slug == "paladin":
        spells = ["Lay on Hands"]
    elif slug == "ranger":
        spells = ["Hunter's Mark"]
    elif slug == "artificer":
        spells = ["Cure Wounds"]

    return slots, cantrips, spells


def create_new_character(
    name: str,
    cls: CharacterClass,
    ability_scores: Optional[Dict[str, int]] = None,
    race: Optional[Race] = None,
    background: Optional[Background] = None,
    difficulty: Optional[DifficultyPreset] = None,
    starting_equipment: Optional[list[str]] = None,
) -> Character:
    base_hp = HIT_DIE_BASE_HP.get(cls.hit_die, 8) + 2  # small bonus
    hp_max = _apply_difficulty_to_hp(base_hp, difficulty)
    profile = CLASS_COMBAT_PROFILE.get(cls.slug, DEFAULT_COMBAT_PROFILE)

    raw_attributes = ability_scores if ability_scores is not None else {}
    base_attributes = _normalize_base_attributes(raw_attributes)
    base_before_race = dict(base_attributes)
    with_race = _apply_racial_bonuses(base_attributes, race)
    attributes = _merge_with_defaults(with_race)

    traits = list(race.traits) if race else []
    background_features = [background.feature] if background and background.feature else []
    proficiencies = list(background.proficiencies) if background else []
    money = background.starting_money if background else 0
    inventory = list(starting_equipment) if starting_equipment else []

    slots, cantrips, spells = _starting_spell_loadout(cls)

    difficulty_slug = difficulty.slug if difficulty else "normal"
    flags: Dict[str, str] = {"difficulty": difficulty_slug} if difficulty else {}
    if background and background.faction:
        flags["faction_affinity"] = background.faction

    return Character(
        id=None,
        name=name,
        level=1,
        xp=0,
        money=money,
        hp_max=hp_max,
        hp_current=hp_max,
        class_name=cls.slug,
        base_attributes=base_before_race,
        attributes=attributes,
        location_id=None,
        armour_class=profile["ac"],
        attack_bonus=profile["attack_bonus"],
        damage_die=profile["damage_die"],
        race=race.name if race else None,
        race_traits=traits,
        speed=race.speed if race else 30,
        background=background.name if background else None,
        background_features=background_features,
        proficiencies=proficiencies,
        difficulty=difficulty_slug,
        flags=flags,
        inventory=inventory,
        incoming_damage_multiplier=difficulty.incoming_damage_multiplier if difficulty else 1.0,
        outgoing_damage_multiplier=difficulty.outgoing_damage_multiplier if difficulty else 1.0,
        spell_slots_max=slots,
        spell_slots_current=slots,
        cantrips=cantrips,
        known_spells=spells,
    )
