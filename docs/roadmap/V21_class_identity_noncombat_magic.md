# V21 — Class Identity & Non-Combat Magic Expansion

## Status

**Implementation Status:** **Implemented** (stabilized and closed).

Stabilization complete (2026-03-02).

Final stabilization gate passed with focused cross-phase verification:
- V19 + V20 + V21 broader gate: 136 passed.
- V21 social provenance polish gate: 74 passed.

This phase is considered closed for roadmap sequencing; follow-on work should be tracked under V22.

## Duration

6–9 weeks

## Objective

Make class fantasy meaningful in exploration, social, and town loops beyond damage output.

## In Scope

1. Utility spell hooks:
   - Detection
   - Traversal
   - Social leverage
   - Protective rituals
2. Class feature milestones reflected in non-combat choices.
3. Companion synergy effects tied to class/party composition.

## Out of Scope

- Full SRD spell parity.
- Summoning ecosystem.

## Work Breakdown

### Stream A: Utility Spell Integration
- Define reusable world-interaction hooks.
- Wire selected spells to those hooks.

### Stream B: Class Feature Paths
- Add level milestone unlocks with explicit option provenance.
- Ensure class advantages are visible and understandable.

### Stream C: Companion Synergy
- Add bounded composition modifiers for checks/combat support.

## Deliverables

- Non-combat spell interaction framework.
- Expanded class identity options in loops.
- Companion synergy rules + tests.

## Acceptance Criteria

- Every caster class has distinct non-combat utility options.
- Martial classes gain meaningful non-combat tactical options.
- Option origin is explicit in UI text.

## Risks and Mitigations

- **Risk:** feature bloat via too many one-off spell rules.
  - **Mitigation:** enforce hook taxonomy and reuse.
- **Risk:** class imbalance.
  - **Mitigation:** playtest matrix across class archetypes.

## Scope Estimate

Large (L)
