from __future__ import annotations

from rpg.application.dtos import CharacterClassDetailView
from rpg.domain.services.class_profiles import CLASS_COMBAT_PROFILE, CLASS_DESCRIPTIONS, DEFAULT_COMBAT_PROFILE


def to_character_class_detail_view(
    *,
    class_name: str,
    class_slug: str,
    primary_ability: str | None,
    hit_die: str | None,
    recommended_line: str,
) -> CharacterClassDetailView:
    profile = CLASS_COMBAT_PROFILE.get(class_slug, DEFAULT_COMBAT_PROFILE)
    description = CLASS_DESCRIPTIONS.get(class_slug, "Adventurer ready for the unknown.")
    return CharacterClassDetailView(
        title=f"Class: {class_name}",
        description=description,
        primary_ability=primary_ability or "None",
        hit_die=hit_die or "d8",
        combat_profile_line=f"AC {profile['ac']}, +{profile['attack_bonus']} to hit, damage {profile['damage_die']}",
        recommended_line=recommended_line,
    )
