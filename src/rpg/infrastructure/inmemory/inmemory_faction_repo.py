from __future__ import annotations

from typing import Dict, List, Optional

from rpg.domain.models.faction import Faction
from rpg.domain.repositories import FactionRepository


class InMemoryFactionRepository(FactionRepository):
    def __init__(self) -> None:
        self._factions: Dict[str, Faction] = {
            "wild": Faction(id="wild", name="Wild Tribes", influence=2, alignment="chaotic"),
            "undead": Faction(id="undead", name="Restless Dead", influence=3, alignment="evil"),
            "wardens": Faction(id="wardens", name="Emerald Wardens", influence=1, alignment="neutral"),
        }

    def get(self, faction_id: str) -> Optional[Faction]:
        return self._factions.get(faction_id)

    def list_all(self) -> List[Faction]:
        return list(self._factions.values())

    def save(self, faction: Faction) -> None:
        self._factions[faction.id] = faction
