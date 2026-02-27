from typing import Dict, List, Optional

from rpg.domain.models.location import Location
from rpg.domain.repositories import LocationRepository

try:
    from rpg.infrastructure.inmemory.generated_taklamakan_locations import GENERATED_LOCATIONS
except Exception:
    GENERATED_LOCATIONS = {}


class InMemoryLocationRepository(LocationRepository):
    def __init__(self, locations: Optional[Dict[int, Location]] = None):
        if locations is not None:
            self._locations = dict(locations)
            return

        if GENERATED_LOCATIONS:
            self._locations = dict(GENERATED_LOCATIONS)
            return

        self._locations = {
            1: Location(id=1, name="Starting Town", biome="village", base_level=1, recommended_level=1)
        }

    def get(self, location_id: int) -> Optional[Location]:
        return self._locations.get(location_id)

    def list_all(self) -> List[Location]:
        return list(self._locations.values())

    def get_starting_location(self) -> Optional[Location]:
        if 1 in self._locations:
            return self._locations[1]
        if not self._locations:
            return None
        first_id = sorted(self._locations.keys())[0]
        return self._locations[first_id]

    # convenience for UI compatibility
    def get_by_id(self, location_id: int) -> Optional[Location]:
        return self.get(location_id)
