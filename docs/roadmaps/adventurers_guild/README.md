# Adventurers Guild Expansion Roadmap (Modular)

This roadmap converts the "Adventurers Guild" idea into implementation-ready slices without overbuilding or underbuilding.

## Current Baseline (already in engine)
- Deterministic world-progression envelopes are active (`faction_conflict_v1`, `crafting_v1`).
- Quest arc metadata v2 already tracks branch signatures from world/faction state.
- Existing quest loop and town/faction views are stable and covered by contract-drift tests.
- Difficulty presets currently exposed in character creation are `story`, `normal`, `hardcore`.

Use this baseline first; do not duplicate systems that already exist.

## Design Goals
- Add a **cross-faction occupation system** where Guild membership can coexist with any political/religious faction.
- Add a **tiered Guild rank loop** (Bronze → Silver → Gold → Diamond → Platinum) for solo and party play.
- Expand quest generation with significantly broader templates, constraints, and scaling controls.
- Introduce explicit **difficulty policy** including Hardcore house rules.
- Provide class-by-class level progression tables as a canonical balancing reference.

## Document Map (manageable files)
1. `faction_and_tiers.md` — Guild identity, rank mechanics, and coexistence rules.
2. `quest_generation_expansion.md` — Quest pipeline, template library, anti-repetition controls.
3. `difficulty_and_hardcore_rules.md` — 5 difficulty tiers and Hardcore modifiers.
4. `class_progression_tables.md` — Per-class level-by-level gain structure.

## Delivery Phases
- **Phase A (Data Contracts):** models/enums/DTOs for Guild occupation state only.
- **Phase B (Generation):** template-driven contract generation on top of existing quest arc v2 hooks.
- **Phase C (Gameplay Loop):** minimal board flow additions (accept/turn-in/rank checks/permits).
- **Phase D (Balancing):** reward/failure/pacing tuning and difficulty policy alignment.
- **Phase E (UX + Telemetry):** lightweight visibility, checklist UI, and repetition telemetry.

## Phase Gates (Checklist)

### Phase A — Data Contracts
- [ ] Define `guild_membership_status`, `guild_rank_tier`, `guild_role_mode` in one canonical contract location.
- [ ] Add bounded world/character payload shapes with safe defaults and version keys.
- [ ] Keep compatibility with current application contract (`v1.x` additive-only).
- [ ] Add unit tests for payload normalization and deterministic defaults.
- [ ] Out of scope: new board UI screens, new economy loops, new combat rules.

### Phase B — Quest Generation Integration
- [ ] Introduce template repository parity (in-memory + SQL) without replacing current quest service paths.
- [ ] Add novelty scoring/rejection sampling as a bounded post-selection pass.
- [ ] Reuse existing deterministic seed policy and branch signature conventions.
- [ ] Add output-spread simulation tests (100-run distribution + repeat protection checks).
- [ ] Out of scope: narrative rewrite engine, procedural dialogue framework overhaul.

### Phase C — Guild Gameplay Loop
- [ ] Add Guild board query/accept/turn-in intents as additive application surface.
- [ ] Implement promotion checks from contract completions, success ratio, reputation, conduct, and role competency.
- [ ] Enforce party-license gates by rank with clear failure reasons.
- [ ] Persist rank history + conduct incidents with deterministic consequence records.
- [ ] Out of scope: multiplayer assumptions, broad faction-engine rewrite.

### Phase D — Balancing + Difficulty Policy
- [ ] Map new five-tier policy onto existing `story/normal/hardcore` baseline via compatibility aliases first.
- [ ] Introduce hardcore toggles as opt-in modifiers, not forced defaults.
- [ ] Bind risk tiers to reward multipliers with anti-farming guardrails.
- [ ] Add deterministic regression tests for rewards, casualty pressure, and rest restrictions.
- [ ] Out of scope: class overhaul, global economy redesign.

### Phase E — UX + Telemetry
- [ ] Show rank card, promotion checklist, and upcoming unlock preview only in existing surfaces.
- [ ] Add quest-repetition telemetry (template family, biome, antagonist signature).
- [ ] Add post-contract summary lines for conduct and merit impact.
- [ ] Verify no contract drift and no replay-signature instability.
- [ ] Out of scope: large UI navigation redesign.

## Anti-Over/Under Programming Rules
1. Build only from active phase tasks.
2. No new abstraction without at least 2 immediate call sites.
3. Every new rule must map to one player-visible behavior.
4. Defer speculative features to backlog.
5. Add tests with each behavior change (unit first, integration where state/atomicity matters).
6. Keep quest templates data-driven (JSON/YAML/DB), not hardcoded branch forests.
7. Reuse existing deterministic envelopes and branch-signature logic before adding new state containers.
8. Any new intent/DTO must be additive and reflected in contract docs/tests in the same slice.

## Definition of Ready / Done (per slice)

### DoR
- [ ] Player value statement and single-slice objective are explicit.
- [ ] In-scope and out-of-scope are listed.
- [ ] Determinism impact statement is documented.
- [ ] Data model impact is bounded and versioned.
- [ ] Test plan includes unit + integration (+ replay if branching).

### DoD
- [ ] Acceptance checks pass.
- [ ] Contract-drift checks pass.
- [ ] Documentation updated in this folder + linked core docs.
- [ ] No unresolved TODO/FIXME in production path.
- [ ] Rollout/fallback behavior documented.

## Exit Criteria
- Guild loop playable from new game to rank promotion.
- Difficulty tiers measurably affect encounter outcomes and resource taxation.
- Quest variety score improves (template uniqueness, biome spread, objective spread).
- Class progression table is fully represented in game-facing data contracts.

## Explicit Non-Goals
- No replacement of existing quest arc v2 architecture.
- No breaking rename/removal of current application intents during `v1.x`.
- No broad refactor of unrelated services to "prepare" future phases.
