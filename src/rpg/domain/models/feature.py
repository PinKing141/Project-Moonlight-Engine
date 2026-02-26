from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Feature:
    id: int | None
    slug: str
    name: str
    trigger_key: str
    effect_kind: str
    effect_value: int
    source: str = "db"
