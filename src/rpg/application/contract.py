CONTRACT_VERSION = "1.0.0"

COMMAND_INTENTS = (
    "rest_intent",
    "explore_intent",
    "combat_resolve_intent",
    "submit_combat_action_intent",
    "apply_encounter_reward_intent",
    "save_character_state",
)

QUERY_INTENTS = (
    "list_character_summaries",
    "get_game_loop_view",
    "combat_round_view_intent",
    "list_spell_options",
    "faction_standings_intent",
)

CONTRACT_DTO_TYPES = (
    "ActionResult",
    "ExploreView",
    "GameLoopView",
    "CombatRoundView",
    "RewardOutcomeView",
)
