import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.game_service import GameService
from rpg.domain.models.character import Character
from rpg.infrastructure.inmemory.inmemory_character_repo import InMemoryCharacterRepository
from rpg.infrastructure.inmemory.inmemory_class_repo import InMemoryClassRepository
from rpg.infrastructure.inmemory.inmemory_entity_repo import InMemoryEntityRepository
from rpg.infrastructure.inmemory.inmemory_location_repo import InMemoryLocationRepository
from rpg.infrastructure.inmemory.inmemory_world_repo import InMemoryWorldRepository
from rpg.infrastructure.inmemory.atomic_persistence import create_inmemory_atomic_persistor


class SnapshotIntentTests(unittest.TestCase):
    def test_create_and_load_snapshot_restores_world_and_character_state(self) -> None:
        character_repo = InMemoryCharacterRepository()
        world_repo = InMemoryWorldRepository(seed=23)
        service = GameService(
            character_repo,
            class_repo=InMemoryClassRepository(),
            entity_repo=InMemoryEntityRepository(),
            location_repo=InMemoryLocationRepository(),
            world_repo=world_repo,
            atomic_state_persistor=create_inmemory_atomic_persistor(character_repo, world_repo),
        )

        created = character_repo.create(
            Character(id=None, name="Arin", class_name="fighter", hp_current=10, hp_max=10, attributes={}),
            location_id=1,
        )
        assert created.id is not None

        first = service.create_snapshot_intent("baseline")
        self.assertTrue(str(first.get("snapshot_id", "")).startswith("snapshot-"))

        created.hp_current = 2
        character_repo.save(created)
        world = world_repo.load_default()
        assert world is not None
        world.current_turn = 7
        world_repo.save(world)

        loaded = service.load_snapshot_intent(str(first["snapshot_id"]))
        self.assertFalse(loaded.game_over)

        restored = character_repo.get(created.id)
        assert restored is not None
        self.assertEqual(10, restored.hp_current)

        restored_world = world_repo.load_default()
        assert restored_world is not None
        self.assertEqual(0, restored_world.current_turn)

    def test_list_snapshots_returns_latest_first(self) -> None:
        service = GameService(
            InMemoryCharacterRepository(),
            class_repo=InMemoryClassRepository(),
            entity_repo=InMemoryEntityRepository(),
            location_repo=InMemoryLocationRepository(),
            world_repo=InMemoryWorldRepository(seed=9),
        )

        first = service.create_snapshot_intent("first")
        second = service.create_snapshot_intent("second")

        rows = service.list_snapshots_intent()
        self.assertEqual(str(second["snapshot_id"]), rows[0]["snapshot_id"])
        self.assertEqual(str(first["snapshot_id"]), rows[1]["snapshot_id"])


if __name__ == "__main__":
    unittest.main()
