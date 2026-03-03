# Quest Generation Expansion ("x100" Depth Plan)

## Baseline to Reuse (already implemented)
- Quest arc metadata v2 with deterministic branch signatures is already active.
- Faction conflict context is already normalized and available for branch conditioning.
- Seed-policy determinism and replay checks are already part of core governance.

This plan extends those systems; it does not replace them.

## 1) Quest Generator v2 Objectives
- Increase quest variety by combining objective templates, context injectors, and consequence branches.
- Ensure quests reflect biome, faction tension, difficulty tier, and party composition.
- Avoid repetitive loops with explicit novelty scoring.

## 2) Pipeline
1. **Seed Intake:** world seed + region seed + guild rank + difficulty policy.
2. **Intent Selection:** choose macro intent (`rescue`, `purge`, `recover`, `escort`, etc.).
3. **Template Build:** instantiate objective chain from data template.
4. **Constraint Pass:** enforce world state, faction relations, availability windows.
5. **Risk/Reward Calibration:** match XP, currency, items, merits, and failure consequences.
6. **Narrative Enrichment:** inject rumors, named NPC hooks, and optional twists.
7. **Novelty Validation:** reject/re-roll low novelty against recent quest history.

### Pipeline Guardrails
- Keep each stage independently testable and skippable behind feature flags.
- Constraint pass must never return a dead-end; always provide fallback objective path.
- Novelty rejection must be bounded (max retries) to avoid generation stalls.

## 3) Template Families (new)
- Retrieval (artifact, medicine, intelligence packet)
- Elimination (named threat, nest collapse, ritual disruption)
- Rescue (civilian, scout squad, captured envoy)
- Escort (merchant, relic, diplomatic convoy)
- Recon (map anomaly, enemy route, weather hazard)
- Defense (hold point, protect convoy, evacuation line)
- Investigation (missing persons, corrupted official, counterfeit ring)
- Diplomacy (ceasefire terms, mediator transport, witness verification)
- Expedition (deep biome traversal with layered checkpoints)
- Hybrid arcs (2–5 stage mixed objective contracts)

## 4) Template Structure (data-first)
Each template should define:
- `objective_nodes`: ordered or branching stages
- `required_tags`: biome/faction/monster/system tags
- `forbidden_tags`: incompatible world states
- `difficulty_curve`: per-node escalation controls
- `failure_modes`: timeout, casualties, item loss, faction fallout
- `recovery_paths`: fallback objectives to avoid dead-end frustration
- `reward_profile`: base + streak + merit modifiers

### Schema Stability Rules
- Add explicit `template_version` and migration notes for each template set.
- Unknown fields must be ignored safely by readers during rollouts.
- Do not embed executable logic in template payloads.

## 5) Anti-Repetition Controls
- Cooldown buckets by objective family.
- Last-N signature exclusion (location + objective + antagonist).
- Biome rotation quotas.
- NPC quest giver uniqueness weighting.
- Consequence diversity requirement (not always same penalty type).

## 6) Rank-Aware Contract Generation
- Bronze: short, low-branch, tutorialized recovery paths.
- Silver: adds optional objectives and mild branching.
- Gold: introduces parallel objectives and timed pressure.
- Diamond: strategic dependencies across multiple settlements.
- Platinum: long arcs with persistent world impact and multi-contract continuity.

## 7) Required Implementation Tasks
- Introduce `QuestTemplateRepository` (in-memory + SQL parity).
- Add template versioning and migration-safe schema.
- Extend quest service with novelty scorer and rejection sampling.
- Add contract simulation tests to validate output spread and success-rate bounds.

## 8) Bounded Slice Plan (Checklist)

### QG-1: Repository + Schema Envelope
- [x] Add `QuestTemplateRepository` interface and in-memory implementation.
- [x] Define `template_version` and normalization/fallback behavior.
- [x] Add loader validation tests for malformed templates.
- [x] Out of scope (now requested): reward rebalance, UI-facing generation note surfacing.

### QG-2: SQL Parity + Migrations
- [x] Add SQL persistence + migration-safe reads/writes.
- [x] Add parity tests (in-memory vs SQL) for template retrieval and filtering.
- [x] Keep read path backward-compatible with existing quest generation defaults.
- [x] Out of scope (now requested): additive `quests_v2` schema envelope with legacy bridge.

### QG-3: Novelty Scorer Integration
- [x] Add novelty scoring against recent quest signatures.
- [x] Add bounded rejection sampling with deterministic retry seed derivation.
- [x] Add deterministic replay tests for identical seed/context outputs.
- [x] Out of scope (now requested): deterministic dynamic narrative payload synthesis.

### QG-4: Rank/Difficulty Conditioning
- [x] Apply guild rank and difficulty policy as data-driven constraints.
- [x] Validate Bronze/Silver accessibility floors are preserved.
- [x] Add tests for failure-path diversity and reward scaling bounds.
- [x] Out of scope (now requested): encounter strategy/profile hints for redesigned behavior hooks.

### QG-5: Telemetry + Tuning Hooks
- [x] Emit template-family/biome/antagonist repetition counters.
- [x] Add threshold alerts for repetition regressions.
- [x] Document tuning knobs and safe default values.
- [x] Out of scope (now requested): lightweight analytics snapshot/export envelope in world flags.

### Telemetry Tuning Knobs (safe defaults)
- `telemetry_recent_window`: `20` recent generated quests retained for repetition checks.
- `telemetry_repeat_alert_threshold`: `4` occurrences in recent window triggers a repetition alert.
- `novelty_recent_window`: `12` signatures used for novelty scoring.
- `novelty_min_score`: `0.50` minimum accepted novelty score before bounded fallback.
- `novelty_max_retries`: `3` deterministic retries before taking best candidate.

## 9) Success Metrics
- Unique template usage over 100 generated quests >= target threshold.
- Objective family distribution variance within configured band.
- Failure mode diversity metric above baseline.
- Player-facing repetition complaints reduced (telemetry + manual playtest notes).

## 10) Non-Goals (explicit)
- No replacement of current quest arc v2 branch-signature system.
- No free-form content generator that bypasses template constraints.
- No large service decomposition unless two immediate call sites exist.
