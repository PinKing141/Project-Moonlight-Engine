# Roadmap Governance and Scope Controls

## Purpose

Define guardrails that keep delivery practical, testable, and deterministic.

## Portfolio Objectives

- Strengthen D&D feel through systemic gameplay depth.
- Preserve deterministic replayability.
- Reduce architectural risk before introducing large mechanics.

## Definition of Ready (DoR)

Every feature slice must include:

- Problem statement and player value.
- Determinism impact statement.
- In-scope and out-of-scope list.
- Data model impact summary.
- Test plan (unit + integration + replay where relevant).
- Rollout/fallback strategy.

## Definition of Done (DoD)

A slice is done only when:

- Acceptance criteria are met.
- Tests pass in CI/local target profile.
- Documentation updated (phase file + any gameplay references).
- No undocumented API/contract drift.
- No unresolved TODO/FIXME left in production path.

## Anti-Overcoding Controls

- **Complexity budget:** limit new public methods per service per phase.
- **Model budget:** reject schema/model expansion without ADR once limits are exceeded.
- **No speculative systems:** every implementation must map to a named acceptance criterion.

## Anti-Undercoding Controls

- Every user-facing mechanic requires explicit failure paths.
- Every new action requires at least one deterministic regression test.
- Every phase must include instrumentation/logging sufficient for triage.

## Determinism Rules

- Randomness only via centralized seed derivation pathways.
- Random context must be normalized and versioned when format changes.
- Replay fixtures required for branching systems (combat, social, exploration).

## Documentation and Repository Hygiene

- Keep roadmap docs under `docs/roadmap/`.
- Keep temporary planning drafts in ignored paths (see `.gitignore`).
- Capture only finalized artifacts in tracked files.

## Release Gate Checklist (Per Phase)

- [ ] Scope frozen (no mid-phase feature additions).
- [ ] Acceptance tests defined before implementation complete.
- [ ] Determinism replay checks green.
- [ ] Architecture checks (imports/layering) green.
- [ ] Docs updated.
