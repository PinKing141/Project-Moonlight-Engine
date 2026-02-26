import sys
from dataclasses import fields
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.contract import COMMAND_INTENTS, QUERY_INTENTS
from rpg.application.dtos import (
    ActionResult,
    CombatRoundView,
    ExploreView,
    GameLoopView,
    RewardOutcomeView,
)


class ContractCompatibilityTests(unittest.TestCase):
    def test_contract_intent_names_are_stable(self) -> None:
        self.assertEqual(
            (
                "rest_intent",
                "explore_intent",
                "combat_resolve_intent",
                "submit_combat_action_intent",
                "apply_encounter_reward_intent",
                "save_character_state",
            ),
            COMMAND_INTENTS,
        )
        self.assertEqual(
            (
                "list_character_summaries",
                "get_game_loop_view",
                "combat_round_view_intent",
                "list_spell_options",
                "faction_standings_intent",
            ),
            QUERY_INTENTS,
        )

    def test_core_dto_fields_are_backward_compatible(self) -> None:
        self.assertEqual(("messages", "game_over"), tuple(field.name for field in fields(ActionResult)))
        self.assertEqual(
            ("has_encounter", "message", "enemies"),
            tuple(field.name for field in fields(ExploreView)),
        )
        self.assertEqual(
            (
                "character_id",
                "name",
                "race",
                "class_name",
                "difficulty",
                "hp_current",
                "hp_max",
                "world_turn",
                "threat_level",
            ),
            tuple(field.name for field in fields(GameLoopView)),
        )
        self.assertEqual(
            ("round_number", "scene", "player", "enemy", "options"),
            tuple(field.name for field in fields(CombatRoundView)),
        )
        self.assertEqual(
            ("xp_gain", "money_gain", "loot_items"),
            tuple(field.name for field in fields(RewardOutcomeView)),
        )


if __name__ == "__main__":
    unittest.main()
