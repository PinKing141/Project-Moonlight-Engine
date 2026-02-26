from __future__ import annotations

import copy
from collections.abc import Callable, Sequence

from rpg.domain.models.character import Character
from rpg.domain.models.world import World


def create_inmemory_atomic_persistor(character_repo, world_repo) -> Callable[..., None]:
    def _persist(
        character: Character,
        world: World,
        operations: Sequence[Callable[[object], None]] | None = None,
    ) -> None:
        snapshot = {
            "characters": copy.deepcopy(getattr(character_repo, "_characters", {})),
            "world": copy.deepcopy(getattr(world_repo, "_world", None)),
            "world_flags": copy.deepcopy(getattr(world_repo, "_world_flags", None)),
            "world_history": copy.deepcopy(getattr(world_repo, "_world_history", None)),
            "progression_unlocks": copy.deepcopy(getattr(character_repo, "_progression_unlocks", None)),
        }
        try:
            character_repo.save(character)
            world_repo.save(world)
            for operation in operations or ():
                operation(None)
        except Exception:
            if hasattr(character_repo, "_characters"):
                character_repo._characters = snapshot["characters"]
            if hasattr(world_repo, "_world"):
                world_repo._world = snapshot["world"]
            if snapshot.get("world_flags") is not None and hasattr(world_repo, "_world_flags"):
                world_repo._world_flags = snapshot["world_flags"]
            if snapshot.get("world_history") is not None and hasattr(world_repo, "_world_history"):
                world_repo._world_history = snapshot["world_history"]
            if snapshot.get("progression_unlocks") is not None and hasattr(character_repo, "_progression_unlocks"):
                character_repo._progression_unlocks = snapshot["progression_unlocks"]
            raise

    return _persist
