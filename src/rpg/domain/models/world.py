from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class World:
    id: int
    name: str
    current_turn: int = 0
    threat_level: int = 0
    flags: Dict[str, Any] = field(default_factory=dict)
    rng_seed: int = 1

    def advance_turns(self, ticks: int = 1) -> None:
        self.current_turn += ticks
