from __future__ import annotations

from typing import TYPE_CHECKING

from rpg.application.dtos import ActionResult, SellInventoryView, ShopView, TownView, TrainingView

if TYPE_CHECKING:
    from rpg.application.services.game_service import GameService


class TownEconomyApplicationService:
    def __init__(self, game_service: GameService) -> None:
        self._game_service = game_service

    def get_town_view_intent(self, character_id: int) -> TownView:
        return self._game_service._get_town_view_intent_impl(character_id)

    def get_shop_view_intent(self, character_id: int) -> ShopView:
        return self._game_service._get_shop_view_intent_impl(character_id)

    def buy_shop_item_intent(self, character_id: int, item_id: str) -> ActionResult:
        return self._game_service._buy_shop_item_intent_impl(character_id, item_id)

    def get_sell_inventory_view_intent(self, character_id: int) -> SellInventoryView:
        return self._game_service._get_sell_inventory_view_intent_impl(character_id)

    def sell_inventory_item_intent(self, character_id: int, item_name: str) -> ActionResult:
        return self._game_service._sell_inventory_item_intent_impl(character_id, item_name)

    def get_training_view_intent(self, character_id: int) -> TrainingView:
        return self._game_service._get_training_view_intent_impl(character_id)

    def purchase_training_intent(self, character_id: int, training_id: str) -> ActionResult:
        return self._game_service._purchase_training_intent_impl(character_id, training_id)
