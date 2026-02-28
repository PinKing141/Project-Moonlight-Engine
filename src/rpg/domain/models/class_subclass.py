from dataclasses import dataclass


@dataclass(frozen=True)
class ClassSubclass:
    slug: str
    name: str
    description: str
