# V20 — Combat Depth: Reactions, Positioning, Roles

## Implementation Status

**Implemented** (stabilization complete, 2026-03-02; V20 scoped verification gate passed).

Current state summary:
- Reaction windows, readied-action triggers, positioning depth, and role-driven enemy behavior are implemented.
- Deterministic trigger-order and tactical behavior coverage is present.
- Scoped V20 verification gate passed: 22 tests (`test_combat_gridless_range`, `test_combat_environmental_hazards`, `test_combat_concentration_and_tactical`).

## Duration

5–8 weeks

## Objective

Deepen tactical combat identity while maintaining CLI readability and deterministic flow.

## In Scope

1. Reaction economy:
   - Opportunity attacks
   - Defensive reactions
   - Limited reaction spell hooks
2. Readied actions:
   - Triggered action definitions with bounded trigger taxonomy
3. Positioning expansion:
   - Engaged/near/far movement cost and lane interactions
4. Enemy role AI:
   - Brute, skirmisher, controller, artillery, support behaviors

## Out of Scope

- Grid map tactical engine.
- Real-time combat systems.

## Work Breakdown

### Stream A: Combat Timeline Model
- Add pre/post-turn reaction windows.
- Add clear event ordering and transcript markers.

### Stream B: Player Action Model
- Add ready/reaction declaration paths.
- Ensure turn prompts remain concise.

### Stream C: AI Role Logic
- Assign role templates and action weights.
- Add deterministic tactical decision hooks.

## Deliverables

- Combat timeline with reaction windows.
- Role-driven enemy behavior profiles.
- Test coverage for trigger resolution order.

## Acceptance Criteria

- Reaction triggers are clearly explained in logs.
- No ordering ambiguity in simultaneous trigger cases.
- Prompt complexity remains within defined UX budget.

## Risks and Mitigations

- **Risk:** excessive branching in combat loop.
  - **Mitigation:** strict trigger taxonomy and capped reaction opportunities.
- **Risk:** AI unpredictability breaks deterministic expectations.
  - **Mitigation:** seed-derived tactical selection only.

## Scope Estimate

Large (L)
