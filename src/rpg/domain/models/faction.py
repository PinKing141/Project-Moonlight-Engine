from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Faction:
    id: str
    name: str
    influence: int = 0
    alignment: str = "neutral"
    tags: List[str] = field(default_factory=list)
    rivalries: Dict[str, int] = field(default_factory=dict)
    allies: List[str] = field(default_factory=list)
    description: str = ""
    reputation: Dict[str, int] = field(default_factory=dict)
    home_location_id: Optional[int] = None

    def adjust_reputation(self, target: str, delta: int) -> int:
        """Update reputation towards another faction or character."""

        self.reputation[target] = self.reputation.get(target, 0) + delta
        return self.reputation[target]

    def attitude_towards(self, target: str) -> str:
        """Return a coarse-grained sentiment for UI and encounter biasing."""

        score = self.reputation.get(target, 0)
        if score >= 20:
            return "allied"
        if score >= 5:
            return "friendly"
        if score <= -20:
            return "hostile"
        if score <= -5:
            return "unfriendly"
        return "neutral"
