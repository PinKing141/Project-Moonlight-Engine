from typing import Dict, List, Optional

from rpg.domain.models.character import Character
from rpg.domain.repositories import CharacterRepository


class InMemoryCharacterRepository(CharacterRepository):
    def __init__(self):
        self._characters: Dict[int, Character] = {}

    def get(self, character_id: int) -> Optional[Character]:
        return self._characters.get(character_id)

    def list_all(self) -> List[Character]:
        return list(self._characters.values())

    def save(self, character: Character) -> None:
        if character.id is None:
            return
        self._characters[character.id] = character

    def find_by_location(self, location_id: int) -> List[Character]:
        return [c for c in self._characters.values() if c.location_id == location_id]

    def create(self, character: Character, location_id: int) -> Character:
        next_id = max(self._characters.keys(), default=0) + 1
        character.id = next_id
        character.location_id = location_id
        self._characters[next_id] = character
        return character
