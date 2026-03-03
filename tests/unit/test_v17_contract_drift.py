import inspect
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.exploration_application_service import ExplorationApplicationService
from rpg.application.services.game_service import GameService
from rpg.application.services.party_application_service import PartyApplicationService
from rpg.application.services.quest_application_service import QuestApplicationService
from rpg.application.services.social_dialogue_application_service import SocialDialogueApplicationService
from rpg.application.services.town_economy_application_service import TownEconomyApplicationService


class V17ContractDriftTests(unittest.TestCase):
    _SERVICE_METHODS: dict[type, list[str]] = {
        ExplorationApplicationService: [
            "explore_intent",
            "get_location_context_intent",
            "get_travel_destinations_intent",
            "travel_intent",
            "get_exploration_environment_intent",
            "wilderness_action_intent",
            "consume_next_explore_surprise_intent",
        ],
        SocialDialogueApplicationService: [
            "get_npc_interaction_intent",
            "get_dialogue_session_intent",
            "submit_social_approach_intent",
            "submit_dialogue_choice_intent",
        ],
        QuestApplicationService: [
            "get_quest_board_intent",
            "get_quest_journal_intent",
            "accept_quest_intent",
            "turn_in_quest_intent",
        ],
        TownEconomyApplicationService: [
            "get_town_view_intent",
            "get_shop_view_intent",
            "buy_shop_item_intent",
            "get_sell_inventory_view_intent",
            "sell_inventory_item_intent",
            "get_training_view_intent",
            "purchase_training_intent",
        ],
        PartyApplicationService: [
            "get_party_status_intent",
            "get_party_capacity_intent",
            "get_party_management_intent",
            "set_party_companion_active_intent",
            "set_party_companion_lane_intent",
        ],
    }

    _FACADE_DELEGATION: dict[str, tuple[str, str]] = {
        "explore_intent": ("exploration_app_service", "explore_intent"),
        "get_location_context_intent": ("exploration_app_service", "get_location_context_intent"),
        "get_travel_destinations_intent": ("exploration_app_service", "get_travel_destinations_intent"),
        "travel_intent": ("exploration_app_service", "travel_intent"),
        "get_exploration_environment_intent": ("exploration_app_service", "get_exploration_environment_intent"),
        "wilderness_action_intent": ("exploration_app_service", "wilderness_action_intent"),
        "consume_next_explore_surprise_intent": ("exploration_app_service", "consume_next_explore_surprise_intent"),
        "get_npc_interaction_intent": ("social_dialogue_app_service", "get_npc_interaction_intent"),
        "get_dialogue_session_intent": ("social_dialogue_app_service", "get_dialogue_session_intent"),
        "submit_social_approach_intent": ("social_dialogue_app_service", "submit_social_approach_intent"),
        "submit_dialogue_choice_intent": ("social_dialogue_app_service", "submit_dialogue_choice_intent"),
        "get_quest_board_intent": ("quest_app_service", "get_quest_board_intent"),
        "get_quest_journal_intent": ("quest_app_service", "get_quest_journal_intent"),
        "accept_quest_intent": ("quest_app_service", "accept_quest_intent"),
        "turn_in_quest_intent": ("quest_app_service", "turn_in_quest_intent"),
        "get_town_view_intent": ("town_economy_app_service", "get_town_view_intent"),
        "get_shop_view_intent": ("town_economy_app_service", "get_shop_view_intent"),
        "buy_shop_item_intent": ("town_economy_app_service", "buy_shop_item_intent"),
        "get_sell_inventory_view_intent": ("town_economy_app_service", "get_sell_inventory_view_intent"),
        "sell_inventory_item_intent": ("town_economy_app_service", "sell_inventory_item_intent"),
        "get_training_view_intent": ("town_economy_app_service", "get_training_view_intent"),
        "purchase_training_intent": ("town_economy_app_service", "purchase_training_intent"),
        "get_party_status_intent": ("party_app_service", "get_party_status_intent"),
        "get_party_capacity_intent": ("party_app_service", "get_party_capacity_intent"),
        "get_party_management_intent": ("party_app_service", "get_party_management_intent"),
        "set_party_companion_active_intent": ("party_app_service", "set_party_companion_active_intent"),
        "set_party_companion_lane_intent": ("party_app_service", "set_party_companion_lane_intent"),
    }

    def test_facade_methods_delegate_to_bounded_services(self) -> None:
        for public_method, (service_attr, service_method) in self._FACADE_DELEGATION.items():
            self.assertTrue(hasattr(GameService, public_method), f"Missing facade method: {public_method}")
            src = inspect.getsource(getattr(GameService, public_method))
            expected = f"self.{service_attr}.{service_method}("
            self.assertIn(expected, src, f"Facade delegation drift for {public_method}")

    def test_bounded_services_call_impl_methods(self) -> None:
        for service_type, methods in self._SERVICE_METHODS.items():
            for method_name in methods:
                self.assertTrue(hasattr(service_type, method_name), f"Missing bounded service method: {service_type.__name__}.{method_name}")
                src = inspect.getsource(getattr(service_type, method_name))
                expected = f"_{method_name}_impl("
                self.assertIn(expected, src, f"Bounded service drift for {service_type.__name__}.{method_name}")


if __name__ == "__main__":
    unittest.main()
