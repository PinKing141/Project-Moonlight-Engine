# Game Features and Function Reference

## Purpose

This document is the consolidated reference for what is currently implemented in the game:

- player-facing gameplay features,
- runtime systems and safeguards,
- and the main function surface across presentation, application, bootstrap, and entrypoint modules.

It reflects the current state of the codebase as of 2026-02-25.

---

## 1) Implemented Game Features

## 1.1 Location-first Core Loop

The root gameplay loop is context-aware and location-first:

- `Act`
- `Travel`
- `Rest`
- `Character`
- `Quit`

Location context is represented as:

- `town` (Town Activities)
- `wilderness` (Explore Area)

Travel toggles between town and wilderness context and advances world time.

## 1.2 Town Systems

In town, the player can access:

- Talk (NPC social interactions)
- Quest Board (accept/turn-in flow)
- Rumour Board (deterministic intel)
- Shop (gold spend + faction-influenced pricing/availability)
- Training (unlocks non-combat interaction options)
- View Factions (reputation view)

Town view also surfaces recent consequence messages.

## 1.3 Social Interaction and Consequences

Social interactions support deterministic checks and persistent NPC memory/disposition.

Current approaches include:

- Friendly
- Direct
- Intimidate
- Leverage Intel (unlock)
- Call In Favor (unlock)

Failure and consequence paths include:

- social rebuff consequence,
- retreat penalties,
- quest timeout failure,
- consequence history in world flags.

## 1.4 Quest Arc

Quest lifecycle currently includes:

- `available` → `active` → `ready_to_turn_in` → `completed`
- `failed` (expiry/consequence path)

Flow supports both:

- combat progression,
- and non-combat social progression for key quest states.

Quest turn-in grants reward payout and faction/world-flag updates.

## 1.5 Economy and Identity Progression

Economy and progression systems currently include:

- bounded shop prices,
- faction-dependent pricing and gated availability,
- training purchases that unlock interaction abilities,
- inventory updates and gold spending.

Unlock examples:

- `intel_leverage` (broker path)
- `captain_favor` (captain path)

## 1.6 Rumour Board and Replay-safe Intel

Rumours are:

- deterministic from seed policy,
- varied by world turn/threat, broker disposition, and faction standings,
- presented with confidence labels (partial information),
- expanded by intel unlocks,
- and persisted with bounded history pruning.

## 1.7 Exploration and Combat

Exploration and combat provide:

- encounter plan generation,
- seed-derived combat resolution,
- scene context (distance/terrain/surprise),
- action menu (attack/spell/dodge/flee),
- reward application on victory,
- and retreat consequence handling on flee.

## 1.8 Character Creation

Character creation includes:

- class/race/background/difficulty selection,
- point-buy validation and roll support,
- external race loading with safe fallback defaults,
- summary DTO generation for presentation rendering.

## 1.9 Persistence and Runtime Safety

Persistence/runtime behavior includes:

- in-memory and MySQL repository paths,
- bootstrap-time MySQL probe with fallback to in-memory,
- runtime MySQL connection error detection and automatic in-memory retry,
- safe shutdown messaging on unrecoverable errors.

## 1.10 Input and UX

Input UX is arrow-key-centric in menu flows via `arrow_menu`.

- Menu navigation: Up/Down (with fallback mappings)
- Confirm: Enter
- Back: Esc/Q (as normalized by menu controls)

---

## 2) Function Surface by Module

## 2.1 Entrypoint and Bootstrap

### `src/rpg/__main__.py`

- `_print_help_surface()`
- `_is_mysql_connectivity_error(exc)`
- `main()`

### `src/rpg/bootstrap.py`

- `_build_encounter_intro_builder()`
- `_build_inmemory_game_service()`
- `_build_mysql_game_service()`
- `create_game_service()`

---

## 2.2 Presentation Layer Functions

### `src/rpg/presentation/main_menu.py`

- `main_menu(game_service)`

### `src/rpg/presentation/load_menu.py`

- `choose_existing_character(game_service)`

### `src/rpg/presentation/menu_controls.py`

- `clear_screen()`
- `_read_key_windows()`
- `read_key()`
- `normalize_menu_key(key)`
- `arrow_menu(title, options)`

### `src/rpg/presentation/game_loop.py`

- `run_game_loop(game_service, character_id)`
- `_run_town(game_service, character_id)`
- `_run_rumour_board(game_service, character_id)`
- `_run_shop(game_service, character_id)`
- `_run_training(game_service, character_id)`
- `_run_quest_board(game_service, character_id)`
- `_run_explore(game_service, character_id)`
- `_choose_combat_action(game_service, options, player, enemy, round_no, scene_ctx=None)`
- `_choose_spell(game_service, player)`
- `_generate_scene()`
- `_scene_flavour(scene, verbosity="compact")`

### `src/rpg/presentation/rolling_ui.py`

- `roll_4d6_drop_lowest()`
- `_render_dice_row(rolls, highlight_index=None)`
- `_animate_stat_roll(stat_name, final_total, final_rolls)`
- `roll_attributes_with_animation()`

---

## 2.3 Application Services (Core)

### `src/rpg/application/services/game_service.py`

Public orchestration and intent methods used by gameplay:

- `rest(character_id)`
- `rest_intent(character_id)`
- `advance_world(ticks=1, persist=True)`
- `explore(character_id)`
- `explore_intent(character_id)`
- `get_player_view(player_id)`
- `list_characters()`
- `list_character_summaries()`
- `get_game_loop_view(character_id)`
- `get_location_context_intent(character_id)`
- `travel_intent(character_id)`
- `rest_with_feedback(character_id)`
- `is_combat_ready()`
- `get_combat_verbosity()`
- `explore_view(character_id)`
- `get_town_view_intent(character_id)`
- `get_npc_interaction_intent(character_id, npc_id)`
- `get_shop_view_intent(character_id)`
- `buy_shop_item_intent(character_id, item_id)`
- `get_training_view_intent(character_id)`
- `purchase_training_intent(character_id, training_id)`
- `get_rumour_board_intent(character_id)`
- `get_quest_board_intent(character_id)`
- `accept_quest_intent(character_id, quest_id)`
- `turn_in_quest_intent(character_id, quest_id)`
- `submit_social_approach_intent(character_id, npc_id, approach)`
- `apply_retreat_consequence_intent(character_id)`
- `build_explore_view(plan)`
- `save_character_state(character)`
- `encounter_intro_intent(enemy)`
- `combat_player_stats_intent(player)`
- `combat_resolve_intent(player, enemy, choose_action, scene=None)`
- `combat_round_view_intent(options, player, enemy, round_no, scene_ctx=None)`
- `submit_combat_action_intent(options, selected_index, spell_slug=None)`
- `list_spell_options(player)`
- `build_character_creation_summary(character)`
- `apply_encounter_reward_intent(character, monster)`
- `faction_standings_intent(character_id)`
- `make_choice(player_id, choice)`

Internal state/rule helpers (still gameplay-relevant):

- world flags helpers (`_world_social_flags`, `_world_quests`, `_world_consequences`, `_world_rumour_history`)
- consequence and rumour history management (`_append_consequence`, `_recent_consequence_messages`, `_record_rumour_history`)
- economy helpers (`_bounded_price`, `_town_price_modifier`)
- location/context helpers (`_location_state_flags`, `_is_town_location`, `_current_location_type`, `_set_location_context`)
- unlock/disposition helpers (`_interaction_unlocks`, `_has_interaction_unlock`, `_grant_interaction_unlock`, `_get_npc_disposition`, `_set_npc_disposition`, `_append_npc_memory`)
- encounter/combat internals (`_run_encounter`, `_pick_monster`, `_resolve_combat`)
- validation/formatting (`_require_world`, `_require_character`, `_format_attr_line`, `_find_town_npc`, `_npc_greeting`)

---

## 2.4 Application Services (Supporting Modules)

### `combat_service.py`

Core classes and functions:

- `CombatLogEntry`
- `CombatResult`
- `ability_mod(score)`
- `proficiency_bonus(level)`
- `roll_die(spec, rng=None)`
- `CombatService.set_seed(seed)`
- `CombatService.derive_player_stats(player)`
- `CombatService.fight_turn_based(...)`
- `CombatService.fight_simple(player, enemy)`

(plus internal resolution helpers for attacks, spells, initiative, intent, logging)

### `encounter_service.py`

- `EncounterService.generate_plan(...)`
- `EncounterService.generate(...)`
- `EncounterService.find_encounter(location_id, character_level)`

### `world_progression.py`

- `WorldProgression.tick(world, ticks=1, persist=True)`

### `quest_service.py`

- `QuestService.register_handlers()`
- `QuestService.on_tick_advanced(event)`
- `QuestService.on_monster_slain(event)`
- `register_quest_handlers(event_bus, world_repo, character_repo)`

### `faction_influence_service.py`

- `FactionInfluenceService.register_handlers()`
- `FactionInfluenceService.on_monster_slain(event)`
- `register_faction_influence_handlers(event_bus, faction_repo, entity_repo)`

### `event_bus.py`

- `EventBus.subscribe(event_type, handler)`
- `EventBus.publish(event)`

### `seed_policy.py`

- `derive_seed(namespace, context)`

### `encounter_intro_enricher.py`

- `EncounterIntroEnricher.build_intro(enemy)`

### `encounter_flavour.py`

- `random_intro(enemy)`

### `balance_tables.py`

- `rest_heal_amount(hp_max)`
- `monster_kill_xp(level)`
- `monster_kill_gold(level)`

### `character_creation_service.py`

Primary API methods:

- `list_classes()`
- `list_races()`
- `list_backgrounds()`
- `list_difficulties()`
- `list_class_names()`
- `race_option_labels()`
- `background_option_labels()`
- `difficulty_option_labels()`
- `class_detail_view(chosen_class)`
- `format_attribute_line(attrs)`
- `point_buy_cost(scores)`
- `create_character(...)`
- `standard_array_for_class(cls)`
- `roll_ability_scores(rng=None)`
- `validate_point_buy(scores, pool=27)`
- `sanitize_name(raw, max_length=20)`

(plus internal parsing/formatting/default-loader helpers)

---

## 2.5 DTO Catalogue (`src/rpg/application/dtos.py`)

- `ActionResult`
- `EncounterPlan`
- `CharacterSummaryView`
- `GameLoopView`
- `EnemyView`
- `ExploreView`
- `SpellOptionView`
- `CharacterCreationSummaryView`
- `CombatSceneView`
- `CombatPlayerPanelView`
- `CombatEnemyPanelView`
- `CombatRoundView`
- `CharacterClassDetailView`
- `RewardOutcomeView`
- `TownNpcView`
- `TownView`
- `NpcInteractionView`
- `SocialOutcomeView`
- `QuestStateView`
- `QuestBoardView`
- `ShopItemView`
- `ShopView`
- `TrainingOptionView`
- `TrainingView`
- `RumourItemView`
- `RumourBoardView`
- `LocationContextView`

---

## 3) Operational Notes

- Menus are expected to remain arrow-key first.
- Presentation should stay intent-driven (no business rule leakage).
- Deterministic pathways should continue to use `derive_seed(...)`.
- Any new player-facing feature should be added here alongside its primary functions.
