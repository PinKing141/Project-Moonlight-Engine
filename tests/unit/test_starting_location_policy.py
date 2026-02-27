import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.domain.models.location import Location
from rpg.infrastructure.inmemory.inmemory_location_repo import InMemoryLocationRepository


class StartingLocationPolicyTests(unittest.TestCase):
    def test_inmemory_starting_location_prefers_town_over_lower_non_town_id(self) -> None:
        repo = InMemoryLocationRepository(
            {
                1: Location(id=1, name="Shattered Expanse", biome="wilderness"),
                2: Location(id=2, name="Ironbarren Town", biome="forest"),
            }
        )

        starting = repo.get_starting_location()

        self.assertIsNotNone(starting)
        self.assertEqual(2, starting.id)


if __name__ == "__main__":
    unittest.main()
