from __future__ import annotations

from rpg.application.dtos import LevelUpPendingView
from rpg.application.services.balance_tables import LEVEL_CAP, xp_required_for_level
from rpg.domain.events import LevelUpAppliedEvent, LevelUpPendingEvent
from rpg.domain.models.character import Character
from rpg.domain.models.progression import ExperiencePoints, Level, normalize_growth_choice


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
            if choice.kind in {"feat", "spell"}:
                unlock_key = f"level_{current_level}_{choice.kind}"
                unlocks[unlock_key] = True

            history.append(
                {
                    "from_level": int(current_level - 1),
                    "to_level": int(current_level),
                    "xp": int(current_xp),
                    "growth_choice": choice.kind,
                    "option": choice.option,
                    "hp_gain": int(hp_gain),
                }
            )
            messages.append(f"Level up! You reached level {current_level} (+{hp_gain} max HP).")

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
