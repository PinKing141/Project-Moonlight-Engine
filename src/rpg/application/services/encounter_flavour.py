import random

from rpg.domain.models.entity import Entity

BEAST_ENCOUNTER_INTROS = [
    "You hear rustling in the undergrowth as a {name} stalks closer.",
    "A low growl turns your blood cold — a {name} emerges from the shadows.",
]

UNDEAD_ENCOUNTER_INTROS = [
    "The air chills as a {name} drags itself towards you.",
    "Bones clatter and a {name} shambles into view.",
]

HUMANOID_ENCOUNTER_INTROS = [
    "A {name} steps into your path, weapons drawn.",
    "You catch a glimpse of steel — a hostile {name} confronts you.",
]

DEFAULT_INTROS = [
    "You run into a {name}.",
    "A sudden noise reveals a {name}.",
]


def random_intro(enemy: Entity, *, seed: int | None = None, rng: random.Random | None = None) -> str:
    kind = getattr(enemy, "kind", "beast")
    if kind == "beast":
        pool = BEAST_ENCOUNTER_INTROS
    elif kind == "undead":
        pool = UNDEAD_ENCOUNTER_INTROS
    elif kind == "humanoid":
        pool = HUMANOID_ENCOUNTER_INTROS
    else:
        pool = DEFAULT_INTROS

    resolved_rng = rng or (random.Random(int(seed)) if seed is not None else random.Random())
    template = resolved_rng.choice(pool)
    return template.format(name=enemy.name)
