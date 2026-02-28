from __future__ import annotations

from rpg.application.dtos import LevelUpPendingView
from rpg.application.services.balance_tables import LEVEL_CAP, xp_required_for_level
from rpg.application.services.combat_service import proficiency_bonus
from rpg.domain.events import LevelUpAppliedEvent, LevelUpPendingEvent
from rpg.domain.models.character import Character
from rpg.domain.models.progression import ExperiencePoints, Level, normalize_growth_choice
from rpg.domain.models.skill_proficiency import (
    SKILL_BY_SLUG,
    SKILL_CATALOG,
    allowed_skill_categories_for_class,
    category_for_skill,
    is_special_skill,
    normalize_skill_map,
    normalize_skill_slug,
    skill_label,
)
from rpg.domain.services.subclass_progression import resolve_subclass_tier_unlocks


class ProgressionService:
    def __init__(self, event_publisher=None) -> None:
        self._event_publisher = event_publisher

    @staticmethod
    def _ability_mod(score: int | None) -> int:
        if score is None:
            return 0
        try:
            return (int(score) - 10) // 2
        except Exception:
            return 0

    @staticmethod
    def _ensure_flags(character: Character) -> dict:
        flags = getattr(character, "flags", None)
        if not isinstance(flags, dict):
            flags = {}
            character.flags = flags
        return flags

    def _ensure_skill_training(self, character: Character) -> dict:
        flags = self._ensure_flags(character)
        payload = flags.setdefault("skill_training", {})
        if not isinstance(payload, dict):
            payload = {}
            flags["skill_training"] = payload

        modifiers = normalize_skill_map(payload.get("modifiers"))
        payload["modifiers"] = modifiers

        intent_raw = payload.get("intent", [])
        intent: list[str] = []
        if isinstance(intent_raw, list):
            seen: set[str] = set()
            for value in intent_raw:
                slug = normalize_skill_slug(str(value))
                if slug and slug not in seen:
                    intent.append(slug)
                    seen.add(slug)
        payload["intent"] = intent

        try:
            payload["points_available"] = max(0, int(payload.get("points_available", 0) or 0))
        except Exception:
            payload["points_available"] = 0
        try:
            payload["points_source_level"] = max(0, int(payload.get("points_source_level", 0) or 0))
        except Exception:
            payload["points_source_level"] = 0
        try:
            payload["spent_this_level"] = max(0, int(payload.get("spent_this_level", 0) or 0))
        except Exception:
            payload["spent_this_level"] = 0
        return payload

    def _known_skill_categories(self, character: Character) -> set[str]:
        categories: set[str] = set()
        for label in list(getattr(character, "proficiencies", []) or []):
            category = category_for_skill(str(label))
            if category:
                categories.add(category)
        return categories

    def initialize_skill_training(
        self,
        character: Character,
        *,
        grant_level_points: bool = False,
    ) -> dict[str, object]:
        training = self._ensure_skill_training(character)
        if grant_level_points and int(training.get("points_available", 0) or 0) <= 0:
            level = max(1, int(getattr(character, "level", 1) or 1))
            training["points_available"] = int(proficiency_bonus(level))
            training["points_source_level"] = level
            training["spent_this_level"] = 0
        return {
            "points_available": int(training.get("points_available", 0) or 0),
            "points_source_level": int(training.get("points_source_level", 0) or 0),
            "spent_this_level": int(training.get("spent_this_level", 0) or 0),
            "intent": list(training.get("intent", [])),
            "modifiers": dict(training.get("modifiers", {})),
        }

    def get_skill_training_snapshot(self, character: Character) -> dict[str, object]:
        training = self._ensure_skill_training(character)
        return {
            "points_available": int(training.get("points_available", 0) or 0),
            "points_source_level": int(training.get("points_source_level", 0) or 0),
            "spent_this_level": int(training.get("spent_this_level", 0) or 0),
            "intent": list(training.get("intent", [])),
            "modifiers": dict(training.get("modifiers", {})),
        }

    def allowed_skill_categories(self, character: Character) -> set[str]:
        class_allowed = allowed_skill_categories_for_class(getattr(character, "class_name", None))
        background_allowed = self._known_skill_categories(character)
        return set(class_allowed).union(background_allowed)

    def list_granular_skills(self, character: Character, *, allow_special: bool = False) -> list[dict[str, object]]:
        training = self._ensure_skill_training(character)
        modifiers = normalize_skill_map(training.get("modifiers"))
        allowed_categories = self.allowed_skill_categories(character)
        intent = set(training.get("intent", []))
        rows: list[dict[str, object]] = []
        for definition in SKILL_CATALOG:
            if definition.special and not allow_special:
                continue
            has_rank = int(modifiers.get(definition.slug, 0) or 0) > 0
            category_allowed = definition.category in allowed_categories
            intent_declared = definition.slug in intent
            eligible_new = has_rank or category_allowed or (definition.special and allow_special)
            rows.append(
                {
                    "slug": definition.slug,
                    "label": definition.label,
                    "category": definition.category,
                    "special": bool(definition.special),
                    "current": int(modifiers.get(definition.slug, 0) or 0),
                    "intent_declared": intent_declared,
                    "eligible_new": bool(eligible_new),
                }
            )
        return rows

    def declare_skill_training_intent(self, character: Character, skill_slugs: list[str]) -> dict[str, object]:
        training = self._ensure_skill_training(character)
        intent: list[str] = []
        seen: set[str] = set()
        for raw in list(skill_slugs or []):
            slug = normalize_skill_slug(raw)
            if not slug or slug in seen:
                continue
            if slug not in SKILL_BY_SLUG:
                continue
            intent.append(slug)
            seen.add(slug)
        training["intent"] = intent
        return {"intent": list(intent)}

    def spend_skill_proficiency_points(
        self,
        character: Character,
        allocations: dict[str, int],
        *,
        allow_special: bool = False,
        require_intent_for_new: bool = True,
    ) -> list[str]:
        training = self._ensure_skill_training(character)
        modifiers = normalize_skill_map(training.get("modifiers"))
        intent = set(training.get("intent", []))
        points = int(training.get("points_available", 0) or 0)
        if points <= 0:
            raise ValueError("No skill proficiency points available")

        allowed_categories = self.allowed_skill_categories(character)
        current_level = max(1, int(getattr(character, "level", 1) or 1))
        cap = min(6, proficiency_bonus(current_level) + 1)

        normalized_allocations = normalize_skill_map(allocations)
        if not normalized_allocations:
            raise ValueError("No skill allocations provided")

        spent = 0
        messages: list[str] = []
        for raw_slug, amount in normalized_allocations.items():
            slug = normalize_skill_slug(raw_slug)
            if slug not in SKILL_BY_SLUG:
                raise ValueError(f"Unknown skill: {raw_slug}")
            for _ in range(int(amount)):
                if points <= 0:
                    raise ValueError("Insufficient skill proficiency points")
                current = int(modifiers.get(slug, 0) or 0)
                if current >= cap:
                    raise ValueError(f"{skill_label(slug)} has reached the cap ({cap})")

                if current <= 0:
                    category = category_for_skill(slug)
                    if is_special_skill(slug) and not allow_special:
                        raise ValueError(f"{skill_label(slug)} requires special training approval")
                    if not is_special_skill(slug) and category not in allowed_categories:
                        raise ValueError(f"{skill_label(slug)} is outside allowed class/background categories")
                    if require_intent_for_new and slug not in intent:
                        raise ValueError(f"{skill_label(slug)} requires declared training intent")
                    next_value = 2
                else:
                    next_value = min(cap, current + 1)

                modifiers[slug] = next_value
                points -= 1
                spent += 1
                messages.append(f"{skill_label(slug)} proficiency is now +{next_value}.")

        training["modifiers"] = modifiers
        training["points_available"] = points
        training["spent_this_level"] = int(training.get("spent_this_level", 0) or 0) + spent
        return messages

    def preview_pending(self, character: Character) -> LevelUpPendingView | None:
        current_level = Level(max(1, int(getattr(character, "level", 1) or 1)))
        xp = ExperiencePoints(max(0, int(getattr(character, "xp", 0) or 0)))
        if current_level.value >= LEVEL_CAP:
            return None
        next_level = current_level.value + 1
        required = xp_required_for_level(next_level)
        if xp.value < required:
            return None
        return LevelUpPendingView(
            character_id=int(getattr(character, "id", 0) or 0),
            current_level=current_level.value,
            next_level=next_level,
            xp_current=xp.value,
            xp_required=int(required),
            growth_choices=["vitality", "feat", "spell"],
            summary=f"You can level up to {next_level}. Choose how you want to grow.",
        )

    def apply_level_progression(self, character: Character, growth_choice: str | None = None) -> list[str]:
        current_level = max(1, int(getattr(character, "level", 1) or 1))
        current_xp = max(0, int(getattr(character, "xp", 0) or 0))
        choice = normalize_growth_choice(growth_choice)

        attrs = getattr(character, "attributes", {}) or {}
        con_mod = self._ability_mod(attrs.get("constitution"))
        base_hp_gain = max(2, 5 + con_mod)

        flags = self._ensure_flags(character)
        history = flags.setdefault("progression_history", [])
        if not isinstance(history, list):
            history = []
            flags["progression_history"] = history

        messages: list[str] = []
        while current_level < LEVEL_CAP and current_xp >= xp_required_for_level(current_level + 1):
            target_level = current_level + 1
            if callable(self._event_publisher):
                self._event_publisher(
                    LevelUpPendingEvent(
                        character_id=int(getattr(character, "id", 0) or 0),
                        from_level=current_level,
                        to_level=target_level,
                        xp=current_xp,
                    )
                )

            hp_gain = base_hp_gain + (1 if choice.kind == "vitality" else 0)
            character.hp_max = max(1, int(getattr(character, "hp_max", 1)) + hp_gain)
            character.hp_current = min(character.hp_max, int(getattr(character, "hp_current", 1)) + hp_gain)
            current_level = target_level
            character.level = current_level

            unlocks = flags.setdefault("progression_unlocks", {})
            if not isinstance(unlocks, dict):
                unlocks = {}
                flags["progression_unlocks"] = unlocks
            unlock_rows: list[dict[str, object]] = []
            if choice.kind in {"feat", "spell"}:
                unlock_key = f"level_{current_level}_{choice.kind}"
                unlocks[unlock_key] = True
                unlock_rows.append(
                    {
                        "kind": "growth_choice",
                        "key": unlock_key,
                        "level": int(current_level),
                    }
                )

            subclass_slug = ""
            subclass_name = ""
            if isinstance(flags, dict):
                subclass_slug = str(flags.get("subclass_slug", "") or "").strip().lower()
                subclass_name = str(flags.get("subclass_name", "") or "").strip()
            subclass_progression = flags.setdefault("subclass_progression", {})
            if not isinstance(subclass_progression, dict):
                subclass_progression = {}
                flags["subclass_progression"] = subclass_progression

            unlocked_tiers_raw = list(subclass_progression.get("unlocked_tiers", []) or [])
            unlocked_tiers: set[int] = set()
            for value in unlocked_tiers_raw:
                try:
                    unlocked_tiers.add(int(value))
                except Exception:
                    continue

            tier_unlocks = resolve_subclass_tier_unlocks(
                class_slug_or_name=getattr(character, "class_name", ""),
                subclass_slug=subclass_slug,
                character_level=current_level,
            )
            for unlock in tier_unlocks:
                if int(unlock.tier) in unlocked_tiers:
                    continue
                unlocked_tiers.add(int(unlock.tier))
                subclass_key = f"subclass_{subclass_slug}_tier_{int(unlock.tier)}"
                unlocks[subclass_key] = True
                unlock_rows.append(
                    {
                        "kind": "subclass_tier",
                        "key": subclass_key,
                        "level": int(current_level),
                    }
                )
                display_name = subclass_name or subclass_slug.replace("_", " ").title()
                messages.append(
                    f"Subclass advancement unlocked: {display_name} — {unlock.label} (tier {unlock.tier}) at level {current_level}."
                )

            subclass_progression["unlocked_tiers"] = sorted(int(value) for value in unlocked_tiers)
            subclass_progression["last_level_processed"] = int(current_level)

            history.append(
                {
                    "from_level": int(current_level - 1),
                    "to_level": int(current_level),
                    "xp": int(current_xp),
                    "growth_choice": choice.kind,
                    "option": choice.option,
                    "hp_gain": int(hp_gain),
                    "unlocks": unlock_rows,
                }
            )
            messages.append(f"Level up! You reached level {current_level} (+{hp_gain} max HP).")

            skill_training = self._ensure_skill_training(character)
            prior_points = int(skill_training.get("points_available", 0) or 0)
            prior_source = int(skill_training.get("points_source_level", 0) or 0)
            if prior_points > 0 and prior_source > 0 and prior_source < current_level:
                messages.append(
                    f"{prior_points} unspent skill proficiency point(s) from level {prior_source} expired."
                )
            earned_points = int(proficiency_bonus(current_level))
            skill_training["points_available"] = earned_points
            skill_training["points_source_level"] = current_level
            skill_training["spent_this_level"] = 0
            messages.append(
                f"You gained {earned_points} skill proficiency point(s) for level {current_level}."
            )

            if callable(self._event_publisher):
                self._event_publisher(
                    LevelUpAppliedEvent(
                        character_id=int(getattr(character, "id", 0) or 0),
                        from_level=current_level - 1,
                        to_level=current_level,
                        hp_gain=int(hp_gain),
                        growth_choice=choice.kind,
                    )
                )

        if messages:
            flags["last_level_up"] = {
                "from_level": int(history[-1]["from_level"]),
                "to_level": int(history[-1]["to_level"]),
                "xp": int(current_xp),
                "hp_gain_last": int(history[-1]["hp_gain"]),
                "growth_choice": str(history[-1]["growth_choice"]),
            }
        return messages
