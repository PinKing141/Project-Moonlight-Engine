from __future__ import annotations

from typing import TYPE_CHECKING

from rpg.application.dtos import ActionResult, ExploreView, LocationContextView, TravelDestinationView
from rpg.domain.models.character import Character
from rpg.domain.models.entity import Entity

if TYPE_CHECKING:
    from rpg.application.services.game_service import GameService


class ExplorationApplicationService:
    def __init__(self, game_service: GameService) -> None:
        self._game_service = game_service

    def explore_intent(self, character_id: int) -> tuple[ExploreView, Character, list[Entity]]:
        return self._game_service._explore_intent_impl(character_id)

    def get_location_context_intent(self, character_id: int) -> LocationContextView:
        return self._game_service._get_location_context_intent_impl(character_id)

    def get_travel_destinations_intent(self, character_id: int) -> list[TravelDestinationView]:
        return self._game_service._get_travel_destinations_intent_impl(character_id)

    def travel_intent(
        self,
        character_id: int,
        destination_id: int | None = None,
        travel_mode: str = "road",
        travel_pace: str = "steady",
    ) -> ActionResult:
        return self._game_service._travel_intent_impl(
            character_id,
            destination_id=destination_id,
            travel_mode=travel_mode,
            travel_pace=travel_pace,
        )

    def get_exploration_environment_intent(self, character_id: int) -> dict[str, str]:
        return self._game_service._get_exploration_environment_intent_impl(character_id)

    def wilderness_action_intent(self, character_id: int, action_id: str) -> ActionResult:
        return self._game_service._wilderness_action_intent_impl(character_id, action_id)

    def consume_next_explore_surprise_intent(self, character_id: int) -> str | None:
        return self._game_service._consume_next_explore_surprise_intent_impl(character_id)
