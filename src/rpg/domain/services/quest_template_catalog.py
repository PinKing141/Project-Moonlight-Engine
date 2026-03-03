from __future__ import annotations

from typing import Mapping

from rpg.domain.models.quest import QuestObjective, QuestObjectiveKind, QuestTemplate


QUEST_TEMPLATE_SCHEMA_VERSION = "quest_template_v1"

_ALLOWED_TEMPLATE_FIELDS = {
    "template_version",
    "slug",
    "title",
    "objective",
    "reward_xp",
    "reward_money",
    "status",
    "default_progress",
    "expires_days",
    "cataclysm_pushback",
    "pushback_tier",
    "requires_alliance_reputation",
    "requires_alliance_count",
    "is_apex_objective",
    "faction_id",
    "tags",
}


def _normalize_slug(value: object) -> str:
    return str(value or "").strip().lower().replace(" ", "_")


def _normalize_int(value: object, default: int = 0, minimum: int | None = None) -> int:
    parsed = int(default)
    if isinstance(value, bool):
        parsed = int(value)
    elif isinstance(value, int):
        parsed = value
    elif isinstance(value, float):
        parsed = int(value)
    elif isinstance(value, str):
        try:
            parsed = int(value.strip())
        except Exception:
            parsed = int(default)
    if minimum is not None:
        parsed = max(int(minimum), parsed)
    return int(parsed)


def _normalize_tags(value: object) -> tuple[str, ...]:
    if isinstance(value, list):
        rows = value
    elif isinstance(value, tuple):
        rows = list(value)
    elif isinstance(value, str):
        rows = [part.strip() for part in value.split(",") if part.strip()]
    else:
        rows = []
    normalized = [_normalize_slug(item) for item in rows if _normalize_slug(item)]
    return tuple(normalized)


def _normalize_objective(payload: object) -> tuple[QuestObjective, tuple[str, ...]]:
    warnings: list[str] = []
    raw = payload if isinstance(payload, Mapping) else {}

    kind_raw = _normalize_slug(raw.get("kind", QuestObjectiveKind.HUNT.value))
    objective_kind = QuestObjectiveKind.HUNT
    try:
        objective_kind = QuestObjectiveKind(kind_raw)
    except Exception:
        warnings.append(f"Unknown objective kind '{kind_raw or 'missing'}'; defaulting to hunt.")

    target_key = _normalize_slug(raw.get("target_key", "any_hostile")) or "any_hostile"
    target_count = _normalize_int(raw.get("target_count", 1), default=1, minimum=1)
    return (
        QuestObjective(kind=objective_kind, target_key=target_key, target_count=target_count),
        tuple(warnings),
    )


def normalize_template_payload(payload: Mapping[str, object] | None) -> tuple[dict[str, object], tuple[str, ...]]:
    warnings: list[str] = []
    raw = payload if isinstance(payload, Mapping) else {}

    version = str(raw.get("template_version", "") or "").strip()
    if version != QUEST_TEMPLATE_SCHEMA_VERSION:
        warnings.append(
            f"Unknown template version '{version or 'missing'}'; defaulting to {QUEST_TEMPLATE_SCHEMA_VERSION}."
        )
        version = QUEST_TEMPLATE_SCHEMA_VERSION

    unknown = sorted(set(str(key) for key in raw.keys()) - _ALLOWED_TEMPLATE_FIELDS)
    if unknown:
        warnings.append(f"Unsupported template fields ignored: {', '.join(unknown)}.")

    slug = _normalize_slug(raw.get("slug", ""))
    if not slug:
        warnings.append("Template slug missing; template will be ignored.")

    title = str(raw.get("title", "") or "").strip() or slug.replace("_", " ").title() or "Untitled Contract"
    objective, objective_warnings = _normalize_objective(raw.get("objective", {}))
    warnings.extend(objective_warnings)

    normalized: dict[str, object] = {
        "template_version": version,
        "slug": slug,
        "title": title,
        "objective": {
            "kind": objective.kind.value,
            "target_key": str(objective.target_key),
            "target_count": int(objective.target_count),
        },
        "reward_xp": _normalize_int(raw.get("reward_xp", 0), default=0, minimum=0),
        "reward_money": _normalize_int(raw.get("reward_money", 0), default=0, minimum=0),
        "status": str(raw.get("status", "available") or "available").strip().lower() or "available",
        "default_progress": _normalize_int(raw.get("default_progress", 0), default=0, minimum=0),
        "expires_days": _normalize_int(raw.get("expires_days", 5), default=5, minimum=1),
        "cataclysm_pushback": bool(raw.get("cataclysm_pushback", False)),
        "pushback_tier": _normalize_int(raw.get("pushback_tier", 0), default=0, minimum=0),
        "requires_alliance_reputation": _normalize_int(raw.get("requires_alliance_reputation", 0), default=0, minimum=0),
        "requires_alliance_count": _normalize_int(raw.get("requires_alliance_count", 0), default=0, minimum=0),
        "is_apex_objective": bool(raw.get("is_apex_objective", False)),
        "faction_id": _normalize_slug(raw.get("faction_id", "")) or None,
        "tags": list(_normalize_tags(raw.get("tags", []))),
    }
    return normalized, tuple(warnings)


def build_template_from_payload(payload: Mapping[str, object] | None) -> tuple[QuestTemplate | None, tuple[str, ...]]:
    normalized, warnings = normalize_template_payload(payload)
    slug = _normalize_slug(normalized.get("slug", ""))
    if not slug:
        return None, tuple(warnings)

    objective_payload = normalized.get("objective", {})
    objective_payload_map = objective_payload if isinstance(objective_payload, Mapping) else {}
    objective_kind_value = str(objective_payload_map.get("kind", QuestObjectiveKind.HUNT.value) or QuestObjectiveKind.HUNT.value)
    try:
        objective_kind = QuestObjectiveKind(objective_kind_value)
    except Exception:
        objective_kind = QuestObjectiveKind.HUNT
    objective = QuestObjective(
        kind=objective_kind,
        target_key=_normalize_slug(objective_payload_map.get("target_key", "any_hostile")) or "any_hostile",
        target_count=_normalize_int(objective_payload_map.get("target_count", 1), default=1, minimum=1),
    )

    template = QuestTemplate(
        slug=slug,
        title=str(normalized.get("title", slug.replace("_", " ").title())),
        objective=objective,
        reward_xp=_normalize_int(normalized.get("reward_xp", 0), default=0, minimum=0),
        reward_money=_normalize_int(normalized.get("reward_money", 0), default=0, minimum=0),
        status=str(normalized.get("status", "available") or "available"),
        default_progress=_normalize_int(normalized.get("default_progress", 0), default=0, minimum=0),
        expires_days=_normalize_int(normalized.get("expires_days", 5), default=5, minimum=1),
        cataclysm_pushback=bool(normalized.get("cataclysm_pushback", False)),
        pushback_tier=_normalize_int(normalized.get("pushback_tier", 0), default=0, minimum=0),
        requires_alliance_reputation=_normalize_int(
            normalized.get("requires_alliance_reputation", 0), default=0, minimum=0
        ),
        requires_alliance_count=_normalize_int(normalized.get("requires_alliance_count", 0), default=0, minimum=0),
        is_apex_objective=bool(normalized.get("is_apex_objective", False)),
        faction_id=str(normalized.get("faction_id", "") or "") or None,
        tags=_normalize_tags(normalized.get("tags", [])),
    )
    return template, tuple(warnings)


def payload_from_template(template: QuestTemplate) -> dict[str, object]:
    return {
        "template_version": QUEST_TEMPLATE_SCHEMA_VERSION,
        "slug": str(template.slug),
        "title": str(template.title),
        "objective": {
            "kind": template.objective.kind.value,
            "target_key": str(template.objective.target_key),
            "target_count": int(template.objective.target_count),
        },
        "reward_xp": int(template.reward_xp),
        "reward_money": int(template.reward_money),
        "status": str(template.status),
        "default_progress": int(template.default_progress),
        "expires_days": int(template.expires_days),
        "cataclysm_pushback": bool(template.cataclysm_pushback),
        "pushback_tier": int(template.pushback_tier),
        "requires_alliance_reputation": int(template.requires_alliance_reputation),
        "requires_alliance_count": int(template.requires_alliance_count),
        "is_apex_objective": bool(template.is_apex_objective),
        "faction_id": str(template.faction_id or "") or None,
        "tags": [str(tag) for tag in tuple(template.tags or ()) if str(tag).strip()],
    }
