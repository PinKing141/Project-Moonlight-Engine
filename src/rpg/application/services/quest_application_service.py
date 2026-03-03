from __future__ import annotations

from typing import TYPE_CHECKING

from rpg.application.dtos import ActionResult, QuestBoardView, QuestJournalView

if TYPE_CHECKING:
    from rpg.application.services.game_service import GameService


class QuestApplicationService:
    def __init__(self, game_service: GameService) -> None:
        self._game_service = game_service

    def get_quest_board_intent(self, character_id: int) -> QuestBoardView:
        return self._game_service._get_quest_board_intent_impl(character_id)

    def get_quest_journal_intent(self, character_id: int) -> QuestJournalView:
        return self._game_service._get_quest_journal_intent_impl(character_id)

    def accept_quest_intent(self, character_id: int, quest_id: str) -> ActionResult:
        return self._game_service._accept_quest_intent_impl(character_id, quest_id)

    def turn_in_quest_intent(self, character_id: int, quest_id: str) -> ActionResult:
        return self._game_service._turn_in_quest_intent_impl(character_id, quest_id)
