from __future__ import annotations

from typing import TYPE_CHECKING

from rpg.application.dtos import ActionResult

if TYPE_CHECKING:
    from rpg.application.services.game_service import GameService


class PartyApplicationService:
    def __init__(self, game_service: GameService) -> None:
        self._game_service = game_service

    def get_party_status_intent(self, character_id: int) -> list[str]:
        return self._game_service._get_party_status_intent_impl(character_id)

    def get_party_capacity_intent(self, character_id: int) -> tuple[int, int]:
        return self._game_service._get_party_capacity_intent_impl(character_id)

    def get_party_management_intent(self, character_id: int) -> list[dict[str, str | bool]]:
        return self._game_service._get_party_management_intent_impl(character_id)

    def set_party_companion_active_intent(self, character_id: int, companion_id: str, active: bool) -> ActionResult:
        return self._game_service._set_party_companion_active_intent_impl(character_id, companion_id, active)

    def set_party_companion_lane_intent(self, character_id: int, companion_id: str, lane: str) -> ActionResult:
        return self._game_service._set_party_companion_lane_intent_impl(character_id, companion_id, lane)
