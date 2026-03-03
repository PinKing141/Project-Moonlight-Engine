from __future__ import annotations


REST_HEAL_DIVISOR = 4
REST_HEAL_MINIMUM = 4

MONSTER_KILL_XP_PER_LEVEL = 5
MONSTER_KILL_XP_MINIMUM = 1

MONSTER_KILL_GOLD_PER_LEVEL = 2
MONSTER_KILL_GOLD_MINIMUM = 1

REWARD_MULTIPLIER_MIN = 0.85
REWARD_MULTIPLIER_MAX = 1.30

HARDCORE_TOGGLES_SCHEMA_VERSION = "hardcore_toggles_v1"
HARDCORE_TOGGLE_DEFAULTS = {
    "max_monster_hp": False,
    "deadlier_death_saves": False,
    "rest_lock_on_failed_saves": False,
}

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

DIFFICULTY_TIER_PROFILES = {
    "easy": {
        "name": "Easy",
        "description": "Minimal resource tax with forgiving pacing.",
        "risk_label": "Low risk",
        "casualty_pressure": "Very low",
        "guardrail_warning": "",
        "legacy_labels": ("story",),
        "hp_multiplier": 1.3,
        "incoming_damage_multiplier": 0.75,
        "outgoing_damage_multiplier": 1.0,
        "reward_multiplier": 0.9,
    },
    "normal": {
        "name": "Normal",
        "description": "Baseline challenge with steady pressure.",
        "risk_label": "Stable risk",
        "casualty_pressure": "Low",
        "guardrail_warning": "",
        "legacy_labels": ("medium",),
        "hp_multiplier": 1.0,
        "incoming_damage_multiplier": 1.0,
        "outgoing_damage_multiplier": 1.0,
        "reward_multiplier": 1.0,
    },
    "hard": {
        "name": "Hard",
        "description": "Mistakes are punished and attrition rises.",
        "risk_label": "High risk",
        "casualty_pressure": "Moderate",
        "guardrail_warning": "",
        "legacy_labels": ("hardcore",),
        "hp_multiplier": 0.8,
        "incoming_damage_multiplier": 1.25,
        "outgoing_damage_multiplier": 1.05,
        "reward_multiplier": 1.12,
    },
    "deadly": {
        "name": "Deadly",
        "description": "High lethality pressure requiring tactical consistency.",
        "risk_label": "Very high risk",
        "casualty_pressure": "High",
        "guardrail_warning": "Warning: high chance of mandatory-path failure for undergeared parties.",
        "legacy_labels": (),
        "hp_multiplier": 0.72,
        "incoming_damage_multiplier": 1.4,
        "outgoing_damage_multiplier": 1.08,
        "reward_multiplier": 1.2,
    },
    "nightmare": {
        "name": "Nightmare",
        "description": "Extreme attrition and near-hardcore encounter cadence.",
        "risk_label": "Extreme risk",
        "casualty_pressure": "Very high",
        "guardrail_warning": "Warning: configuration may create unwinnable mandatory encounters without optimized play.",
        "legacy_labels": (),
        "hp_multiplier": 0.65,
        "incoming_damage_multiplier": 1.55,
        "outgoing_damage_multiplier": 1.1,
        "reward_multiplier": 1.28,
    },
}

DIFFICULTY_ALIAS_TO_TIER = {
    "normal": "normal",
    "story": "easy",
    "easy": "easy",
    "medium": "normal",
    "hard": "hard",
    "hardcore": "hard",
    "deadly": "deadly",
    "nightmare": "nightmare",
}

DIFFICULTY_PRESET_PROFILES = {
    "easy": {
        "name": "Easy",
        "description": "Minimal resource tax with forgiving pacing.",
        "risk_label": DIFFICULTY_TIER_PROFILES["easy"]["risk_label"],
        "casualty_pressure": DIFFICULTY_TIER_PROFILES["easy"]["casualty_pressure"],
        "guardrail_warning": DIFFICULTY_TIER_PROFILES["easy"]["guardrail_warning"],
        "legacy_labels": DIFFICULTY_TIER_PROFILES["easy"]["legacy_labels"],
        "hp_multiplier": DIFFICULTY_TIER_PROFILES["easy"]["hp_multiplier"],
        "incoming_damage_multiplier": DIFFICULTY_TIER_PROFILES["easy"]["incoming_damage_multiplier"],
        "outgoing_damage_multiplier": DIFFICULTY_TIER_PROFILES["easy"]["outgoing_damage_multiplier"],
    },
    "normal": {
        "name": "Normal",
        "description": "Baseline challenge with steady pressure.",
        "risk_label": DIFFICULTY_TIER_PROFILES["normal"]["risk_label"],
        "casualty_pressure": DIFFICULTY_TIER_PROFILES["normal"]["casualty_pressure"],
        "guardrail_warning": DIFFICULTY_TIER_PROFILES["normal"]["guardrail_warning"],
        "legacy_labels": DIFFICULTY_TIER_PROFILES["normal"]["legacy_labels"],
        "hp_multiplier": DIFFICULTY_TIER_PROFILES["normal"]["hp_multiplier"],
        "incoming_damage_multiplier": DIFFICULTY_TIER_PROFILES["normal"]["incoming_damage_multiplier"],
        "outgoing_damage_multiplier": DIFFICULTY_TIER_PROFILES["normal"]["outgoing_damage_multiplier"],
    },
    "hard": {
        "name": "Hard",
        "description": "High-pressure combat where mistakes are punished.",
        "risk_label": DIFFICULTY_TIER_PROFILES["hard"]["risk_label"],
        "casualty_pressure": DIFFICULTY_TIER_PROFILES["hard"]["casualty_pressure"],
        "guardrail_warning": DIFFICULTY_TIER_PROFILES["hard"]["guardrail_warning"],
        "legacy_labels": DIFFICULTY_TIER_PROFILES["hard"]["legacy_labels"],
        "hp_multiplier": DIFFICULTY_TIER_PROFILES["hard"]["hp_multiplier"],
        "incoming_damage_multiplier": DIFFICULTY_TIER_PROFILES["hard"]["incoming_damage_multiplier"],
        "outgoing_damage_multiplier": DIFFICULTY_TIER_PROFILES["hard"]["outgoing_damage_multiplier"],
    },
    "deadly": {
        "name": "Deadly",
        "description": "High lethality pressure requiring tactical consistency.",
        "risk_label": DIFFICULTY_TIER_PROFILES["deadly"]["risk_label"],
        "casualty_pressure": DIFFICULTY_TIER_PROFILES["deadly"]["casualty_pressure"],
        "guardrail_warning": DIFFICULTY_TIER_PROFILES["deadly"]["guardrail_warning"],
        "legacy_labels": DIFFICULTY_TIER_PROFILES["deadly"]["legacy_labels"],
        "hp_multiplier": DIFFICULTY_TIER_PROFILES["deadly"]["hp_multiplier"],
        "incoming_damage_multiplier": DIFFICULTY_TIER_PROFILES["deadly"]["incoming_damage_multiplier"],
        "outgoing_damage_multiplier": DIFFICULTY_TIER_PROFILES["deadly"]["outgoing_damage_multiplier"],
    },
    "nightmare": {
        "name": "Nightmare",
        "description": "Extreme attrition and near-hardcore encounter cadence.",
        "risk_label": DIFFICULTY_TIER_PROFILES["nightmare"]["risk_label"],
        "casualty_pressure": DIFFICULTY_TIER_PROFILES["nightmare"]["casualty_pressure"],
        "guardrail_warning": DIFFICULTY_TIER_PROFILES["nightmare"]["guardrail_warning"],
        "legacy_labels": DIFFICULTY_TIER_PROFILES["nightmare"]["legacy_labels"],
        "hp_multiplier": DIFFICULTY_TIER_PROFILES["nightmare"]["hp_multiplier"],
        "incoming_damage_multiplier": DIFFICULTY_TIER_PROFILES["nightmare"]["incoming_damage_multiplier"],
        "outgoing_damage_multiplier": DIFFICULTY_TIER_PROFILES["nightmare"]["outgoing_damage_multiplier"],
    },
}


def resolve_difficulty_tier(difficulty_slug: str | None) -> str:
    slug = str(difficulty_slug or "").strip().lower()
    if not slug:
        return "normal"
    return str(DIFFICULTY_ALIAS_TO_TIER.get(slug, "normal"))


def normalize_hardcore_toggles(payload: dict[str, object] | None) -> dict[str, bool]:
    normalized = {key: bool(value) for key, value in HARDCORE_TOGGLE_DEFAULTS.items()}
    if not isinstance(payload, dict):
        return normalized

    alias_keys = {
        "rest_restrictions": "rest_lock_on_failed_saves",
    }
    for raw_key, raw_value in payload.items():
        key = str(raw_key or "").strip().lower()
        canonical = alias_keys.get(key, key)
        if canonical not in normalized:
            continue
        normalized[canonical] = bool(raw_value)
    return normalized


def difficulty_profile_for_slug(difficulty_slug: str | None) -> dict[str, float | str]:
    tier = resolve_difficulty_tier(difficulty_slug)
    profile = DIFFICULTY_TIER_PROFILES.get(tier, DIFFICULTY_TIER_PROFILES["normal"])
    return dict(profile)


def difficulty_reward_multiplier(difficulty_slug: str | None) -> float:
    profile = difficulty_profile_for_slug(difficulty_slug)
    raw = float(profile.get("reward_multiplier", 1.0) or 1.0)
    return max(REWARD_MULTIPLIER_MIN, min(REWARD_MULTIPLIER_MAX, raw))


def rest_heal_amount(hp_max: int) -> int:
    return max(hp_max // REST_HEAL_DIVISOR, REST_HEAL_MINIMUM)


def monster_kill_xp(level: int, difficulty_slug: str | None = None) -> int:
    base = max(level * MONSTER_KILL_XP_PER_LEVEL, MONSTER_KILL_XP_MINIMUM)
    scaled = int(base * difficulty_reward_multiplier(difficulty_slug))
    return max(scaled, MONSTER_KILL_XP_MINIMUM)


def monster_kill_gold(level: int, difficulty_slug: str | None = None) -> int:
    base = max(level * MONSTER_KILL_GOLD_PER_LEVEL, MONSTER_KILL_GOLD_MINIMUM)
    scaled = int(base * difficulty_reward_multiplier(difficulty_slug))
    return max(scaled, MONSTER_KILL_GOLD_MINIMUM)


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
