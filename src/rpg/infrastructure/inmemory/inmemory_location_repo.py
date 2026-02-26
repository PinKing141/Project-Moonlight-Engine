from typing import List, Optional

from rpg.domain.models.location import Location
from rpg.domain.repositories import LocationRepository


class InMemoryLocationRepository(LocationRepository):
    def __init__(self):
        self._locations = {
            1: Location(id=1, name="Starting Town", biome="village", base_level=1, recommended_level=1)
        }

    def get(self, location_id: int) -> Optional[Location]:
        return self._locations.get(location_id)

    def list_all(self) -> List[Location]:
        return list(self._locations.values())

    def get_starting_location(self) -> Optional[Location]:
        return self._locations.get(1)

    # convenience for UI compatibility
    def get_by_id(self, location_id: int) -> Optional[Location]:
        return self.get(location_id)
