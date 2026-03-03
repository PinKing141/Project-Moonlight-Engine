import sys
from pathlib import Path
import unittest
from typing import Any, cast

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.dtos import ActionResult, ExploreView, LocationContextView, TravelDestinationView
from rpg.application.services.game_service import GameService
from rpg.domain.models.character import Character
from rpg.infrastructure.db.inmemory.repos import InMemoryCharacterRepository


class _ExplorationStub:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def explore_intent(self, character_id: int):
        self.calls.append(("explore_intent", character_id))
        return ExploreView(has_encounter=False, message="stub", enemies=[]), Character(id=character_id, name="Stub"), []

    def get_location_context_intent(self, character_id: int):
        self.calls.append(("get_location_context_intent", character_id))
        return LocationContextView(
            location_type="wilderness",
            title="WILDERNESS",
            current_location_name="Frontier",
            act_label="Explore Area",
            travel_label="Return to Town",
            rest_label="Make Camp",
        )

    def get_travel_destinations_intent(self, character_id: int):
        self.calls.append(("get_travel_destinations_intent", character_id))
        return [
            TravelDestinationView(
                location_id=2,
                name="North Road",
                location_type="wilderness",
                biome="forest",
                preview="Lv 1 • 1d • Low",
                estimated_days=1,
                route_note="",
                mode_hint="",
                prep_summary="",
            )
        ]

    def travel_intent(self, character_id: int, destination_id: int | None = None, travel_mode: str = "road", travel_pace: str = "steady"):
        self.calls.append(("travel_intent", character_id, destination_id, travel_mode, travel_pace))
        return ActionResult(messages=["travel stub"], game_over=False)

    def get_exploration_environment_intent(self, character_id: int):
        self.calls.append(("get_exploration_environment_intent", character_id))
        return {"location_name": "Stubland", "light_level": "Bright", "detection_state": "Unaware", "detection_note": ""}

    def wilderness_action_intent(self, character_id: int, action_id: str):
        self.calls.append(("wilderness_action_intent", character_id, action_id))
        return ActionResult(messages=["wilderness stub"], game_over=False)

    def consume_next_explore_surprise_intent(self, character_id: int):
        self.calls.append(("consume_next_explore_surprise_intent", character_id))
        return "player"


class V17ExplorationFacadeDelegationTests(unittest.TestCase):
    def test_exploration_intents_delegate_to_bounded_service(self) -> None:
        character_repo = InMemoryCharacterRepository({1: Character(id=1, name="Tester")})
        service = GameService(character_repo=character_repo)
        stub = _ExplorationStub()
        cast(Any, service).exploration_app_service = stub

        view, character, enemies = service.explore_intent(1)
        context = service.get_location_context_intent(1)
        destinations = service.get_travel_destinations_intent(1)
        travel_result = service.travel_intent(1, destination_id=2, travel_mode="stealth", travel_pace="slow")
        env = service.get_exploration_environment_intent(1)
        wilderness_result = service.wilderness_action_intent(1, "scout")
        surprise = service.consume_next_explore_surprise_intent(1)

        self.assertEqual("stub", view.message)
        self.assertIsNotNone(character.id)
        self.assertEqual(1, cast(int, character.id))
        self.assertEqual([], enemies)
        self.assertEqual("WILDERNESS", context.title)
        self.assertEqual(1, len(destinations))
        self.assertEqual(["travel stub"], list(travel_result.messages))
        self.assertEqual("Bright", str(env.get("light_level", "")))
        self.assertEqual(["wilderness stub"], list(wilderness_result.messages))
        self.assertEqual("player", surprise)

        self.assertIn(("explore_intent", 1), stub.calls)
        self.assertIn(("get_location_context_intent", 1), stub.calls)
        self.assertIn(("get_travel_destinations_intent", 1), stub.calls)
        self.assertIn(("travel_intent", 1, 2, "stealth", "slow"), stub.calls)
        self.assertIn(("get_exploration_environment_intent", 1), stub.calls)
        self.assertIn(("wilderness_action_intent", 1, "scout"), stub.calls)
        self.assertIn(("consume_next_explore_surprise_intent", 1), stub.calls)


if __name__ == "__main__":
    unittest.main()
