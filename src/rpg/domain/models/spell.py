from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class Spell:
    slug: str
    name: str
    level_int: int
    school: Optional[str] = None
    casting_time: Optional[str] = None
    range_text: Optional[str] = None
    duration: Optional[str] = None
    components: Optional[str] = None
    concentration: bool = False
    ritual: bool = False
    desc_text: Optional[str] = None
    higher_level: Optional[str] = None
    classes: Optional[List[str]] = None
