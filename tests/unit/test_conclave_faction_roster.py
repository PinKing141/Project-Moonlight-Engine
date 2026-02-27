import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.infrastructure.inmemory.inmemory_faction_repo import InMemoryFactionRepository


class ConclaveFactionRosterTests(unittest.TestCase):
    def test_inmemory_roster_contains_conclave_and_towers(self) -> None:
        repo = InMemoryFactionRepository()
        ids = {faction.id for faction in repo.list_all()}

        expected = {
            "conclave_council",
            "tower_crimson",
            "tower_cobalt",
            "tower_emerald",
            "tower_aurelian",
            "tower_obsidian",
            "tower_alabaster",
        }

        self.assertTrue(expected.issubset(ids))


if __name__ == "__main__":
    unittest.main()
