# V22 — Campaign Systems: Faction War, Crafting, Endgame

## Status

**Implementation Status:** **Implemented** (V22a and V22b closeout complete, 2026-03-02).

Superseded by subsequent roadmap phases (post-2026-03-02).

## Phase Split Strategy

V22 is executed in two controlled sub-phases to reduce integration risk:

- **V22a (implemented):** faction simulation foundation + quest arc generator v2 integration.
- **V22b (implemented):** crafting/profession loop + endgame crisis framework foundation.

- [V22a — Faction Simulation & Quest Arc Foundation](./V22a_faction_quest_foundation.md) is completed.
- [V22b — Crafting & Endgame Foundation](./V22b_crafting_endgame_foundation.md) is completed.

## Duration

8–12 weeks (consider split: V22a and V22b)

## Objective

Deliver long-form campaign depth and replayability through faction dynamics, bounded crafting, and escalating endgame states.

## In Scope

1. Faction conflict simulation:
   - Alliance/hostility states
   - Territory pressure
   - Player intervention opportunities
2. Crafting/profession loop (bounded):
   - Gather -> unlock -> craft
   - Consumables/utility outputs first
3. Quest arc generator v2:
   - Branching conditioned by world/faction context
4. Endgame crisis cadence:
   - Multi-stage escalating threats
   - Fail-forward outcomes

## Out of Scope

- Sandbox city-builder systems.
- Infinite economy simulations.

## Work Breakdown

### Stream A: Faction Simulation
- Define state machine and transition triggers.
- Add diplomacy and pressure effects to world progression.

### Stream B: Crafting
- Implement minimal profession taxonomy.
- Add recipe unlock conditions and output balancing.

### Stream C: Endgame Framework
- Define crisis phases and thresholds.
- Add scenario packs and outcome branches.

## Deliverables

- Faction diplomacy/conflict system.
- Crafting subsystem with progression hooks.
- Endgame scenario and branching outcomes.

## Acceptance Criteria

- Campaign states diverge significantly across different seeds.
- Crafting adds strategic value without replacing core loops.
- Endgame has recoverable and terminal paths with clear signposting.

## Risks and Mitigations

- **Risk:** runaway complexity across interacting subsystems.
  - **Mitigation:** split into V22a (faction+quest) and V22b (crafting+endgame) if needed.
- **Risk:** replay incoherence.
  - **Mitigation:** scenario validation harness for long-run state checks.

## Scope Estimate

Extra Large (XL)
