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
from rpg.infrastructure.inmemory.inmemory_faction_repo import InMemoryFactionRepository


class EconomyIdentityFlowTests(unittest.TestCase):
    def _build_service(self, money: int = 20):
        event_bus = EventBus()
        world_repo = InMemoryWorldRepository(seed=21)
        character = Character(id=501, name="Arden", location_id=1, money=money)
        character_repo = InMemoryCharacterRepository({character.id: character})
        entity_repo = InMemoryEntityRepository([])
        location_repo = InMemoryLocationRepository({1: Location(id=1, name="Town")})
        faction_repo = InMemoryFactionRepository()
        progression = WorldProgression(world_repo, entity_repo, event_bus)

        service = GameService(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
            progression=progression,
            faction_repo=faction_repo,
        )
        return service, character_repo, faction_repo, character.id

    def test_shop_price_changes_with_faction_standing(self):
        neutral_service, _neutral_chars, _neutral_factions, character_id = self._build_service()
        neutral_shop = neutral_service.get_shop_view_intent(character_id)
        neutral_price = next(item.price for item in neutral_shop.items if item.item_id == "healing_herbs")

        service, _char_repo, faction_repo, character_id = self._build_service()
        wardens = faction_repo.get("wardens")
        wardens.adjust_reputation(f"character:{character_id}", 6)
        faction_repo.save(wardens)

        discounted_shop = service.get_shop_view_intent(character_id)
        discounted_price = next(item.price for item in discounted_shop.items if item.item_id == "healing_herbs")
        self.assertLess(discounted_price, neutral_price)

    def test_buying_shop_item_spends_gold_and_adds_inventory(self):
        service, character_repo, _faction_repo, character_id = self._build_service(money=20)

        result = service.buy_shop_item_intent(character_id, "sturdy_rations")
        updated = character_repo.get(character_id)

        self.assertIn("Purchased", " ".join(result.messages))
        self.assertLess(updated.money, 20)
        self.assertIn("Sturdy Rations", updated.inventory)

    def test_training_unlock_adds_new_broker_interaction_option(self):
        service, character_repo, _faction_repo, character_id = self._build_service(money=25)

        before = service.get_npc_interaction_intent(character_id, "broker_silas")
        self.assertNotIn("Leverage Intel", before.approaches)

        outcome = service.purchase_training_intent(character_id, "streetwise_briefing")
        after = service.get_npc_interaction_intent(character_id, "broker_silas")
        updated = character_repo.get(character_id)

        self.assertIn("Training complete", " ".join(outcome.messages))
        self.assertIn("Leverage Intel", after.approaches)
        self.assertLess(updated.money, 25)

    def test_second_training_requires_faction_standing(self):
        service, _character_repo, _faction_repo, character_id = self._build_service(money=25)

        training = service.get_training_view_intent(character_id)
        watch_option = next(item for item in training.options if item.training_id == "watch_liaison_drills")
        self.assertFalse(watch_option.can_buy)
        self.assertIn("reputation", watch_option.availability_note)

        blocked = service.purchase_training_intent(character_id, "watch_liaison_drills")
        self.assertIn("requires wardens reputation", " ".join(blocked.messages).lower())

    def test_second_training_unlock_adds_captain_interaction_option(self):
        service, character_repo, faction_repo, character_id = self._build_service(money=30)
        wardens = faction_repo.get("wardens")
        wardens.adjust_reputation(f"character:{character_id}", 5)
        faction_repo.save(wardens)

        before = service.get_npc_interaction_intent(character_id, "captain_ren")
        self.assertNotIn("Call In Favor", before.approaches)

        outcome = service.purchase_training_intent(character_id, "watch_liaison_drills")
        after = service.get_npc_interaction_intent(character_id, "captain_ren")
        updated = character_repo.get(character_id)

        self.assertIn("Training complete", " ".join(outcome.messages))
        self.assertIn("Call In Favor", after.approaches)
        self.assertLess(updated.money, 30)

    def test_sell_inventory_item_increases_gold_and_removes_item(self):
        service, character_repo, _faction_repo, character_id = self._build_service(money=5)
        hero = character_repo.get(character_id)
        hero.inventory = ["Sturdy Rations"]
        character_repo.save(hero)

        quote = service.get_sell_inventory_view_intent(character_id)
        quoted_price = next(row.price for row in quote.items if row.name == "Sturdy Rations")

        result = service.sell_inventory_item_intent(character_id, "Sturdy Rations")
        updated = character_repo.get(character_id)

        self.assertIn("Sold Sturdy Rations", " ".join(result.messages))
        self.assertEqual(5 + quoted_price, updated.money)
        self.assertNotIn("Sturdy Rations", updated.inventory)

    def test_selling_equipped_item_auto_unequips_last_copy(self):
        service, character_repo, _faction_repo, character_id = self._build_service(money=4)
        hero = character_repo.get(character_id)
        hero.inventory = ["Longsword"]
        character_repo.save(hero)
        service.equip_inventory_item_intent(character_id, "Longsword")

        result = service.sell_inventory_item_intent(character_id, "Longsword")
        updated = character_repo.get(character_id)

        self.assertNotIn("Longsword", updated.inventory)
        self.assertNotIn("weapon", updated.flags.get("equipment", {}))
        self.assertIn("automatically unequipped", " ".join(result.messages).lower())


if __name__ == "__main__":
    unittest.main()
