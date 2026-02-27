import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.domain.models.character import Character
from rpg.domain.models.world import World
from rpg.infrastructure.inmemory.atomic_persistence import create_inmemory_atomic_persistor


class _StubCharacterRepo:
    def __init__(self) -> None:
        self._characters = {}

    def save(self, character: Character) -> None:
        if character.id is not None:
            self._characters[int(character.id)] = character


class _StubWorldRepo:
    def __init__(self) -> None:
        self._world = World(id=1, name="Stub", current_turn=0, threat_level=0, flags={})
        self._world_flags = {}
        self._world_history = []

    def save(self, world: World) -> None:
        self._world = world


class InMemoryAtomicPersistenceTests(unittest.TestCase):
    def test_operations_receive_non_none_session_object(self) -> None:
        character_repo = _StubCharacterRepo()
        world_repo = _StubWorldRepo()
        persistor = create_inmemory_atomic_persistor(character_repo, world_repo)

        seen = {"dialect": None}

        def operation(session) -> None:
            seen["dialect"] = getattr(getattr(getattr(session, "bind", None), "dialect", None), "name", None)

        character = Character(id=1, name="Ari", hp_current=10, hp_max=10)
        world = World(id=1, name="Stub", current_turn=1, threat_level=0, flags={})

        persistor(character, world, operations=[operation])

        self.assertEqual("inmemory", seen["dialect"])


if __name__ == "__main__":
    unittest.main()
