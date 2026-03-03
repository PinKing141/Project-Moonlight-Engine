# ADR — V17 Service Decomposition (Initial Slice)

## Status
Accepted (initial implementation slice)

Completed bounded extraction slices: exploration, social/dialogue, quest, town-economy, and party (facade-first with `_..._impl` preservation).

## Context
`GameService` has become a broad orchestration hotspot with mixed responsibilities across exploration, social, quests, town economy, and party management. This increases regression risk and slows phase delivery.

## Decision
1. Introduce bounded application-service modules:
   - `ExplorationApplicationService`
   - `SocialDialogueApplicationService`
   - `QuestApplicationService`
   - `TownEconomyApplicationService`
   - `PartyApplicationService`
2. Keep `GameService` as the compatibility facade used by presentation and tests.
3. Route exploration-facing intents through `ExplorationApplicationService` first while preserving existing behavior via internal `GameService` `_..._impl` methods.
4. Add architecture guardrail coverage to prevent direct runtime imports from `application.services` into `infrastructure` modules.

## Consequences
- Immediate behavior parity is preserved because public intent names and signatures remain on `GameService`.
- Decomposition can proceed method-cluster by method-cluster without UI/presentation breakage.
- Future slices can migrate social/quest/town/party logic from pass-through wrappers into isolated orchestration implementations.

## Follow-up (V17 next slices)
- Introduce explicit ports/interfaces for reference-world dataset loading and inject adapters in bootstrap.
- Maintain bounded-service delegation coverage via `tests/unit/test_v17_contract_drift.py`.
- Run consolidated V17 verification via `tools/testing/verify_v17.ps1`.
