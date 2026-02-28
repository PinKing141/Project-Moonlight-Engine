from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SubclassTierUnlock:
    tier: int
    level: int
    label: str


SUBCLASS_SELECTION_LEVEL_BY_CLASS: dict[str, int] = {
    "artificer": 3,
    "barbarian": 3,
    "bard": 3,
    "cleric": 1,
    "druid": 2,
    "fighter": 3,
    "monk": 3,
    "paladin": 3,
    "ranger": 3,
    "rogue": 3,
    "sorcerer": 1,
    "warlock": 1,
    "wizard": 2,
}


def subclass_tier_levels_for_class(class_slug_or_name: str | None) -> tuple[int, ...]:
    class_key = str(class_slug_or_name or "").strip().lower()
    selection_level = int(SUBCLASS_SELECTION_LEVEL_BY_CLASS.get(class_key, 3) or 3)
    if selection_level <= 1:
        return (1, 6, 14, 18)
    if selection_level == 2:
        return (2, 6, 10, 14)
    return (3, 6, 10, 14)


def resolve_subclass_tier_unlocks(
    *,
    class_slug_or_name: str | None,
    subclass_slug: str | None,
    character_level: int,
) -> list[SubclassTierUnlock]:
    if not str(subclass_slug or "").strip():
        return []
    tier_levels = subclass_tier_levels_for_class(class_slug_or_name)
    labels = (
        "Subclass Initiate",
        "Subclass Adept",
        "Subclass Expert",
        "Subclass Master",
    )
    unlocked: list[SubclassTierUnlock] = []
    level = max(1, int(character_level or 1))
    for index, unlock_level in enumerate(tier_levels):
        if level != int(unlock_level):
            continue
        unlocked.append(
            SubclassTierUnlock(
                tier=index + 1,
                level=int(unlock_level),
                label=labels[min(index, len(labels) - 1)],
            )
        )
    return unlocked
