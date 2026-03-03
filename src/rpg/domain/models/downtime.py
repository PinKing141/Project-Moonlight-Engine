from dataclasses import dataclass, field


@dataclass(frozen=True)
class DowntimeActivity:
    id: str
    title: str
    description: str
    days: int
    gold_cost: int = 0
    gold_reward: int = 0
    inventory_costs: tuple[str, ...] = ()
    inventory_rewards: tuple[str, ...] = ()
    reputation_deltas: dict[str, int] = field(default_factory=dict)
    activity_family: str = ""


@dataclass(frozen=True)
class DowntimeOutcome:
    activity_id: str
    days_spent: int
    gold_delta: int
    inventory_added: tuple[str, ...]
    inventory_removed: tuple[str, ...]
    reputation_deltas: dict[str, int]
    messages: tuple[str, ...]
