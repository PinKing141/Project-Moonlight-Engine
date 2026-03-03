# Project Moonlight Engine Master Roadmap (Governance + V17–V22a)

This is a single consolidated roadmap document covering governance and all phases from V17 through V22a.

## Roadmap Governance and Scope Controls

### Purpose
Define guardrails that keep delivery practical, testable, and deterministic.

### Portfolio Objectives
- Strengthen D&D feel through systemic gameplay depth.
- Preserve deterministic replayability.
- Reduce architectural risk before introducing large mechanics.

### Definition of Ready (DoR)
Every feature slice must include:
- Problem statement and player value.
- Determinism impact statement.
- In-scope and out-of-scope list.
- Data model impact summary.
- Test plan (unit + integration + replay where relevant).
- Rollout/fallback strategy.

### Definition of Done (DoD)
A slice is done only when:
- Acceptance criteria are met.
- Tests pass in CI/local target profile.
- Documentation updated (phase file + any gameplay references).
- No undocumented API/contract drift.
- No unresolved TODO/FIXME left in production path.

### Anti-Overcoding Controls
- **Complexity budget:** limit new public methods per service per phase.
- **Model budget:** reject schema/model expansion without ADR once limits are exceeded.
- **No speculative systems:** every implementation must map to a named acceptance criterion.

### Anti-Undercoding Controls
- Every user-facing mechanic requires explicit failure paths.
- Every new action requires at least one deterministic regression test.
- Every phase must include instrumentation/logging sufficient for triage.

### Determinism Rules
- Randomness only via centralized seed derivation pathways.
- Random context must be normalized and versioned when format changes.
- Replay fixtures required for branching systems (combat, social, exploration).

### Documentation and Repository Hygiene
- Keep roadmap docs under `docs/roadmap/`.
- Keep temporary planning drafts in ignored paths (see `.gitignore`).
- Capture only finalized artifacts in tracked files.

### Release Gate Checklist (Per Phase)
- [ ] Scope frozen (no mid-phase feature additions).
- [ ] Acceptance tests defined before implementation complete.
- [ ] Determinism replay checks green.
- [ ] Architecture checks (imports/layering) green.
- [ ] Docs updated.

---

## V17 — Architecture Stabilization

### Implementation Status
**Implemented** (stabilization complete, 2026-03-02; V17 verification gate passed with 95 tests).

### Duration
4–6 weeks

### Objective
Decompose orchestration hotspots to reduce coupling and regression risk before feature expansion.

### In Scope
1. Split current orchestration into bounded services:
   - Exploration application service
   - Social/dialogue application service
   - Quest application service
   - Town economy application service
   - Party application service
2. Keep a compatibility facade for existing presentation paths.
3. Remove direct application-layer dependencies on infrastructure helpers via interfaces/adapters.
4. Add contract-drift checks between declared contract and exposed intents.

### Out of Scope
- New gameplay mechanics.
- UI redesign.
- Save format changes unless required for parity.

### Work Breakdown
#### Stream A: Service Decomposition
- Identify method clusters and extract by bounded context.
- Move shared policies into focused helper modules.
- Keep facade methods delegating to extracted services.

#### Stream B: Layering Compliance
- Introduce interface ports for external/data loaders currently imported directly.
- Add architecture checks to prevent regressions.

#### Stream C: Contract Reliability
- Expand application contract declarations.
- Add tests to fail on contract drift.

### Deliverables
- New service modules with preserved behavior.
- Contract verification tests.
- ADR documenting decomposition decisions.

### Acceptance Criteria
- Existing gameplay parity preserved.
- Deterministic replay scenarios remain stable.
- No prohibited application->infrastructure import paths.

### Risks and Mitigations
- **Risk:** hidden coupling emerges mid-refactor.
  - **Mitigation:** slice extraction behind facade method-by-method.
- **Risk:** accidental behavior drift.
  - **Mitigation:** golden transcript/replay checks per slice.

### Scope Estimate
Large (L)

---

## V18 — D&D Feel Layer 1: Checks, Stealth, Consequences

### Implementation Status
**Implemented** (stabilization complete, 2026-03-02; V18 scoped verification gate passed).

### Duration
5–7 weeks

### Objective
Introduce core tabletop-style non-combat resolution and stealth gameplay.

### In Scope
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

### Out of Scope
- Full non-combat spell utility matrix.
- Crafting/professions.

### Work Breakdown
#### Stream A: Rule Engine
- Implement check resolution module and deterministic roll context contracts.
- Add structured result payloads (success, margin, consequence tags).

#### Stream B: Stealth in Exploration
- Add stealth actions and detection checks.
- Persist stealth-related state and escalation outcomes.

#### Stream C: Social Consequence Extension
- Expand social checks and consequence ladders.
- Add failure-forward outcomes (no dead-end loops).

### Deliverables
- Check resolution service.
- Stealth-capable wilderness/town action paths.
- New tests for deterministic branching outcomes.

### Acceptance Criteria
- Check outcomes are deterministic for identical seeds/contexts.
- At least 12 scenario tests cover pass/fail/escalation branches.
- Consequence states are visible and explainable in UX output.

### Risks and Mitigations
- **Risk:** stealth adds opaque state transitions.
  - **Mitigation:** explicit state labels in logs and UI summaries.
- **Risk:** check engine complexity leak into UI.
  - **Mitigation:** keep UI-facing DTO compact and semantic.

### Scope Estimate
Medium/Large (M/L)

---

## V19 — D&D Feel Layer 2: Resource Attrition & Rest Pressure

### Implementation Status
**Implemented** (feature set landed and regression-tested), pending optional formal closeout note parity with V21 format.

### Duration
4–6 weeks

### Objective
Make travel/rest choices strategically meaningful through bounded scarcity and recovery tradeoffs.

### In Scope
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

### Out of Scope
- Deep survival simulation.
- Dynamic weather simulation.

### Work Breakdown
#### Stream A: Data and Persistence
- Extend character/world flags for resource state.
- Add migration and in-memory parity handling.

#### Stream B: Rest and Recovery Logic
- Introduce short/long rest risk tables.
- Apply deterministic interruption outcomes.

#### Stream C: UX and Feedback
- Add concise pressure status summaries.
- Surface risk warnings before travel/rest confirmation.

### Deliverables
- Resource pressure subsystem.
- Rest risk and partial recovery outcomes.
- Regression tests for depletion/recovery loops.

### Acceptance Criteria
- Resource decisions affect near-term gameplay outcomes.
- No irreversible soft-lock from depletion.
- Deterministic parity for repeat runs.

### Risks and Mitigations
- **Risk:** over-punishing attrition reduces fun.
  - **Mitigation:** tune bounds and guarantee recovery paths.
- **Risk:** menu complexity creep.
  - **Mitigation:** aggregate state into compact status lines.

### Scope Estimate
Medium (M)

---

## V20 — Combat Depth: Reactions, Positioning, Roles

### Implementation Status
**Implemented** (stabilization complete, 2026-03-02; V20 scoped verification gate passed: 22 tests).

### Duration
5–8 weeks

### Objective
Deepen tactical combat identity while maintaining CLI readability and deterministic flow.

### In Scope
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

### Out of Scope
- Grid map tactical engine.
- Real-time combat systems.

### Work Breakdown
#### Stream A: Combat Timeline Model
- Add pre/post-turn reaction windows.
- Add clear event ordering and transcript markers.

#### Stream B: Player Action Model
- Add ready/reaction declaration paths.
- Ensure turn prompts remain concise.

#### Stream C: AI Role Logic
- Assign role templates and action weights.
- Add deterministic tactical decision hooks.

### Deliverables
- Combat timeline with reaction windows.
- Role-driven enemy behavior profiles.
- Test coverage for trigger resolution order.

### Acceptance Criteria
- Reaction triggers are clearly explained in logs.
- No ordering ambiguity in simultaneous trigger cases.
- Prompt complexity remains within defined UX budget.

### Risks and Mitigations
- **Risk:** excessive branching in combat loop.
  - **Mitigation:** strict trigger taxonomy and capped reaction opportunities.
- **Risk:** AI unpredictability breaks deterministic expectations.
  - **Mitigation:** seed-derived tactical selection only.

### Scope Estimate
Large (L)

---

## V21 — Class Identity & Non-Combat Magic Expansion

### Status
**Implementation Status:** **Implemented** (stabilized and closed).

Stabilization complete (2026-03-02).

Final stabilization gate passed with focused cross-phase verification:
- V19 + V20 + V21 broader gate: 136 passed.
- V21 social provenance polish gate: 74 passed.

This phase is considered closed for roadmap sequencing; follow-on work should be tracked under V22.

### Duration
6–9 weeks

### Objective
Make class fantasy meaningful in exploration, social, and town loops beyond damage output.

### In Scope
1. Utility spell hooks:
   - Detection
   - Traversal
   - Social leverage
   - Protective rituals
2. Class feature milestones reflected in non-combat choices.
3. Companion synergy effects tied to class/party composition.

### Out of Scope
- Full SRD spell parity.
- Summoning ecosystem.

### Work Breakdown
#### Stream A: Utility Spell Integration
- Define reusable world-interaction hooks.
- Wire selected spells to those hooks.

#### Stream B: Class Feature Paths
- Add level milestone unlocks with explicit option provenance.
- Ensure class advantages are visible and understandable.

#### Stream C: Companion Synergy
- Add bounded composition modifiers for checks/combat support.

### Deliverables
- Non-combat spell interaction framework.
- Expanded class identity options in loops.
- Companion synergy rules + tests.

### Acceptance Criteria
- Every caster class has distinct non-combat utility options.
- Martial classes gain meaningful non-combat tactical options.
- Option origin is explicit in UI text.

### Risks and Mitigations
- **Risk:** feature bloat via too many one-off spell rules.
  - **Mitigation:** enforce hook taxonomy and reuse.
- **Risk:** class imbalance.
  - **Mitigation:** playtest matrix across class archetypes.

### Scope Estimate
Large (L)

---

## V22 — Campaign Systems: Faction War, Crafting, Endgame

### Status
**Implementation Status:** **Implemented** (V22a and V22b closeout complete, 2026-03-02).

Active next roadmap phase (2026-03-02).

### Phase Split Strategy
V22 is executed in two controlled sub-phases to reduce integration risk:
- **V22a (active):** faction simulation foundation + quest arc generator v2 integration.
- **V22a (implemented):** faction simulation foundation + quest arc generator v2 integration.
- **V22b (implemented):** crafting/profession loop + endgame crisis framework foundation.

- [V22a — Faction Simulation & Quest Arc Foundation](./V22a_faction_quest_foundation.md) is completed.
- [V22b — Crafting & Endgame Foundation](./V22b_crafting_endgame_foundation.md) is completed.

### Duration
8–12 weeks (consider split: V22a and V22b)

### Objective
Deliver long-form campaign depth and replayability through faction dynamics, bounded crafting, and escalating endgame states.

### In Scope
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

### Out of Scope
- Sandbox city-builder systems.
- Infinite economy simulations.

### Work Breakdown
#### Stream A: Faction Simulation
- Define state machine and transition triggers.
- Add diplomacy and pressure effects to world progression.

#### Stream B: Crafting
- Implement minimal profession taxonomy.
- Add recipe unlock conditions and output balancing.

#### Stream C: Endgame Framework
- Define crisis phases and thresholds.
- Add scenario packs and outcome branches.

### Deliverables
- Faction diplomacy/conflict system.
- Crafting subsystem with progression hooks.
- Endgame scenario and branching outcomes.

### Acceptance Criteria
- Campaign states diverge significantly across different seeds.
- Crafting adds strategic value without replacing core loops.
- Endgame has recoverable and terminal paths with clear signposting.

### Risks and Mitigations
- **Risk:** runaway complexity across interacting subsystems.
  - **Mitigation:** split into V22a (faction+quest) and V22b (crafting+endgame) if needed.
- **Risk:** replay incoherence.
  - **Mitigation:** scenario validation harness for long-run state checks.

### Scope Estimate
Extra Large (XL)

---

## V22a — Faction Simulation & Quest Arc Foundation

### Status
Implemented (closeout complete, 2026-03-02).

### Implementation Progress (2026-03-02)
- ✅ Deterministic `faction_conflict_v1` normalization + per-turn transition tick integrated in world progression.
- ✅ Compact faction-conflict summary surfaced in town and faction-standings views.
- ✅ Town intervention path (`submit_pressure_relief_intent`) now persists explicit world consequences and de-escalates linked faction-conflict relations.
- ✅ Quest arc metadata v2 now syncs deterministic branch keys/signatures from faction/world state and is surfaced in quest board/journal summaries.
- ✅ Integration flow coverage added for town intervention -> world progression -> quest board branch visibility shift.
- ✅ Added 24-turn replay fixture proving stable faction-conflict + quest-arc signatures under identical seeds.

### Verification Evidence
- `python -m pytest tests/unit/test_v17_contract_drift.py tests/unit/test_event_bus_progression.py tests/unit/test_town_social_flow.py tests/unit/test_quest_journal_view.py tests/unit/test_quest_arc_flow.py` → 70 passed.
- `python -m pytest tests/test_game_logic.py -k pressure_relief` → 3 passed.
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

### Duration
3–5 weeks

### Objective
Establish deterministic faction-conflict progression and hook it into quest branching without introducing crafting/endgame scope.

### Scope
#### In Scope
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

#### Out of Scope (deferred to V22b)
- Crafting/profession loop implementation
- Endgame crisis phase implementation
- New economy subsystems beyond existing faction pressure hooks

### Determinism Impact Statement
- All new branching must resolve from centralized seed derivation and normalized context payloads.
- Faction transition contexts must include explicit versioned keys to preserve replay compatibility.

### Data Model Impact
- Extend `world.flags` with a bounded `faction_conflict_v1` envelope.
- Add quest arc v2 metadata keys under quest state without breaking existing quest read paths.

### Test Plan
- Unit:
  - Faction state transition determinism for identical seed/context
  - Quest arc branch selection determinism for identical seed/context
  - Intervention action consequence and persistence checks
- Integration:
  - Town -> intervention -> world progression -> quest board branch visibility
- Replay:
  - Golden long-run fixture for 20+ turns with stable faction/quest outcomes

### Acceptance Criteria
- At least two factions can transition state over time under deterministic rules.
- Quest board/journal reflects branch metadata conditioned by faction/world state.
- Intervention path produces explainable, persisted pressure outcomes.
- No contract drift in current presentation intents.

### Rollout & Fallback
- Gate behavior behind `faction_conflict_v1` presence checks and safe defaults.
- On failure, degrade to current static faction pressure behavior while preserving save compatibility.

### First Implementation Slice
1. Add `faction_conflict_v1` normalization helper in world progression.
2. Add deterministic transition tick with no UI changes.
3. Surface compact summary line in existing town/faction views.
4. Add targeted regression + replay fixture.

---

## V22b — Crafting & Endgame Foundation

### Status
Implemented (closeout complete, 2026-03-02).

### Implementation Progress (2026-03-02)
- ✅ Added bounded `crafting_v1` normalization in world progression with safe defaults and versioned envelope.
- ✅ Wired normalization into world progression tick loop for consistent save-state shape.
- ✅ Added deterministic tests for crafting envelope normalization and identical-run stability.
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
