from __future__ import annotations


REST_HEAL_DIVISOR = 4
REST_HEAL_MINIMUM = 4

MONSTER_KILL_XP_PER_LEVEL = 5
MONSTER_KILL_XP_MINIMUM = 1

MONSTER_KILL_GOLD_PER_LEVEL = 2
MONSTER_KILL_GOLD_MINIMUM = 1

LEVEL_UP_XP_STEP = 25
LEVEL_CAP = 20

FULL_CASTER_CLASSES = {
    "bard",
    "cleric",
    "druid",
    "sorcerer",
    "wizard",
}
HALF_CASTER_CLASSES = {
    "paladin",
    "ranger",
    "artificer",
}
THIRD_CASTER_CLASSES = {
    "arcane_trickster",
    "eldritch_knight",
}

_MULTICLASS_TOTAL_SPELL_SLOTS = {
    1: 2,
    2: 3,
    3: 6,
    4: 7,
    5: 9,
    6: 10,
    7: 11,
    8: 12,
    9: 14,
    10: 15,
    11: 16,
    12: 16,
    13: 17,
    14: 17,
    15: 18,
    16: 18,
    17: 19,
    18: 20,
    19: 21,
    20: 22,
}

FIRST_HUNT_QUEST_ID = "first_hunt"
FIRST_HUNT_TARGET_KILLS = 1
FIRST_HUNT_REWARD_XP = 10
FIRST_HUNT_REWARD_MONEY = 5

DIFFICULTY_PRESET_PROFILES = {
    "story": {
        "name": "Story Mode",
        "description": "More HP, forgiving damage for a relaxed run.",
        "hp_multiplier": 1.3,
        "incoming_damage_multiplier": 0.75,
        "outgoing_damage_multiplier": 1.0,
    },
    "normal": {
        "name": "Standard",
        "description": "Baseline challenge.",
        "hp_multiplier": 1.0,
        "incoming_damage_multiplier": 1.0,
        "outgoing_damage_multiplier": 1.0,
    },
    "hardcore": {
        "name": "Hardcore",
        "description": "Harsher blows and slimmer HP.",
        "hp_multiplier": 0.8,
        "incoming_damage_multiplier": 1.25,
        "outgoing_damage_multiplier": 1.05,
    },
}


def rest_heal_amount(hp_max: int) -> int:
    return max(hp_max // REST_HEAL_DIVISOR, REST_HEAL_MINIMUM)


def monster_kill_xp(level: int) -> int:
    return max(level * MONSTER_KILL_XP_PER_LEVEL, MONSTER_KILL_XP_MINIMUM)


def monster_kill_gold(level: int) -> int:
    return max(level * MONSTER_KILL_GOLD_PER_LEVEL, MONSTER_KILL_GOLD_MINIMUM)


def xp_required_for_level(level: int) -> int:
    safe_level = max(1, int(level))
    return (safe_level - 1) * LEVEL_UP_XP_STEP


def multiclass_caster_level(class_levels: dict[str, int] | None) -> int:
    if not isinstance(class_levels, dict):
        return 0
    total = 0
    for raw_slug, raw_level in class_levels.items():
        slug = str(raw_slug or "").strip().lower()
        try:
            class_level = max(0, int(raw_level or 0))
        except Exception:
            class_level = 0
        if class_level <= 0:
            continue
        if slug in FULL_CASTER_CLASSES:
            total += class_level
        elif slug in HALF_CASTER_CLASSES:
            total += class_level // 2
        elif slug in THIRD_CASTER_CLASSES:
            total += class_level // 3
    return max(0, min(20, int(total)))


def multiclass_spell_slot_pool(caster_level: int) -> int:
    level_key = max(0, min(20, int(caster_level or 0)))
    if level_key <= 0:
        return 0
    return int(_MULTICLASS_TOTAL_SPELL_SLOTS.get(level_key, 0))
