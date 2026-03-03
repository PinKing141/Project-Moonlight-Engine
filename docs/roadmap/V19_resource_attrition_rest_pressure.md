# V19 — D&D Feel Layer 2: Resource Attrition & Rest Pressure

## Implementation Status

**Implemented** (feature set landed and regression-tested), pending optional formal closeout note parity with V21 format.

Current state summary:
- Resource pressure tracks, rest risk/interruption outcomes, and bounded encumbrance behavior are implemented.
- UX pressure/risk surfacing is present in gameplay views.
- Deterministic regression coverage is present for core loops.

## Duration

4–6 weeks

## Objective

Make travel/rest choices strategically meaningful through bounded scarcity and recovery tradeoffs.

## In Scope

1. Resource tracks:
   - Rations
   - Ammunition
   - Light sources
   - Fatigue/exhaustion indicator
2. Rest risk model:
   - Camp interruption chances
   - Partial recovery outcomes
3. Exhaustion-like penalty ladder (bounded tiers).
4. Lightweight encumbrance bands (light/loaded/overburdened).

## Out of Scope

- Deep survival simulation.
- Dynamic weather simulation.

## Work Breakdown

### Stream A: Data and Persistence
- Extend character/world flags for resource state.
- Add migration and in-memory parity handling.

### Stream B: Rest and Recovery Logic
- Introduce short/long rest risk tables.
- Apply deterministic interruption outcomes.

### Stream C: UX and Feedback
- Add concise pressure status summaries.
- Surface risk warnings before travel/rest confirmation.

## Deliverables

- Resource pressure subsystem.
- Rest risk and partial recovery outcomes.
- Regression tests for depletion/recovery loops.

## Acceptance Criteria

- Resource decisions affect near-term gameplay outcomes.
- No irreversible soft-lock from depletion.
- Deterministic parity for repeat runs.

## Risks and Mitigations

- **Risk:** over-punishing attrition reduces fun.
  - **Mitigation:** tune bounds and guarantee recovery paths.
- **Risk:** menu complexity creep.
  - **Mitigation:** aggregate state into compact status lines.

## Scope Estimate

Medium (M)
