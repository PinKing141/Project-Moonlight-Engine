# V18 — D&D Feel Layer 1: Checks, Stealth, Consequences

## Implementation Status

**Implemented** (stabilization complete, 2026-03-02; V18 scoped verification gate passed).

Current state summary:
- Check-resolution, stealth/detection, and consequence branching capabilities are present in runtime paths.
- Deterministic test coverage exists across affected mechanics.
- Scoped V18 verification gate passed: 58 tests (`test_v18_check_resolution_service`, `test_exploration_light_and_suspicion`, `test_town_social_flow`).

## Duration

5–7 weeks

## Objective

Introduce core tabletop-style non-combat resolution and stealth gameplay.

## In Scope

1. Unified check resolution engine:
   - Ability checks
   - Skill proficiency contribution
   - Advantage/disadvantage handling
   - Difficulty class tiers
2. Stealth subsystem:
   - Hidden/suspicious/alerted states
   - Opposed detection flow
   - Stateful consequences
3. Trap and hazard interactions:
   - Detect/disarm/trigger branches
4. Social DC expansion:
   - NPC stance, prior state, and faction context as modifiers

## Out of Scope

- Full non-combat spell utility matrix.
- Crafting/professions.

## Work Breakdown

### Stream A: Rule Engine
- Implement check resolution module and deterministic roll context contracts.
- Add structured result payloads (success, margin, consequence tags).

### Stream B: Stealth in Exploration
- Add stealth actions and detection checks.
- Persist stealth-related state and escalation outcomes.

### Stream C: Social Consequence Extension
- Expand social checks and consequence ladders.
- Add failure-forward outcomes (no dead-end loops).

## Deliverables

- Check resolution service.
- Stealth-capable wilderness/town action paths.
- New tests for deterministic branching outcomes.

## Acceptance Criteria

- Check outcomes are deterministic for identical seeds/contexts.
- At least 12 scenario tests cover pass/fail/escalation branches.
- Consequence states are visible and explainable in UX output.

## Risks and Mitigations

- **Risk:** stealth adds opaque state transitions.
  - **Mitigation:** explicit state labels in logs and UI summaries.
- **Risk:** check engine complexity leak into UI.
  - **Mitigation:** keep UI-facing DTO compact and semantic.

## Scope Estimate

Medium/Large (M/L)
