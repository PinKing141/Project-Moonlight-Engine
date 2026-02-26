import random

from rpg.domain.models.world import World
from rpg.domain.repositories import WorldRepository


class InMemoryWorldRepository(WorldRepository):
    def __init__(self, seed: int | None = None) -> None:
        resolved_seed = int(seed) if seed is not None else random.SystemRandom().randint(1, 2_147_483_647)
        self._world = World(id=1, name="Default World", rng_seed=resolved_seed)

    def load_default(self) -> World | None:
        return self._world

    def save(self, world: World) -> None:
        self._world = world
