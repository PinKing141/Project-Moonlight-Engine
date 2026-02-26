# Application Contract v1

**Version:** `1.1.0`

This document defines the stable application-layer command/query surface for external adapters (CLI now, web/desktop later).

## Commands (state-changing intents)

- `rest_intent(character_id) -> ActionResult`
- `explore_intent(character_id) -> (ExploreView, Character, list[Entity])`
- `combat_resolve_intent(player, enemy, choose_action, scene?) -> CombatResult`
- `submit_combat_action_intent(options, selected_index, spell_slug?) -> tuple[str, Optional[str]] | str`
- `apply_encounter_reward_intent(character, monster) -> RewardOutcomeView`
- `save_character_state(character) -> None`
- `create_snapshot_intent(label?) -> dict[str, object]`
- `load_snapshot_intent(snapshot_id) -> ActionResult`

## Queries (read/presentation intents)

- `list_character_summaries() -> list[CharacterSummaryView]`
- `get_game_loop_view(character_id) -> GameLoopView`
- `combat_round_view_intent(options, player, enemy, round_no, scene_ctx?) -> CombatRoundView`
- `list_spell_options(player) -> list[SpellOptionView]`
- `faction_standings_intent(character_id) -> dict[str, int]`
- `list_snapshots_intent() -> list[dict[str, object]]`

## Contract DTOs

- `ActionResult`
- `ExploreView`
- `GameLoopView`
- `CombatRoundView`
- `RewardOutcomeView`

## Compatibility Rule

- Any breaking change to command/query names, required arguments, or DTO field removal requires a contract version bump.
- Additive DTO fields are allowed in `1.x` if existing fields and semantics remain stable.
