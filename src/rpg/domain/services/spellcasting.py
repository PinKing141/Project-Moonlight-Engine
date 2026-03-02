from __future__ import annotations

from typing import Any


def _character_flags(actor: Any) -> dict[str, Any]:
    flags = getattr(actor, "flags", None)
    if not isinstance(flags, dict):
        flags = {}
        setattr(actor, "flags", flags)
    return flags


def normalize_slot_ledger(actor: Any) -> tuple[dict[int, int], dict[int, int]]:
    flags = _character_flags(actor)
    ledger = flags.get("spell_slot_ledger")
    max_by_level: dict[int, int] = {}
    current_by_level: dict[int, int] = {}

    if isinstance(ledger, dict):
        raw_max = ledger.get("max")
        raw_current = ledger.get("current")
        if isinstance(raw_max, dict):
            for level_key, value in raw_max.items():
                try:
                    level = int(level_key)
                    amount = max(0, int(value or 0))
                except Exception:
                    continue
                if level > 0 and amount > 0:
                    max_by_level[level] = amount
        if isinstance(raw_current, dict):
            for level_key, value in raw_current.items():
                try:
                    level = int(level_key)
                    amount = max(0, int(value or 0))
                except Exception:
                    continue
                if level > 0:
                    current_by_level[level] = amount

    if not max_by_level:
        try:
            fallback_max = max(0, int(getattr(actor, "spell_slots_max", 0) or 0))
        except Exception:
            fallback_max = 0
        try:
            fallback_current = max(0, int(getattr(actor, "spell_slots_current", fallback_max) or fallback_max))
        except Exception:
            fallback_current = fallback_max
        if fallback_max > 0:
            max_by_level[1] = fallback_max
            current_by_level[1] = min(fallback_max, fallback_current)

    normalized_current: dict[int, int] = {}
    for level, max_amount in max_by_level.items():
        normalized_current[level] = max(0, min(max_amount, int(current_by_level.get(level, max_amount) or 0)))

    set_slot_ledger(actor, max_by_level=max_by_level, current_by_level=normalized_current)
    return dict(max_by_level), dict(normalized_current)


def set_slot_ledger(actor: Any, *, max_by_level: dict[int, int], current_by_level: dict[int, int]) -> None:
    flags = _character_flags(actor)
    clean_max: dict[str, int] = {}
    clean_current: dict[str, int] = {}
    total_max = 0
    total_current = 0

    for raw_level in sorted(max_by_level.keys()):
        try:
            level = int(raw_level)
            max_amount = max(0, int(max_by_level.get(raw_level, 0) or 0))
        except Exception:
            continue
        if level <= 0 or max_amount <= 0:
            continue
        current_amount = max(0, min(max_amount, int(current_by_level.get(level, max_amount) or 0)))
        clean_max[str(level)] = int(max_amount)
        clean_current[str(level)] = int(current_amount)
        total_max += int(max_amount)
        total_current += int(current_amount)

    flags["spell_slot_ledger"] = {"max": clean_max, "current": clean_current}
    setattr(actor, "spell_slots_max", int(total_max))
    setattr(actor, "spell_slots_current", int(total_current))


def available_slot_levels(actor: Any, *, min_level: int) -> list[int]:
    max_by_level, current_by_level = normalize_slot_ledger(actor)
    threshold = max(1, int(min_level or 1))
    return [
        level
        for level in sorted(max_by_level.keys())
        if int(level) >= threshold and int(current_by_level.get(level, 0) or 0) > 0
    ]


def consume_slot(actor: Any, *, cast_level: int) -> bool:
    max_by_level, current_by_level = normalize_slot_ledger(actor)
    level = int(cast_level or 0)
    if level <= 0:
        return True
    if int(current_by_level.get(level, 0) or 0) <= 0:
        return False
    current_by_level[level] = int(current_by_level.get(level, 0) or 0) - 1
    set_slot_ledger(actor, max_by_level=max_by_level, current_by_level=current_by_level)
    return True


def restore_slots(actor: Any, *, amount: int | None = None) -> int:
    max_by_level, current_by_level = normalize_slot_ledger(actor)
    restored = 0
    if amount is None:
        set_slot_ledger(actor, max_by_level=max_by_level, current_by_level=max_by_level)
        return sum(int(max_by_level.get(level, 0) or 0) - int(current_by_level.get(level, 0) or 0) for level in max_by_level.keys())

    remaining = max(0, int(amount or 0))
    if remaining <= 0:
        return 0

    for level in sorted(max_by_level.keys()):
        if remaining <= 0:
            break
        cap = int(max_by_level.get(level, 0) or 0)
        now = int(current_by_level.get(level, 0) or 0)
        if now >= cap:
            continue
        delta = min(remaining, cap - now)
        current_by_level[level] = now + delta
        restored += delta
        remaining -= delta

    set_slot_ledger(actor, max_by_level=max_by_level, current_by_level=current_by_level)
    return int(restored)
