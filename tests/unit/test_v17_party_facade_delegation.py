import sys
from pathlib import Path
import unittest
from typing import Any, cast

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.dtos import ActionResult
from rpg.application.services.game_service import GameService
from rpg.domain.models.character import Character
from rpg.infrastructure.db.inmemory.repos import InMemoryCharacterRepository


class _PartyStub:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def get_party_status_intent(self, character_id: int) -> list[str]:
        self.calls.append(("get_party_status_intent", character_id))
        return ["Stub Ally: HP 10/10"]

    def get_party_capacity_intent(self, character_id: int) -> tuple[int, int]:
        self.calls.append(("get_party_capacity_intent", character_id))
        return 1, 3

    def get_party_management_intent(self, character_id: int) -> list[dict[str, str | bool]]:
        self.calls.append(("get_party_management_intent", character_id))
        return [
            {
                "companion_id": "npc_stub",
                "name": "Stub Ally",
                "active": True,
                "unlocked": True,
                "recruitable": True,
                "gate_note": "",
                "lane": "auto",
                "status": "HP 10/10",
            }
        ]

    def set_party_companion_active_intent(self, character_id: int, companion_id: str, active: bool) -> ActionResult:
        self.calls.append(("set_party_companion_active_intent", character_id, companion_id, active))
        return ActionResult(messages=["active stub"], game_over=False)

    def set_party_companion_lane_intent(self, character_id: int, companion_id: str, lane: str) -> ActionResult:
        self.calls.append(("set_party_companion_lane_intent", character_id, companion_id, lane))
        return ActionResult(messages=["lane stub"], game_over=False)


class V17PartyFacadeDelegationTests(unittest.TestCase):
    def test_party_intents_delegate_to_bounded_service(self) -> None:
        character_repo = InMemoryCharacterRepository({1: Character(id=1, name="Tester")})
        service = GameService(character_repo=character_repo)
        stub = _PartyStub()
        cast(Any, service).party_app_service = stub

        status = service.get_party_status_intent(1)
        capacity = service.get_party_capacity_intent(1)
        management = service.get_party_management_intent(1)
        set_active = service.set_party_companion_active_intent(1, "npc_stub", True)
        set_lane = service.set_party_companion_lane_intent(1, "npc_stub", "vanguard")

        self.assertEqual(["Stub Ally: HP 10/10"], status)
        self.assertEqual((1, 3), capacity)
        self.assertEqual("Stub Ally", str(management[0].get("name", "")))
        self.assertEqual(["active stub"], list(set_active.messages))
        self.assertEqual(["lane stub"], list(set_lane.messages))

        self.assertIn(("get_party_status_intent", 1), stub.calls)
        self.assertIn(("get_party_capacity_intent", 1), stub.calls)
        self.assertIn(("get_party_management_intent", 1), stub.calls)
        self.assertIn(("set_party_companion_active_intent", 1, "npc_stub", True), stub.calls)
        self.assertIn(("set_party_companion_lane_intent", 1, "npc_stub", "vanguard"), stub.calls)


if __name__ == "__main__":
    unittest.main()
