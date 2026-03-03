import sys
from pathlib import Path
import unittest
from typing import Any, cast

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.dtos import (
    ActionResult,
    SellInventoryView,
    SellItemView,
    ShopItemView,
    ShopView,
    TownView,
    TrainingOptionView,
    TrainingView,
)
from rpg.application.services.game_service import GameService
from rpg.domain.models.character import Character
from rpg.infrastructure.db.inmemory.repos import InMemoryCharacterRepository


class _TownEconomyStub:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def get_town_view_intent(self, character_id: int) -> TownView:
        self.calls.append(("get_town_view_intent", character_id))
        return TownView(
            day=1,
            threat_level=1,
            location_name="Stub Town",
            npcs=[],
            consequences=[],
            district_tag="",
            landmark_tag="",
            active_prep_summary="",
        )

    def get_shop_view_intent(self, character_id: int) -> ShopView:
        self.calls.append(("get_shop_view_intent", character_id))
        return ShopView(
            gold=10,
            price_modifier_label="neutral",
            items=[ShopItemView(item_id="torch", name="Torch", description="", price=2, can_buy=True)],
        )

    def buy_shop_item_intent(self, character_id: int, item_id: str) -> ActionResult:
        self.calls.append(("buy_shop_item_intent", character_id, item_id))
        return ActionResult(messages=["buy stub"], game_over=False)

    def get_sell_inventory_view_intent(self, character_id: int) -> SellInventoryView:
        self.calls.append(("get_sell_inventory_view_intent", character_id))
        return SellInventoryView(gold=12, items=[SellItemView(name="Torch", price=1, equipped=False)], empty_state_hint="")

    def sell_inventory_item_intent(self, character_id: int, item_name: str) -> ActionResult:
        self.calls.append(("sell_inventory_item_intent", character_id, item_name))
        return ActionResult(messages=["sell stub"], game_over=False)

    def get_training_view_intent(self, character_id: int) -> TrainingView:
        self.calls.append(("get_training_view_intent", character_id))
        return TrainingView(
            gold=8,
            options=[
                TrainingOptionView(
                    training_id="drill",
                    title="Drill",
                    cost=4,
                    unlocked=False,
                    can_buy=True,
                    effect_summary="",
                    availability_note="",
                )
            ],
        )

    def purchase_training_intent(self, character_id: int, training_id: str) -> ActionResult:
        self.calls.append(("purchase_training_intent", character_id, training_id))
        return ActionResult(messages=["training stub"], game_over=False)


class V17TownEconomyFacadeDelegationTests(unittest.TestCase):
    def test_town_economy_intents_delegate_to_bounded_service(self) -> None:
        character_repo = InMemoryCharacterRepository({1: Character(id=1, name="Tester")})
        service = GameService(character_repo=character_repo)
        stub = _TownEconomyStub()
        cast(Any, service).town_economy_app_service = stub

        town = service.get_town_view_intent(1)
        shop = service.get_shop_view_intent(1)
        buy = service.buy_shop_item_intent(1, "torch")
        sell_view = service.get_sell_inventory_view_intent(1)
        sell = service.sell_inventory_item_intent(1, "Torch")
        training_view = service.get_training_view_intent(1)
        training = service.purchase_training_intent(1, "drill")

        self.assertEqual("Stub Town", town.location_name)
        self.assertEqual("Torch", shop.items[0].name)
        self.assertEqual(["buy stub"], list(buy.messages))
        self.assertEqual("Torch", sell_view.items[0].name)
        self.assertEqual(["sell stub"], list(sell.messages))
        self.assertEqual("Drill", training_view.options[0].title)
        self.assertEqual(["training stub"], list(training.messages))

        self.assertIn(("get_town_view_intent", 1), stub.calls)
        self.assertIn(("get_shop_view_intent", 1), stub.calls)
        self.assertIn(("buy_shop_item_intent", 1, "torch"), stub.calls)
        self.assertIn(("get_sell_inventory_view_intent", 1), stub.calls)
        self.assertIn(("sell_inventory_item_intent", 1, "Torch"), stub.calls)
        self.assertIn(("get_training_view_intent", 1), stub.calls)
        self.assertIn(("purchase_training_intent", 1, "drill"), stub.calls)


if __name__ == "__main__":
    unittest.main()
