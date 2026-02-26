import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.event_bus import EventBus
from rpg.application.services.game_service import GameService
from rpg.application.services.world_progression import WorldProgression
from rpg.domain.models.character import Character
from rpg.domain.models.location import Location
from rpg.infrastructure.db.inmemory.repos import (
    InMemoryCharacterRepository,
    InMemoryEntityRepository,
    InMemoryLocationRepository,
    InMemoryWorldRepository,
)


class _CharacterRepoWithShop(InMemoryCharacterRepository):
    def list_shop_items(self, *, character_id: int, max_items: int = 8) -> list[dict[str, object]]:
        _ = character_id, max_items
        return [
            {
                "id": "canonical_item_101",
                "name": "Moonlit Blade",
                "description": "Canonical equipment (Req Lv 2).",
                "base_price": 12,
            }
        ]


class ShopCanonicalItemsTests(unittest.TestCase):
    def test_shop_merges_dynamic_canonical_items(self) -> None:
        event_bus = EventBus()
        world_repo = InMemoryWorldRepository(seed=2)
        character = Character(id=1, name="Arin", level=2, money=20, location_id=1)
        char_repo = _CharacterRepoWithShop({1: character})
        entity_repo = InMemoryEntityRepository([])
        location_repo = InMemoryLocationRepository({1: Location(id=1, name="Town")})
        progression = WorldProgression(world_repo, entity_repo, event_bus)

        service = GameService(
            character_repo=char_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
            progression=progression,
        )

        shop = service.get_shop_view_intent(1)
        ids = [item.item_id for item in shop.items]
        names = [item.name for item in shop.items]

        self.assertIn("canonical_item_101", ids)
        self.assertIn("Moonlit Blade", names)


if __name__ == "__main__":
    unittest.main()
