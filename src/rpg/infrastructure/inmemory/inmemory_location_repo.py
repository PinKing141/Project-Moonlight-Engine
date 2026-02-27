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
        if 1 in self._locations and self._is_town_like(self._locations[1]):
            return self._locations[1]
        ordered = [self._locations[key] for key in sorted(self._locations.keys())]
        town_candidate = next((location for location in ordered if self._is_town_like(location)), None)
        if town_candidate is not None:
            return town_candidate
        if 1 in self._locations:
            return self._locations[1]
        if not self._locations:
            return None
        first_id = sorted(self._locations.keys())[0]
        return self._locations[first_id]

    @staticmethod
    def _is_town_like(location: Location | None) -> bool:
        if location is None:
            return False
        name = str(getattr(location, "name", "") or "").lower()
        biome = str(getattr(location, "biome", "") or "").lower()
        tags = [str(tag).lower() for tag in getattr(location, "tags", []) or []]
        haystack = " ".join([name, biome] + tags)
        town_tokens = ("town", "village", "city", "square", "settlement")
        return any(token in haystack for token in town_tokens)

    # convenience for UI compatibility
    def get_by_id(self, location_id: int) -> Optional[Location]:
        return self.get(location_id)
