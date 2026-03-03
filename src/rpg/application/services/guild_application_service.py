from __future__ import annotations

from typing import TYPE_CHECKING

from rpg.application.dtos import ActionResult, GuildBoardView, GuildPromotionCheckView, GuildStatusView

if TYPE_CHECKING:
    from rpg.application.services.game_service import GameService


class GuildApplicationService:
    def __init__(self, game_service: GameService) -> None:
        self._game_service = game_service

    def get_guild_status_intent(self, character_id: int) -> GuildStatusView:
        return self._game_service._get_guild_status_intent_impl(character_id)

    def get_guild_board_intent(self, character_id: int, region: str | None = None) -> GuildBoardView:
        return self._game_service._get_guild_board_intent_impl(character_id, region=region)

    def accept_guild_contract_intent(self, character_id: int, contract_id: str, region: str | None = None) -> ActionResult:
        return self._game_service._accept_guild_contract_intent_impl(character_id, contract_id, region=region)

    def turn_in_guild_contract_intent(self, character_id: int, contract_id: str, success: bool = True) -> ActionResult:
        return self._game_service._turn_in_guild_contract_intent_impl(character_id, contract_id, success=success)

    def check_guild_promotion_intent(self, character_id: int, apply_if_eligible: bool = False) -> GuildPromotionCheckView:
        return self._game_service._check_guild_promotion_intent_impl(character_id, apply_if_eligible=apply_if_eligible)
