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