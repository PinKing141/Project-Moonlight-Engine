# V22b — Crafting & Endgame Foundation

## Status

Implemented (closeout complete, 2026-03-02).

### Implementation Progress (2026-03-02)

- ✅ Added bounded `crafting_v1` normalization in world progression with safe defaults and versioned envelope.
- ✅ Wired normalization into world progression tick loop for consistent save-state shape.
- ✅ Added deterministic tests for crafting envelope normalization and identical-run signature stability.
- ✅ Added deterministic craft outcome resolver for curated downtime recipe family.
- ✅ Surfaced compact crafting and crisis summaries in existing town pressure view.
- ✅ Added integration tests for deterministic craft outcomes and persisted `crafting_v1` recipe/stockpile updates.

### Verification Evidence

- `python -m pytest tests/unit/test_event_bus_progression.py -k crafting_state` → 2 passed.
- `python -m pytest tests/unit/test_event_bus_progression.py tests/unit/test_quest_arc_flow.py tests/unit/test_quest_journal_view.py` → 29 passed.
- `python -m pytest tests/unit/test_downtime_flow.py tests/unit/test_town_social_flow.py -k "craft or crafting or crisis"` → 4 passed.
- `python -m pytest tests/unit/test_v17_contract_drift.py tests/unit/test_event_bus_progression.py tests/unit/test_downtime_flow.py tests/unit/test_town_social_flow.py tests/unit/test_quest_arc_flow.py tests/unit/test_quest_journal_view.py` → 79 passed.

### Acceptance Closeout Checklist

- ✅ Crafting baseline is playable via one deterministic town action path.
  - Covered by `test_submit_downtime_crafting_outcome_is_deterministic_for_same_seed` and `test_submit_downtime_crafting_spends_gold_adds_item_and_advances_world`.
- ✅ Crisis progression state advances predictably under deterministic rules.
  - Covered by `test_cataclysm_clock_is_deterministic_for_same_state`.
- ✅ Existing presentation contracts remain stable.
  - Covered by `test_v17_contract_drift.py` suite.

## Duration

3–5 weeks

## Objective

Establish a deterministic crafting/profession baseline and endgame crisis state scaffolding without expanding into broad economy systems.

## Scope

### In Scope

1. Crafting foundation (bounded):
   - Minimal profession taxonomy (`gathering`, `refining`, `fieldcraft`).
   - Recipe envelope persistence under versioned world/character flags.
   - One town-facing craft action path with explainable outcomes.
2. Endgame framework foundation:
   - Crisis envelope normalization + phase thresholds.
   - Deterministic per-turn crisis drift hook in world progression (no major UI expansion).
3. Deterministic surfacing:
   - Compact crafting/cataclysm summary lines in existing views only.

### Out of Scope

- Full recipe catalog expansion.
- New economy subsystems or market simulation.
- Full apex/end-state cinematic flow.

## Determinism Impact Statement

- Crafting and crisis branching must resolve from centralized seed derivation with explicit versioned context keys.
- New envelopes must normalize unknown/legacy payloads into safe defaults.

## Data Model Impact

- Add bounded `crafting_v1` envelope in world/character flags.
- Extend crisis state metadata with stable branch signature fields.

## Test Plan

- Unit:
  - Crafting envelope normalization + deterministic outcome selection.
  - Crisis drift determinism for identical seed/context.
- Integration:
  - Town craft action -> world tick -> summary visibility.
- Replay:
  - 20+ turn fixture validating stable craft/crisis signatures.

## Acceptance Criteria

- Crafting baseline is playable via one deterministic town action path.
- Crisis progression state advances predictably under deterministic rules.
- Existing presentation contracts remain stable.

## Rollout & Fallback

- Gate behavior behind `crafting_v1` and crisis envelope presence checks.
- On failure, degrade to existing non-crafting flow while preserving save compatibility.

## First Implementation Slice

1. Add `crafting_v1` normalization helper and default envelope.
2. Add deterministic craft outcome resolver for one curated recipe family.
3. Surface compact craft/cataclysm summary in existing town view.
4. Add targeted unit + integration regression tests.
