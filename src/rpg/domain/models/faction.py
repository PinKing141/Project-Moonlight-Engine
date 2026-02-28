from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from rpg.domain.models.character import CharacterAlignment


class InfluenceThreshold(str, Enum):
    HOSTILE = "hostile"
    NEUTRAL = "neutral"
    FRIENDLY = "friendly"
    REVERED = "revered"


@dataclass(frozen=True)
class Reputation:
    score: int = 0

    @property
    def threshold(self) -> InfluenceThreshold:
        return reputation_threshold(self.score)


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
    alignment_affinities: Dict[str, int] = field(default_factory=dict)

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

    def alignment_affinity_delta(self, character_alignment: str | None) -> int:
        normalized = CharacterAlignment.normalize(character_alignment)
        direct = self.alignment_affinities.get(normalized)
        if direct is not None:
            return int(direct)

        axis_pairs = {
            "lawful_good": ("lawful", "good"),
            "neutral_good": ("neutral_axis", "good"),
            "chaotic_good": ("chaotic", "good"),
            "lawful_neutral": ("lawful", "neutral_moral"),
            "true_neutral": ("neutral_axis", "neutral_moral"),
            "chaotic_neutral": ("chaotic", "neutral_moral"),
            "lawful_evil": ("lawful", "evil"),
            "neutral_evil": ("neutral_axis", "evil"),
            "chaotic_evil": ("chaotic", "evil"),
        }
        axis_tags = axis_pairs.get(normalized, ("neutral_axis", "neutral_moral"))
        total = 0
        for key in axis_tags:
            total += int(self.alignment_affinities.get(key, 0) or 0)
        return int(total)


def reputation_threshold(reputation_score: int) -> InfluenceThreshold:
    score = int(reputation_score)
    if score >= 40:
        return InfluenceThreshold.REVERED
    if score >= 10:
        return InfluenceThreshold.FRIENDLY
    if score <= -10:
        return InfluenceThreshold.HOSTILE
    return InfluenceThreshold.NEUTRAL


def calculate_price_modifier(reputation_score: int) -> int:
    threshold = reputation_threshold(reputation_score)
    if threshold == InfluenceThreshold.REVERED:
        return -25
    if threshold == InfluenceThreshold.FRIENDLY:
        return -10
    if threshold == InfluenceThreshold.HOSTILE:
        return 20
    return 0


def determines_aggro(faction_alignment: str, reputation_score: int) -> bool:
    alignment = str(faction_alignment or "neutral").strip().lower()
    threshold = reputation_threshold(reputation_score)

    if alignment in {"hostile", "aggressive", "evil"}:
        return threshold != InfluenceThreshold.REVERED
    if alignment in {"friendly", "lawful", "ally"}:
        return threshold == InfluenceThreshold.HOSTILE
    return threshold == InfluenceThreshold.HOSTILE
