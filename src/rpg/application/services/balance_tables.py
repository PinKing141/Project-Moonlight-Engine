from __future__ import annotations


REST_HEAL_DIVISOR = 4
REST_HEAL_MINIMUM = 4

MONSTER_KILL_XP_PER_LEVEL = 5
MONSTER_KILL_XP_MINIMUM = 1

MONSTER_KILL_GOLD_PER_LEVEL = 2
MONSTER_KILL_GOLD_MINIMUM = 1

LEVEL_UP_XP_STEP = 25
LEVEL_CAP = 20

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
