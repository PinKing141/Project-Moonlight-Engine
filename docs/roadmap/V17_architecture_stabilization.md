# V17 — Architecture Stabilization

## Implementation Status

**Implemented** (stabilization complete, 2026-03-02).

Current state summary:
- Bounded service extraction slices are in place (exploration/social/quest/town-economy/party facade routing).
- Architecture guardrails and contract-drift coverage exist.
- V17 verification gate passed (`tools/testing/verify_v17.ps1`): 95 passed.

## Duration

4–6 weeks

## Objective

Decompose orchestration hotspots to reduce coupling and regression risk before feature expansion.

## In Scope

1. Split current orchestration into bounded services:
   - Exploration application service
   - Social/dialogue application service
   - Quest application service
   - Town economy application service
   - Party application service
2. Keep a compatibility facade for existing presentation paths.
3. Remove direct application-layer dependencies on infrastructure helpers via interfaces/adapters.
4. Add contract-drift checks between declared contract and exposed intents.

## Out of Scope

- New gameplay mechanics.
- UI redesign.
- Save format changes unless required for parity.

## Work Breakdown

### Stream A: Service Decomposition
- Identify method clusters and extract by bounded context.
- Move shared policies into focused helper modules.
- Keep facade methods delegating to extracted services.

### Stream B: Layering Compliance
- Introduce interface ports for external/data loaders currently imported directly.
- Add architecture checks to prevent regressions.

### Stream C: Contract Reliability
- Expand application contract declarations.
- Add tests to fail on contract drift.

## Deliverables

- New service modules with preserved behavior.
- Contract verification tests.
- ADR documenting decomposition decisions.

## Acceptance Criteria

- Existing gameplay parity preserved.
- Deterministic replay scenarios remain stable.
- No prohibited application->infrastructure import paths.

## Risks and Mitigations

- **Risk:** hidden coupling emerges mid-refactor.
  - **Mitigation:** slice extraction behind facade method-by-method.
- **Risk:** accidental behavior drift.
  - **Mitigation:** golden transcript/replay checks per slice.

## Scope Estimate

Large (L)
