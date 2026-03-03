# V22a — Faction Simulation & Quest Arc Foundation

## Status

Implemented (closeout complete, 2026-03-02).

### Implementation Progress (2026-03-02)

- ✅ Deterministic `faction_conflict_v1` normalization + per-turn transition tick integrated in world progression.
- ✅ Compact faction-conflict summary surfaced in town and faction-standings views.
- ✅ Town intervention path (`submit_pressure_relief_intent`) now persists explicit world consequences and de-escalates linked faction-conflict relations.
- ✅ Quest arc metadata v2 now syncs deterministic branch keys/signatures from faction/world state and is surfaced in quest board/journal summaries.

### Verification Evidence

- `python -m pytest tests/test_game_logic.py -k pressure_relief` → 3 passed.
- `python -m pytest tests/unit/test_v17_contract_drift.py tests/unit/test_event_bus_progression.py tests/unit/test_town_social_flow.py tests/unit/test_quest_journal_view.py tests/unit/test_quest_arc_flow.py` → 70 passed.
- `python -m pytest tests/unit/test_event_bus_progression.py tests/unit/test_town_social_flow.py` → 54 passed.
- `python -m pytest tests/unit/test_quest_arc_flow.py -k replay_24_turns` → 1 passed.
- `python -m pytest tests/unit/test_quest_journal_view.py tests/unit/test_quest_arc_flow.py` → 14 passed.
- `python -m pytest tests/unit/test_escalating_quests_and_rumours.py tests/unit/test_town_social_flow.py -k "quest or faction_conflict"` → 3 passed.

### Acceptance Closeout Checklist

- ✅ At least two factions can transition state over time under deterministic rules.
  - Covered by `test_faction_conflict_tick_is_deterministic_for_same_seed_and_state`.
- ✅ Quest board/journal reflects branch metadata conditioned by faction/world state.
  - Covered by `test_quest_board_persists_arc_metadata_and_surfaces_branch_summary` and `test_intervention_then_world_tick_shifts_quest_branch_visibility`.
- ✅ Intervention path produces explainable, persisted pressure outcomes.
  - Covered by `test_pressure_relief_persists_faction_conflict_deescalation_and_consequence`.
- ✅ No contract drift in current presentation intents.
  - Covered by `test_v17_contract_drift.py` suite.
- ✅ Replay fixture validates 20+ turn stable faction/quest outcomes.
  - Covered by `test_replay_24_turns_keeps_faction_and_quest_arc_signatures_stable`.

## Duration

3–5 weeks

## Objective

Establish deterministic faction-conflict progression and hook it into quest branching without introducing crafting/endgame scope.

## Scope

### In Scope

1. Faction state machine foundation:
   - Alliance/neutral/hostile relationship bands
   - Deterministic transition triggers from world pressure and player actions
   - Bounded per-turn diplomacy updates in world progression
2. Quest arc generator v2 (foundation pass):
   - Branch keys conditioned by faction/world state
   - Stable arc metadata persisted for replay parity
3. Player intervention hooks (minimal):
   - At least one town-facing intervention action path
   - Explicit consequence logging for faction pressure shifts

### Out of Scope (deferred to V22b)

- Crafting/profession loop implementation
- Endgame crisis phase implementation
- New economy subsystems beyond existing faction pressure hooks

## Determinism Impact Statement

- All new branching must resolve from centralized seed derivation and normalized context payloads.
- Faction transition contexts must include explicit versioned keys to preserve replay compatibility.

## Data Model Impact

- Extend `world.flags` with a bounded `faction_conflict_v1` envelope.
- Add quest arc v2 metadata keys under quest state without breaking existing quest read paths.

## Test Plan

- Unit:
  - Faction state transition determinism for identical seed/context
  - Quest arc branch selection determinism for identical seed/context
  - Intervention action consequence and persistence checks
- Integration:
  - Town -> intervention -> world progression -> quest board branch visibility
- Replay:
  - Golden long-run fixture for 20+ turns with stable faction/quest outcomes

## Acceptance Criteria

- At least two factions can transition state over time under deterministic rules.
- Quest board/journal reflects branch metadata conditioned by faction/world state.
- Intervention path produces explainable, persisted pressure outcomes.
- No contract drift in current presentation intents.

## Rollout & Fallback

- Gate behavior behind `faction_conflict_v1` presence checks and safe defaults.
- On failure, degrade to current static faction pressure behavior while preserving save compatibility.

## First Implementation Slice

1. Add `faction_conflict_v1` normalization helper in world progression.
2. Add deterministic transition tick with no UI changes.
3. Surface compact summary line in existing town/faction views.
4. Add targeted regression + replay fixture.
