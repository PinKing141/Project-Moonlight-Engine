import sys
from pathlib import Path
import unittest
from typing import Any, cast

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.dtos import ActionResult, QuestBoardView, QuestJournalSectionView, QuestJournalView, QuestStateView
from rpg.application.services.game_service import GameService
from rpg.domain.models.character import Character
from rpg.infrastructure.db.inmemory.repos import InMemoryCharacterRepository


class _QuestStub:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def get_quest_board_intent(self, character_id: int) -> QuestBoardView:
        self.calls.append(("get_quest_board_intent", character_id))
        return QuestBoardView(
            quests=[
                QuestStateView(
                    quest_id="q1",
                    title="Stub Quest",
                    status="available",
                    progress=0,
                    target=1,
                    reward_xp=5,
                    reward_money=3,
                    objective_summary="Do the thing",
                    urgency_label="Normal",
                )
            ],
            empty_state_hint="",
        )

    def get_quest_journal_intent(self, character_id: int) -> QuestJournalView:
        self.calls.append(("get_quest_journal_intent", character_id))
        return QuestJournalView(
            sections=[QuestJournalSectionView(title="Active", quests=[])],
            empty_state_hint="journal stub",
        )

    def accept_quest_intent(self, character_id: int, quest_id: str) -> ActionResult:
        self.calls.append(("accept_quest_intent", character_id, quest_id))
        return ActionResult(messages=["accept stub"], game_over=False)

    def turn_in_quest_intent(self, character_id: int, quest_id: str) -> ActionResult:
        self.calls.append(("turn_in_quest_intent", character_id, quest_id))
        return ActionResult(messages=["turnin stub"], game_over=False)


class V17QuestFacadeDelegationTests(unittest.TestCase):
    def test_quest_intents_delegate_to_bounded_service(self) -> None:
        character_repo = InMemoryCharacterRepository({1: Character(id=1, name="Tester")})
        service = GameService(character_repo=character_repo)
        stub = _QuestStub()
        cast(Any, service).quest_app_service = stub

        board = service.get_quest_board_intent(1)
        journal = service.get_quest_journal_intent(1)
        accept = service.accept_quest_intent(1, "q1")
        turnin = service.turn_in_quest_intent(1, "q1")

        self.assertEqual("Stub Quest", board.quests[0].title)
        self.assertEqual("journal stub", journal.empty_state_hint)
        self.assertEqual(["accept stub"], list(accept.messages))
        self.assertEqual(["turnin stub"], list(turnin.messages))

        self.assertIn(("get_quest_board_intent", 1), stub.calls)
        self.assertIn(("get_quest_journal_intent", 1), stub.calls)
        self.assertIn(("accept_quest_intent", 1, "q1"), stub.calls)
        self.assertIn(("turn_in_quest_intent", 1, "q1"), stub.calls)


if __name__ == "__main__":
    unittest.main()
