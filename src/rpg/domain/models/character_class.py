from dataclasses import dataclass, field
from typing import Dict


@dataclass
class CharacterClass:
    id: int | None
    name: str
    slug: str
    hit_die: str = "d8"
    primary_ability: str | None = None
    base_attributes: Dict[str, int] = field(default_factory=dict)
