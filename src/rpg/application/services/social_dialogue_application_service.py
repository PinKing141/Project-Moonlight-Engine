from __future__ import annotations

from typing import TYPE_CHECKING

from rpg.application.dtos import DialogueSessionView, NpcInteractionView, SocialOutcomeView

if TYPE_CHECKING:
    from rpg.application.services.game_service import GameService


class SocialDialogueApplicationService:
    def __init__(self, game_service: GameService) -> None:
        self._game_service = game_service

    def get_npc_interaction_intent(self, character_id: int, npc_id: str) -> NpcInteractionView:
        return self._game_service._get_npc_interaction_intent_impl(character_id, npc_id)

    def get_dialogue_session_intent(self, character_id: int, npc_id: str) -> DialogueSessionView:
        return self._game_service._get_dialogue_session_intent_impl(character_id, npc_id)

    def submit_social_approach_intent(
        self,
        character_id: int,
        npc_id: str,
        approach: str,
        forced_dc: int | None = None,
        forced_skill: str | None = None,
    ) -> SocialOutcomeView:
        return self._game_service._submit_social_approach_intent_impl(
            character_id,
            npc_id,
            approach,
            forced_dc=forced_dc,
            forced_skill=forced_skill,
        )

    def submit_dialogue_choice_intent(self, character_id: int, npc_id: str, choice_id: str) -> SocialOutcomeView:
        return self._game_service._submit_dialogue_choice_intent_impl(character_id, npc_id, choice_id)
