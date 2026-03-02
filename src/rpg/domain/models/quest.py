from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping


class QuestObjectiveKind(str, Enum):
    HUNT = "hunt"
    GATHER = "gather"
    DELIVER = "deliver"
    TRAVEL = "travel"


@dataclass(frozen=True)
class QuestObjective:
    kind: QuestObjectiveKind
    target_key: str
    target_count: int = 1


@dataclass(frozen=True)
class QuestTemplate:
    slug: str
    title: str
    objective: QuestObjective
    reward_xp: int = 0
    reward_money: int = 0
    status: str = "available"
    default_progress: int = 0
    expires_days: int = 5
    cataclysm_pushback: bool = False
    pushback_tier: int = 0
    requires_alliance_reputation: int = 0
    requires_alliance_count: int = 0
    is_apex_objective: bool = False
    faction_id: str | None = None
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class QuestState:
    template_slug: str
    status: str
    progress: int = 0
    accepted_turn: int = 0
    completed_turn: int | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class QuestEscalationNode:
    offset_days: int
    state: str
    objective_note: str = ""
    urgency_label: str = ""
    target_delta: int = 0
    message: str = ""
    failed_reason: str = ""
    failure_faction_id: str | None = None
    failure_reputation_delta: int = 0


@dataclass(frozen=True)
class QuestEscalationPath:
    expires_days: int = 5
    nodes: tuple[QuestEscalationNode, ...] = ()


QUEST_ESCALATION_PATHS: Mapping[str, QuestEscalationPath] = {
    "forest_path_clearance": QuestEscalationPath(
        expires_days=30,
        nodes=(
            QuestEscalationNode(
                offset_days=14,
                state="escalated",
                objective_note="The goblin camp is fortified and hostages are now at risk.",
                urgency_label="URGENT: Time is running out.",
                target_delta=1,
                message="The goblins have fortified their camp and taken hostages.",
            ),
            QuestEscalationNode(
                offset_days=21,
                state="failed",
                failed_reason="ignored_escalation",
                message="The goblins burn a nearby farm while the contract sits unresolved.",
                failure_faction_id="wardens",
                failure_reputation_delta=-3,
            ),
        ),
    ),
}


QUEST_TEMPLATES: Mapping[str, QuestTemplate] = {
    "first_hunt": QuestTemplate(
        slug="first_hunt",
        title="First Hunt",
        objective=QuestObjective(kind=QuestObjectiveKind.HUNT, target_key="any_hostile", target_count=1),
        reward_xp=10,
        reward_money=5,
    ),
    "trail_patrol": QuestTemplate(
        slug="trail_patrol",
        title="Trail Patrol",
        objective=QuestObjective(kind=QuestObjectiveKind.HUNT, target_key="any_hostile", target_count=2),
        reward_xp=16,
        reward_money=7,
    ),
    "supply_drop": QuestTemplate(
        slug="supply_drop",
        title="Supply Drop",
        objective=QuestObjective(kind=QuestObjectiveKind.TRAVEL, target_key="route_leg", target_count=2),
        reward_xp=12,
        reward_money=8,
    ),
    "crown_hunt_order": QuestTemplate(
        slug="crown_hunt_order",
        title="Crown Hunt Order",
        objective=QuestObjective(kind=QuestObjectiveKind.HUNT, target_key="any_hostile", target_count=2),
        reward_xp=18,
        reward_money=9,
    ),
    "syndicate_route_run": QuestTemplate(
        slug="syndicate_route_run",
        title="Syndicate Route Run",
        objective=QuestObjective(kind=QuestObjectiveKind.TRAVEL, target_key="route_leg", target_count=3),
        reward_xp=16,
        reward_money=10,
    ),
    "forest_path_clearance": QuestTemplate(
        slug="forest_path_clearance",
        title="Forest Path Clearance",
        objective=QuestObjective(kind=QuestObjectiveKind.HUNT, target_key="any_hostile", target_count=3),
        reward_xp=20,
        reward_money=8,
        expires_days=30,
    ),
    "ruins_wayfinding": QuestTemplate(
        slug="ruins_wayfinding",
        title="Ruins Wayfinding",
        objective=QuestObjective(kind=QuestObjectiveKind.TRAVEL, target_key="route_leg", target_count=2),
        reward_xp=14,
        reward_money=9,
    ),
    "cataclysm_scout_front": QuestTemplate(
        slug="cataclysm_scout_front",
        title="Frontline Scout Sweep",
        objective=QuestObjective(kind=QuestObjectiveKind.HUNT, target_key="any_hostile", target_count=3),
        reward_xp=26,
        reward_money=12,
        cataclysm_pushback=True,
        pushback_tier=1,
    ),
    "cataclysm_supply_lines": QuestTemplate(
        slug="cataclysm_supply_lines",
        title="Seal Fractured Supply Lines",
        objective=QuestObjective(kind=QuestObjectiveKind.TRAVEL, target_key="route_leg", target_count=2),
        reward_xp=24,
        reward_money=14,
        cataclysm_pushback=True,
        pushback_tier=1,
    ),
    "cataclysm_alliance_accord": QuestTemplate(
        slug="cataclysm_alliance_accord",
        title="Alliance Accord Muster",
        objective=QuestObjective(kind=QuestObjectiveKind.HUNT, target_key="any_hostile", target_count=4),
        reward_xp=34,
        reward_money=18,
        cataclysm_pushback=True,
        pushback_tier=2,
        requires_alliance_reputation=10,
        requires_alliance_count=2,
    ),
    "cataclysm_apex_clash": QuestTemplate(
        slug="cataclysm_apex_clash",
        title="Apex Clash",
        objective=QuestObjective(kind=QuestObjectiveKind.HUNT, target_key="cataclysm_apex", target_count=1),
        reward_xp=50,
        reward_money=25,
        cataclysm_pushback=True,
        pushback_tier=3,
        is_apex_objective=True,
    ),
}


def quest_template_for(quest_id: str) -> QuestTemplate | None:
    key = str(quest_id or "").strip().lower()
    if not key:
        return None
    return QUEST_TEMPLATES.get(key)


def standard_quest_templates() -> tuple[QuestTemplate, ...]:
    return tuple(template for template in QUEST_TEMPLATES.values() if not bool(template.cataclysm_pushback))


def cataclysm_quest_templates() -> tuple[QuestTemplate, ...]:
    return tuple(template for template in QUEST_TEMPLATES.values() if bool(template.cataclysm_pushback))


def quest_template_objective_kind(template: QuestTemplate) -> str:
    if template.objective.kind == QuestObjectiveKind.TRAVEL:
        return "travel_count"
    return "kill_any"


def quest_payload_from_template(
    template: QuestTemplate,
    *,
    cataclysm_kind: str = "",
    cataclysm_phase: str = "",
) -> dict[str, object]:
    payload: dict[str, object] = {
        "quest_id": str(template.slug),
        "status": str(template.status),
        "objective_kind": quest_template_objective_kind(template),
        "progress": int(template.default_progress),
        "target": max(1, int(template.objective.target_count)),
        "reward_xp": int(template.reward_xp),
        "reward_money": int(template.reward_money),
    }
    if bool(template.cataclysm_pushback):
        payload["cataclysm_pushback"] = True
        payload["pushback_tier"] = max(1, int(template.pushback_tier))
        payload["pushback_focus"] = str(cataclysm_kind or "")
        payload["phase"] = str(cataclysm_phase or "")
    if int(template.requires_alliance_reputation) > 0:
        payload["requires_alliance_reputation"] = int(template.requires_alliance_reputation)
    if int(template.requires_alliance_count) > 0:
        payload["requires_alliance_count"] = int(template.requires_alliance_count)
    if bool(template.is_apex_objective):
        payload["is_apex_objective"] = True
    return payload


def quest_title_for(quest_id: str) -> str:
    template = quest_template_for(quest_id)
    if template is not None:
        return str(template.title)
    return str(quest_id or "").replace("_", " ").title()


def quest_acceptance_block_reason(
    template: QuestTemplate | None,
    *,
    faction_standings: Mapping[str, int] | None = None,
) -> str:
    if template is None:
        return ""

    required_rep = max(0, int(template.requires_alliance_reputation))
    required_count = max(0, int(template.requires_alliance_count))
    if required_rep <= 0 or required_count <= 0:
        return ""

    standings = faction_standings or {}
    qualified = sum(1 for score in standings.values() if int(score) >= required_rep)
    if qualified >= required_count:
        return ""

    return f"This bounty requires alliance standing {required_rep}+ with at least {required_count} factions."


def quest_escalation_path_for(quest_id: str) -> QuestEscalationPath | None:
    key = str(quest_id or "").strip().lower()
    if not key:
        return None
    return QUEST_ESCALATION_PATHS.get(key)


def is_objective_met(
    *,
    objective: QuestObjective,
    inventory_state: Mapping[str, int] | None,
    world_flags: Mapping[str, object] | None,
    progress: int,
) -> bool:
    target = max(int(objective.target_count), 1)
    inventory = inventory_state or {}
    flags = world_flags or {}

    if objective.kind == QuestObjectiveKind.HUNT:
        return int(progress) >= target

    if objective.kind == QuestObjectiveKind.GATHER:
        return int(inventory.get(objective.target_key, 0)) >= target

    if objective.kind == QuestObjectiveKind.DELIVER:
        delivered = int(flags.get(f"delivered:{objective.target_key}", 0) or 0)
        return delivered >= target

    if objective.kind == QuestObjectiveKind.TRAVEL:
        visits = int(flags.get(f"visited:{objective.target_key}", 0) or 0)
        return visits >= target

    return False