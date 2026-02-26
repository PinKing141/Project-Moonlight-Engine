from __future__ import annotations

from dataclasses import dataclass


VALID_GROWTH_CHOICES: tuple[str, ...] = ("vitality", "feat", "spell")


@dataclass(frozen=True)
class ExperiencePoints:
    value: int

    def __post_init__(self) -> None:
        if int(self.value) < 0:
            raise ValueError("Experience points cannot be negative")


@dataclass(frozen=True)
class Level:
    value: int

    def __post_init__(self) -> None:
        if int(self.value) < 1:
            raise ValueError("Level must be at least 1")


@dataclass(frozen=True)
class GrowthChoice:
    kind: str
    option: str | None = None


def normalize_growth_choice(raw_choice: str | None, *, option: str | None = None) -> GrowthChoice:
    normalized = str(raw_choice or "vitality").strip().lower()
    if normalized not in VALID_GROWTH_CHOICES:
        raise ValueError(f"Unsupported growth choice: {raw_choice}")
    return GrowthChoice(kind=normalized, option=(str(option).strip() if option is not None else None))
