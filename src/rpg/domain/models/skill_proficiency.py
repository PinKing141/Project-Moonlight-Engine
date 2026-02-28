from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SkillDefinition:
    slug: str
    label: str
    category: str
    special: bool = False


CORE_SKILLS: tuple[SkillDefinition, ...] = (
    SkillDefinition(slug="athletics", label="Athletics", category="strength"),
    SkillDefinition(slug="acrobatics", label="Acrobatics", category="dexterity"),
    SkillDefinition(slug="sleight_of_hand", label="Sleight of Hand", category="dexterity"),
    SkillDefinition(slug="stealth", label="Stealth", category="dexterity"),
    SkillDefinition(slug="arcana", label="Arcana", category="intelligence"),
    SkillDefinition(slug="history", label="History", category="intelligence"),
    SkillDefinition(slug="investigation", label="Investigation", category="intelligence"),
    SkillDefinition(slug="nature", label="Nature", category="intelligence"),
    SkillDefinition(slug="religion", label="Religion", category="intelligence"),
    SkillDefinition(slug="animal_handling", label="Animal Handling", category="wisdom"),
    SkillDefinition(slug="insight", label="Insight", category="wisdom"),
    SkillDefinition(slug="medicine", label="Medicine", category="wisdom"),
    SkillDefinition(slug="perception", label="Perception", category="wisdom"),
    SkillDefinition(slug="survival", label="Survival", category="wisdom"),
    SkillDefinition(slug="deception", label="Deception", category="charisma"),
    SkillDefinition(slug="intimidation", label="Intimidation", category="charisma"),
    SkillDefinition(slug="performance", label="Performance", category="charisma"),
    SkillDefinition(slug="persuasion", label="Persuasion", category="charisma"),
)

SPECIAL_SKILLS: tuple[SkillDefinition, ...] = (
    SkillDefinition(slug="endurance", label="Endurance", category="special", special=True),
    SkillDefinition(slug="trade_skill", label="Trade Skill", category="special", special=True),
    SkillDefinition(slug="language", label="Language", category="special", special=True),
    SkillDefinition(slug="reading_writing", label="Reading/Writing", category="special", special=True),
)

SKILL_CATALOG: tuple[SkillDefinition, ...] = (*CORE_SKILLS, *SPECIAL_SKILLS)
SKILL_BY_SLUG: dict[str, SkillDefinition] = {row.slug: row for row in SKILL_CATALOG}

_CLASS_CATEGORY_ALLOWLIST: dict[str, set[str]] = {
    "barbarian": {"strength", "dexterity", "constitution"},
    "fighter": {"strength", "dexterity", "constitution"},
    "monk": {"strength", "dexterity", "wisdom"},
    "paladin": {"strength", "charisma", "constitution"},
    "ranger": {"strength", "dexterity", "wisdom"},
    "rogue": {"dexterity", "intelligence", "charisma"},
    "bard": {"dexterity", "charisma", "wisdom"},
    "cleric": {"wisdom", "charisma", "strength"},
    "druid": {"wisdom", "intelligence", "constitution"},
    "sorcerer": {"charisma", "constitution", "dexterity"},
    "warlock": {"charisma", "intelligence", "wisdom"},
    "wizard": {"intelligence", "wisdom", "dexterity"},
    "artificer": {"intelligence", "constitution", "dexterity"},
}


def normalize_skill_slug(value: str) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("/", " ")
    text = text.replace("-", " ")
    text = text.replace("'", "")
    return "_".join(part for part in text.split() if part)


def normalize_skill_map(values: dict[str, int] | None) -> dict[str, int]:
    if not isinstance(values, dict):
        return {}
    normalized: dict[str, int] = {}
    for key, raw in values.items():
        slug = normalize_skill_slug(str(key))
        if not slug:
            continue
        try:
            score = int(raw)
        except Exception:
            continue
        if score <= 0:
            continue
        normalized[slug] = score
    return normalized


def allowed_skill_categories_for_class(class_name: str | None) -> set[str]:
    slug = normalize_skill_slug(class_name or "")
    if slug in _CLASS_CATEGORY_ALLOWLIST:
        return set(_CLASS_CATEGORY_ALLOWLIST[slug])
    return {"strength", "dexterity", "intelligence", "wisdom", "charisma", "constitution"}


def category_for_skill(slug: str) -> str | None:
    row = SKILL_BY_SLUG.get(normalize_skill_slug(slug))
    return row.category if row else None


def is_special_skill(slug: str) -> bool:
    row = SKILL_BY_SLUG.get(normalize_skill_slug(slug))
    return bool(row.special) if row else False


def skill_label(slug: str) -> str:
    normalized = normalize_skill_slug(slug)
    row = SKILL_BY_SLUG.get(normalized)
    if row is not None:
        return row.label
    return normalized.replace("_", " ").title()
