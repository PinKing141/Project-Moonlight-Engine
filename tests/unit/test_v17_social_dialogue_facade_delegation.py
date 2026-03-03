import sys
from pathlib import Path
import unittest
from typing import Any, cast

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.dtos import DialogueChoiceView, DialogueSessionView, NpcInteractionView, SocialOutcomeView
from rpg.application.services.game_service import GameService
from rpg.domain.models.character import Character
from rpg.infrastructure.db.inmemory.repos import InMemoryCharacterRepository


class _SocialDialogueStub:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def get_npc_interaction_intent(self, character_id: int, npc_id: str) -> NpcInteractionView:
        self.calls.append(("get_npc_interaction_intent", character_id, npc_id))
        return NpcInteractionView(
            npc_id=npc_id,
            npc_name="Stub NPC",
            role="Broker",
            temperament="calm",
            relationship=0,
            greeting="Hello there.",
            approaches=["Friendly", "Direct"],
        )

    def get_dialogue_session_intent(self, character_id: int, npc_id: str) -> DialogueSessionView:
        self.calls.append(("get_dialogue_session_intent", character_id, npc_id))
        return DialogueSessionView(
            npc_id=npc_id,
            npc_name="Stub NPC",
            stage_id="opening",
            greeting="Greetings.",
            choices=[DialogueChoiceView(choice_id="c1", label="Ask", available=True, locked_reason="")],
            challenge_progress=0,
            challenge_target=3,
        )

    def submit_social_approach_intent(
        self,
        character_id: int,
        npc_id: str,
        approach: str,
        forced_dc: int | None = None,
        forced_skill: str | None = None,
    ) -> SocialOutcomeView:
        self.calls.append(("submit_social_approach_intent", character_id, npc_id, approach, forced_dc, forced_skill))
        return SocialOutcomeView(
            npc_id=npc_id,
            npc_name="Stub NPC",
            approach=approach,
            success=True,
            roll_total=15,
            target_dc=12,
            relationship_before=0,
            relationship_after=6,
            messages=["social stub"],
        )

    def submit_dialogue_choice_intent(self, character_id: int, npc_id: str, choice_id: str) -> SocialOutcomeView:
        self.calls.append(("submit_dialogue_choice_intent", character_id, npc_id, choice_id))
        return SocialOutcomeView(
            npc_id=npc_id,
            npc_name="Stub NPC",
            approach="direct",
            success=True,
            roll_total=14,
            target_dc=12,
            relationship_before=6,
            relationship_after=8,
            messages=["dialogue stub"],
        )


class V17SocialDialogueFacadeDelegationTests(unittest.TestCase):
    def test_social_dialogue_intents_delegate_to_bounded_service(self) -> None:
        character_repo = InMemoryCharacterRepository({1: Character(id=1, name="Tester")})
        service = GameService(character_repo=character_repo)
        stub = _SocialDialogueStub()
        cast(Any, service).social_dialogue_app_service = stub

        interaction = service.get_npc_interaction_intent(1, "npc_stub")
        session = service.get_dialogue_session_intent(1, "npc_stub")
        social = service.submit_social_approach_intent(1, "npc_stub", "friendly", forced_dc=10, forced_skill="persuasion")
        dialogue = service.submit_dialogue_choice_intent(1, "npc_stub", "c1")

        self.assertEqual("Stub NPC", interaction.npc_name)
        self.assertEqual("opening", session.stage_id)
        self.assertEqual(["social stub"], list(social.messages))
        self.assertEqual(["dialogue stub"], list(dialogue.messages))

        self.assertIn(("get_npc_interaction_intent", 1, "npc_stub"), stub.calls)
        self.assertIn(("get_dialogue_session_intent", 1, "npc_stub"), stub.calls)
        self.assertIn(("submit_social_approach_intent", 1, "npc_stub", "friendly", 10, "persuasion"), stub.calls)
        self.assertIn(("submit_dialogue_choice_intent", 1, "npc_stub", "c1"), stub.calls)


if __name__ == "__main__":
    unittest.main()
