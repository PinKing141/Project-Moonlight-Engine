import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.infrastructure.inmemory.inmemory_entity_repo import InMemoryEntityRepository


class _FakeEntityNameGenerator:
    def generate_entity_name(self, default_name, kind=None, faction_id=None, entity_id=None, level=None):
        if kind == "humanoid":
            return f"NPC-{entity_id}"
        return default_name


class InMemoryEntityNameGenerationTests(unittest.TestCase):
    def test_humanoid_entities_can_be_renamed_by_generator(self) -> None:
        repo = InMemoryEntityRepository(name_generator=_FakeEntityNameGenerator())

        goblin = repo.get(1)
        wolf = repo.get(2)

        self.assertEqual("NPC-1", goblin.name)
        self.assertEqual("Wolf", wolf.name)


if __name__ == "__main__":
    unittest.main()
