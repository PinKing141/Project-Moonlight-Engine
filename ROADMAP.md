# Project Moonlight — Execution Roadmap (Tracked)

**Purpose:** Execute development strictly phase-by-phase, with measurable completion evidence and anti-overcoding controls.

**Current Mode:** CLI-first, architecture-safe, UI-ready via strict application contracts.

---

## 1) Operating Rules (Do Not Skip)

### Phase Lock Rule
- Work on **one phase at a time**.
- Do not start a phase until all exit gates for the current phase are met or explicitly waived.
- Any new idea discovered mid-phase is logged in **Backlog**, not implemented immediately.

### Scope Rule
- Every code change must map to a task ID in this roadmap.
- If a change does not map to a task ID, do not implement it.

### Redundancy Rule
Before coding any task, confirm all are true:
- Existing implementation cannot be reused with a small extension.
- New abstraction has immediate callers now (not hypothetical future usage).
- No duplicate path is created for the same behavior.
- No duplicated state is introduced.

### Definition of Done (Global)
A task is only complete when:
1. Acceptance criteria are met.
2. Targeted tests pass.
3. Architecture boundary checks pass.
4. Done evidence is recorded in this file.

---

## 2) Status Legend

- `Not Started`
- `In Progress`
- `Blocked`
- `Done`
- `Waived` (must include approver/date/reason)

---

## 3) Global Exit Gates (Applied to Every Phase)

1. **Scope Gate** — all changed files map to roadmap task IDs.
2. **Boundary Gate** — presentation does not directly access repositories/domain internals.
3. **Complexity Gate** — no duplicate API paths unless temporary migration tag exists.
4. **Quality Gate** — targeted tests for changed behavior pass.
5. **Docs Gate** — only behavior-relevant docs updates.
6. **Cleanup Gate** — temporary shims/deprecations include explicit removal criteria.

---

## 4) Global Checklists

### 4.1 Pre-Implementation Checklist
- [ ] Task ID selected and status set to `In Progress`.
- [ ] Non-goals for this task written down.
- [ ] Reuse check completed (no existing method can satisfy this cleanly).
- [ ] File change budget defined (expected files to touch).

### 4.2 Post-Implementation Checklist
- [ ] Acceptance criteria verified.
- [ ] Tests executed and results recorded.
- [ ] No architecture boundary violations introduced.
- [ ] No redundant code paths added.
- [ ] Done evidence filled in below.

### 4.3 Overcoding Stop Checklist
Stop implementation if any condition is true:
- [ ] You are adding abstractions with zero current consumers.
- [ ] You are building generalized framework for unimplemented features.
- [ ] You are duplicating behavior under a second API path without migration intent.
- [ ] You are editing files unrelated to the active task ID.

---

## 5) Phase Tracker

## Phase 1 — CLI/Application Decoupling Foundation

### Phase Goal
Make CLI the canonical client while separating presentation from infrastructure/domain details through application façades.

### Status
`Done`

### Completed Baseline (already done)
- `P1-T01` Canonical entrypoint alignment to `python -m rpg`.
- `P1-T02` Added initial UI-neutral DTOs.
- `P1-T03` Added initial GameService façade methods.
- `P1-T04` Migrated key presentation paths away from direct repo access.
- `P1-T05` Added legacy runtime deprecation behavior.
- `P1-T06` Extracted legacy compatibility bootstrap from presentation into `infrastructure` shim to satisfy presentation boundary gate.

### Remaining Tasks

#### `P1.6-T01` Combat Round ViewModel Intent
- **Status:** `Done`
- **Objective:** Provide combat round payload from application (player panel, enemy panel, options, scene context).
- **Acceptance Criteria:**
  - Presentation does not assemble combat state from domain objects directly.
  - UI consumes one intent payload per round.
- **Files (expected):**
  - `src/rpg/application/dtos.py`
  - `src/rpg/application/services/game_service.py`
  - `src/rpg/presentation/game_loop.py`
- **Tests:**
  - Add/adjust unit tests for payload completeness and action option availability.
- **Done Evidence:**
  - Commit/patch refs: Added combat round DTOs and intent builder in `src/rpg/application/dtos.py` and `src/rpg/application/services/game_service.py`; presentation consumption wired in `src/rpg/presentation/game_loop.py`.
  - Tests run + output summary: `pytest tests/test_game_logic.py tests/e2e/test_cli_flow.py` → `5 passed`.
  - Boundary check notes: Combat panel/state assembly moved into application intent payload (`combat_round_view_intent`); presentation renders DTO.

#### `P1.6-T02` Combat Action Intent Execution Contract
- **Status:** `Done`
- **Objective:** Route player action submission through explicit app intent method(s).
- **Acceptance Criteria:**
  - Presentation submits action intent and receives structured result.
  - No direct combat engine calls in presentation.
- **Files (expected):**
  - `src/rpg/application/services/game_service.py`
  - `src/rpg/presentation/game_loop.py`
- **Tests:**
  - Unit coverage for intent execution paths (attack/spell/dodge/flee).
- **Done Evidence:**
  - Commit/patch refs: Added `submit_combat_action_intent` and used it from presentation callback; presentation no longer calls combat engine directly (uses `combat_resolve_intent`).
  - Tests run + output summary: `pytest tests/test_game_logic.py tests/e2e/test_cli_flow.py` → `5 passed`.
  - Boundary check notes: Action submission now routes through explicit app intent mapping; no direct `combat_service` calls in presentation.

#### `P1.6-T03` Character Creation Strict Port Completion
- **Status:** `Done`
- **Objective:** Move any remaining UI-side data shaping for character creation into app responses.
- **Acceptance Criteria:**
  - Character creation UI only renders app-provided models.
  - No creation validation logic duplicated in presentation.
- **Files (expected):**
  - `src/rpg/application/dtos.py`
  - `src/rpg/application/services/character_creation_service.py`
  - `src/rpg/application/services/game_service.py`
  - `src/rpg/presentation/character_creation_ui.py`
- **Tests:**
  - Unit tests for creation option payloads and summary model.
- **Done Evidence:**
  - Commit/patch refs: Added creation option/class-detail formatting contracts in `src/rpg/application/services/character_creation_service.py` and `src/rpg/application/dtos.py`; removed presentation-side formatting logic in `src/rpg/presentation/character_creation_ui.py`.
  - Tests run + output summary: `pytest tests/unit/test_character_creation_races.py tests/test_game_logic.py tests/e2e/test_cli_flow.py` → `9 passed`.
  - Boundary check notes: Race/background/difficulty/class-detail rendering labels now come from application methods; validation remains centralized in `CharacterCreationService.validate_point_buy`.

### Phase 1 Exit Gates
- [x] All remaining Phase 1 tasks are `Done`.
- [x] `src/rpg/presentation` has no direct repository access.
- [x] Canonical runtime path documented and verified.
- [x] Targeted regression tests pass.

---

## Phase 2 — Determinism and Simulation Integrity

### Phase Goal
Ensure repeatable outcomes for the same seed + intent sequence.

### Status
`Done`

#### `P2-T01` RNG Injection Strategy
- **Status:** `Done`
- **Objective:** Replace global randomness in application-critical paths with injected RNG source.
- **Acceptance Criteria:**
  - No global `random` usage in deterministic core flows.
  - RNG source is configurable by orchestration.
- **Files (expected):**
  - `src/rpg/application/services/game_service.py`
  - `src/rpg/application/services/encounter_service.py`
  - `src/rpg/application/services/combat_service.py`
- **Tests:** deterministic unit tests for encounter/combat reproducibility.
- **Done Evidence:**
  - Commit/patch refs: RNG injection implemented in `src/rpg/application/services/encounter_service.py` (seeded RNG factory, removed global `random.seed`) and `src/rpg/application/services/combat_service.py` (instance RNG + `set_seed` API); orchestration seeding added in `src/rpg/application/services/game_service.py` (`combat_resolve_intent` context seed).
  - Determinism test scenarios + outputs: Added deterministic tests in `tests/test_game_logic.py` for repeatable encounter plans and combat outcomes under same context; ran `pytest tests/test_game_logic.py tests/unit/test_encounter_planning.py tests/e2e/test_cli_flow.py` → `11 passed`.
  - Current audit notes: Core simulation RNG now configurable/seeded in encounter and combat services; non-critical flavour text randomness remains for future tightening under Phase 2.

#### `P2-T02` Seed Derivation Contract
- **Status:** `Done`
- **Objective:** Centralize seed derivation from world + character + context.
- **Acceptance Criteria:**
  - Single seed derivation policy used by all relevant services.
  - Policy documented.
- **Done Evidence:**
  - Commit/patch refs: Added centralized seed policy module `src/rpg/application/services/seed_policy.py`; migrated encounter and combat seeding to `derive_seed(...)` in `src/rpg/application/services/encounter_service.py` and `src/rpg/application/services/game_service.py`.
  - Seed policy doc link: `README.md` deterministic seed contract section.

#### `P2-T03` Replayability Test Harness (Minimal)
- **Status:** `Done`
- **Objective:** Add lightweight tests that replay fixed intent sequences.
- **Acceptance Criteria:**
  - Same input script yields same outputs (or same state snapshot).
- **Done Evidence:**
  - Test files: `tests/unit/test_replay_harness.py`
  - Replay assertions summary: Added fixed-script replay tests that execute identical intent sequences across fresh service instances and assert matching encounter sequences + final state snapshots; validated with `pytest tests/unit/test_replay_harness.py tests/unit/test_seed_policy.py tests/test_game_logic.py tests/unit/test_encounter_planning.py tests/e2e/test_cli_flow.py` → `16 passed`.

### Phase 2 Exit Gates
- [x] Determinism tests pass consistently.
- [x] RNG policy centralized and enforced.
- [x] No hidden random side effects in core simulation loop.

---

## Phase 3 — Persistence Parity and Atomicity

### Phase Goal
Ensure in-memory and MySQL adapters behave equivalently for application contracts.

### Status
`Done`

#### `P3-T01` Repository Contract Parity Audit
- **Status:** `Done`
- **Objective:** Verify adapter parity for all app-used repository methods.
- **Acceptance Criteria:**
  - No adapter-specific assumptions in application layer.
- **Done Evidence:**
  - Audit matrix path: `docs/repository_parity_matrix.md`
  - Commit/patch refs: Added static parity audit tests in `tests/unit/test_repository_parity_audit.py` and matrix documentation in `docs/repository_parity_matrix.md`.
  - Test run summary: `pytest tests/unit/test_repository_parity_audit.py tests/test_game_logic.py tests/e2e/test_cli_flow.py` → `9 passed`.

#### `P3-T02` Atomic Save Boundaries
- **Status:** `Done`
- **Objective:** Guarantee world/character critical updates persist atomically.
- **Acceptance Criteria:**
  - Documented transaction boundaries in MySQL paths.
  - Integration test coverage for rollback scenarios.
- **Done Evidence:**
  - Integration tests run: `pytest tests/integration/test_atomic_persistence.py tests/unit/test_repository_parity_audit.py tests/test_game_logic.py tests/e2e/test_cli_flow.py` → `11 passed`.
  - Commit/patch refs: Added atomic persistence helper `src/rpg/infrastructure/db/mysql/atomic_persistence.py`; wired MySQL composition roots in `src/rpg/bootstrap.py` and `src/rpg/infrastructure/legacy_cli_compat.py`; updated `GameService` and `WorldProgression` persistence boundary hooks to support atomic outer transaction.

#### `P3-T03` Migration Reliability Pass
- **Status:** `Done`
- **Objective:** Validate clean install and upgrade migration execution.
- **Acceptance Criteria:**
  - Migrations pass on empty DB and incremental upgrade path.
- **Done Evidence:**
  - Commit/patch refs: Updated `src/rpg/infrastructure/db/migrations/_apply_all.sql` to use portable relative `SOURCE` paths and include the full numbered chain (`001..003`); fixed MySQL-incompatible syntax in `src/rpg/infrastructure/db/migrations/002_add_spell_table.sql` and `src/rpg/infrastructure/db/migrations/003_update_entity_combat.sql`; added migration-chain reliability tests in `tests/unit/test_migration_chain.py`; added Python migration runner `src/rpg/infrastructure/db/mysql/migrate.py` for CLI-independent execution.
  - Docs update: Updated MySQL setup instructions in `README.md` to use `python -m rpg.infrastructure.db.mysql.migrate` (+ `--dry-run`).
  - Test run summary: `C:/Users/Favour/Documents/Github/project-moonlight-main/.venv/Scripts/python.exe -m pytest tests/unit/test_mysql_migration_runner.py tests/unit/test_migration_chain.py tests/integration/test_atomic_persistence.py -q` → `8 passed`.
  - Dry-run execution summary: `C:/Users/Favour/Documents/Github/project-moonlight-main/.venv/Scripts/python.exe -m rpg.infrastructure.db.mysql.migrate --dry-run` resolved 6 SQL files / 136 statements across base schema + migrations.
  - Live execution summary (clean install): On local MySQL `8.4.8` at `127.0.0.1:3307`, executed `_apply_all.sql` and validated schema markers: `world` seeded (`world_rows = 1`), `spell` table present, `entity.armour_class` present, `character.hp_current` present.
  - Live execution summary (incremental upgrade): Executed baseline (`create_tables.sql` + `create_history_tables.sql` + `001`) followed by `002` and `003`, then validated `spell` table plus `entity` combat columns (`armour_class`, `attack_bonus`, `damage_dice`, `hp_max`, `kind`).
  - Environment note: `RPG_DATABASE_URL` set to `mysql+mysqlconnector://root@127.0.0.1:3307/rpg_game_clean` for live verification.

### Phase 3 Exit Gates
- [x] Adapter parity tests pass.
- [x] Atomicity behavior validated.
- [x] Migration checks complete.

---

## Phase 4 — Gameplay Systems Expansion (Architecture-Safe)

### Phase Goal
Add deeper systems (quests/factions/loot progression) through existing architecture, not UI shortcuts.

### Status
`Done`

#### `P4-T01` Faction Influence Loop
- **Status:** `Done`
- **Objective:** Introduce faction standing changes tied to events.
- **Acceptance Criteria:**
  - Faction outcomes applied through app/domain events.
- **Done Evidence:**
  - Commit/patch refs: Added event-driven faction standing handler in `src/rpg/application/services/faction_influence_service.py`; wired handler registration into composition roots in `src/rpg/bootstrap.py` and `src/rpg/infrastructure/legacy_cli_compat.py`; added safe publication and standings intent in `src/rpg/application/services/game_service.py`.
  - Domain event coverage summary: `MonsterSlain` events now update faction reputation/influence through `EventBus` subscriptions (no presentation-layer logic).
  - Tests run + output summary: `C:/Users/Favour/Documents/Github/project-moonlight-main/.venv/Scripts/python.exe -m pytest tests/unit/test_faction_influence.py tests/unit/test_event_bus_progression.py tests/test_game_logic.py -q` → `11 passed`.

#### `P4-T02` Quest Hook Framework (Minimal)
- **Status:** `Done`
- **Objective:** Add quest trigger/completion hooks integrated with world progression.
- **Acceptance Criteria:**
  - At least one quest flow end-to-end (trigger, state update, reward).
- **Done Evidence:**
  - Commit/patch refs: Added quest hook service `src/rpg/application/services/quest_service.py` (subscribed to `TickAdvanced` + `MonsterSlain`); wired handlers in `src/rpg/bootstrap.py` and `src/rpg/infrastructure/legacy_cli_compat.py`.
  - E2E scenario summary: `first_hunt` quest now triggers on world progression tick, tracks progress on monster slain events, marks completion, and awards XP/money to the slayer.
  - Tests run + output summary: `C:/Users/Favour/Documents/Github/project-moonlight-main/.venv/Scripts/python.exe -m pytest tests/unit/test_quest_service.py tests/unit/test_faction_influence.py tests/unit/test_event_bus_progression.py tests/test_game_logic.py -q` → `12 passed`.

#### `P4-T03` Loot and Reward Pipeline
- **Status:** `Done`
- **Objective:** Structured loot outcomes from encounters and quest rewards.
- **Acceptance Criteria:**
  - Rewards pass through app service contract and persistence.
- **Done Evidence:**
  - Commit/patch refs: Added application reward contract `RewardOutcomeView` in `src/rpg/application/dtos.py`; routed encounter rewards through `GameService.apply_encounter_reward_intent` in `src/rpg/application/services/game_service.py` with persistence-backed updates.
  - Unit + integration coverage summary: Added reward pipeline assertions in `tests/test_game_logic.py` (reward view payload, money/xp persistence, inventory reward item); validated with `C:/Users/Favour/Documents/Github/project-moonlight-main/.venv/Scripts/python.exe -m pytest tests/unit/test_quest_service.py tests/unit/test_faction_influence.py tests/unit/test_event_bus_progression.py tests/test_game_logic.py -q` → `13 passed`.

### Phase 4 Exit Gates
- [x] New systems exposed via app intents/events only.
- [x] No gameplay logic added in presentation.
- [x] Core feature tests pass.

---

## Phase 5 — Balance and Progression Tuning

### Phase Goal
Stabilize class progression, difficulty modes, and economy pacing.

### Status
`Done`

#### `P5-T01` Central Balance Tables
- **Status:** `Done`
- **Objective:** Consolidate tunable values in one source.
- **Acceptance Criteria:**
  - No duplicated formulas across services.
- **Done Evidence:**
  - Tunables file(s): `src/rpg/application/services/balance_tables.py` (`rest_heal_amount`, monster reward scaling, first-hunt quest tuning constants).
  - Commit/patch refs: `GameService` and `QuestService` formulas migrated to centralized balance helpers (`src/rpg/application/services/game_service.py`, `src/rpg/application/services/quest_service.py`).
  - Test run summary: `C:/Users/Favour/Documents/Github/project-moonlight-main/.venv/Scripts/python.exe -m pytest tests/unit/test_balance_tables.py tests/unit/test_quest_service.py tests/test_game_logic.py -q` → `10 passed`.

#### `P5-T02` Difficulty Preset Calibration
- **Status:** `Done`
- **Objective:** Validate mode deltas (Story/Standard/Hardcore) with measurable outcomes.
- **Acceptance Criteria:**
  - Test scenarios demonstrate expected differences.
- **Done Evidence:**
  - Calibration test summary: Added `tests/unit/test_difficulty_calibration.py` to verify default difficulty profiles map to centralized calibration values and preserve expected deltas (Story > Standard > Hardcore HP; incoming damage inverse ordering; Hardcore outgoing > Standard).
  - Commit/patch refs: Added centralized preset profile table in `src/rpg/application/services/balance_tables.py`; migrated `CharacterCreationService._default_difficulties` to read from this table.
  - Test run summary: `C:/Users/Favour/Documents/Github/project-moonlight-main/.venv/Scripts/python.exe -m pytest tests/unit/test_difficulty_calibration.py tests/unit/test_character_factory.py tests/unit/test_balance_tables.py -q` → `6 passed`.

#### `P5-T03` Progression Curve Validation
- **Status:** `Done`
- **Objective:** Verify XP/reward pacing through mid-game.
- **Acceptance Criteria:**
  - No dead progression states in tested paths.
- **Done Evidence:**
  - Simulation snapshots summary: Added `tests/unit/test_progression_curve.py` to simulate level 1→6 reward accumulation and assert positive per-level gains with mid-game growth over early-game values.
  - Test run summary: `C:/Users/Favour/Documents/Github/project-moonlight-main/.venv/Scripts/python.exe -m pytest tests/unit/test_difficulty_calibration.py tests/unit/test_progression_curve.py tests/unit/test_balance_tables.py tests/unit/test_character_factory.py -q` → `7 passed`.

### Phase 5 Exit Gates
- [x] Balance constants centralized.
- [x] Difficulty behavior validated.
- [x] Progression tests pass.

---

## Phase 6 — CLI Productization and Reliability

### Phase Goal
Harden CLI play session quality while preserving UI-agnostic architecture.

### Status
`Done`

#### `P6-T01` Save/Load Robustness
- **Status:** `Done`
- **Objective:** Ensure interruption-safe save/load behaviors.
- **Acceptance Criteria:**
  - Recovery paths tested for partial/invalid state.
- **Done Evidence:**
  - Commit/patch refs: Hardened MySQL world state loading/saving in `src/rpg/infrastructure/db/mysql/repos.py` to recover from malformed/non-dict `flags` payloads instead of crashing.
  - E2E save/load report: Added malformed-state recovery integration test `tests/integration/test_mysql_repositories.py::test_load_default_recovers_from_malformed_flags_payload`.
  - Test run summary: `C:/Users/Favour/Documents/Github/project-moonlight-main/.venv/Scripts/python.exe -m pytest tests/integration/test_mysql_repositories.py tests/integration/test_atomic_persistence.py -q` → `5 passed`.

#### `P6-T02` Input and Navigation Consistency
- **Status:** `Done`
- **Objective:** Ensure arrow-key UX consistency across all menus/flows.
- **Acceptance Criteria:**
  - All actionable menus support same control conventions.
- **Done Evidence:**
  - UX checklist report: Added shared key normalization in `src/rpg/presentation/menu_controls.py` (`UP/DOWN`, `W/S`, `ENTER`, `Q/ESC`) and applied it in class-detail menu flow (`src/rpg/presentation/character_creation_ui.py`).
  - Test run summary: `C:/Users/Favour/Documents/Github/project-moonlight-main/.venv/Scripts/python.exe -m pytest tests/unit/test_menu_controls.py tests/unit/test_character_creation_races.py -q` → `7 passed`.

#### `P6-T03` Error UX and Help Surface
- **Status:** `Done`
- **Objective:** Improve user-facing error messages and help prompts.
- **Acceptance Criteria:**
  - No raw tracebacks in expected user flows.
- **Done Evidence:**
  - Commit/patch refs: Improved top-level runtime error UX and help guidance in `src/rpg/__main__.py`; added in-menu help surface in `src/rpg/presentation/main_menu.py`; improved invalid action hinting in `src/rpg/application/services/game_service.py`.
  - Test coverage: Updated `tests/unit/test_main_entry_error_handling.py` to assert help surface output and absence of traceback text for handled errors.
  - Manual smoke notes: Runtime failures now return friendly messaging plus controls/help hints instead of raw traceback output.
  - Test run summary: `C:/Users/Favour/Documents/Github/project-moonlight-main/.venv/Scripts/python.exe -m pytest tests/unit/test_main_entry_error_handling.py tests/unit/test_menu_controls.py tests/test_game_logic.py -q` → `12 passed`.

### Phase 6 Exit Gates
- [x] CLI run quality validated by scripted smoke.
- [x] Input consistency checklist complete.
- [x] Error paths user-friendly and stable.

---

## Phase 7 — Future UI Adapter Contract

### Phase Goal
Finalize a stable command/query contract so web/desktop client can plug in cleanly.

### Status
`Done`

#### `P7-T01` Public App Contract Definition
- **Status:** `Done`
- **Objective:** Define versioned command/query contract for external adapters.
- **Acceptance Criteria:**
  - Contract documented and test-covered.
- **Done Evidence:**
  - Contract doc path: `docs/application_contract_v1.md`
  - Commit/patch refs: Added versioned contract artifact `src/rpg/application/contract.py` (commands, queries, DTO names, version).
  - Test run summary: `C:/Users/Favour/Documents/Github/project-moonlight-main/.venv/Scripts/python.exe -m pytest tests/unit/test_app_contract.py tests/unit/test_main_entry_error_handling.py tests/test_game_logic.py -q` → `12 passed`.

#### `P7-T02` Contract Compatibility Tests
- **Status:** `Done`
- **Objective:** Prevent accidental breaking changes in DTO/API payloads.
- **Acceptance Criteria:**
  - Contract tests fail on breaking changes.
- **Done Evidence:**
  - Commit/patch refs: Added compatibility guard suite `tests/unit/test_contract_compatibility.py` to pin command/query names and core DTO field sets.
  - Test run summary: `C:/Users/Favour/Documents/Github/project-moonlight-main/.venv/Scripts/python.exe -m pytest tests/unit/test_app_contract.py tests/unit/test_contract_compatibility.py tests/e2e/test_cli_flow.py -q` → `6 passed`.

### Phase 7 Exit Gates
- [x] Contract stable and versioned.
- [x] CLI verified as adapter over same contract.

---

## Phase 8 — Release Hardening (v1.0 CLI Core)

### Phase Goal
Prepare stable, documented, testable release of CLI RPG core.

### Status
`Done`

#### `P8-T01` Full Test Matrix Green
- **Status:** `Done`
- **Objective:** Run and stabilize full unit/integration/e2e suite.
- **Acceptance Criteria:**
  - CI-equivalent local test matrix passes.
- **Done Evidence:**
  - Full test report summary:
    - `tests/unit` → `47 passed` (`python -m pytest tests/unit -q`)
    - `tests/integration` → `7 passed` (`python -m pytest tests/integration -q`)
    - `tests/e2e` → `1 passed` (`python -m pytest tests/e2e -q`)
    - Root suites: `tests/test_game_logic.py` → `7 passed`; `tests/test_inmemory_repositories.py` → `7 passed`; `tests/test_mysql_repositories.py` → `1 passed`
    - Aggregate summary: `70 passed`, no failures in segmented full-matrix execution.

#### `P8-T02` Documentation and Runbook Completion
- **Status:** `Done`
- **Objective:** Ensure setup, operations, and troubleshooting docs are current.
- **Acceptance Criteria:**
  - New contributor can run game from docs only.
- **Done Evidence:**
  - Docs checklist completed by: Copilot (2026-02-24)
  - Commit/patch refs: Added contributor runbook `docs/contributor_runbook.md` with environment setup, in-memory/MySQL run paths, full test commands, and troubleshooting; linked from `README.md`.

#### `P8-T03` Release Checklist and Changelog
- **Status:** `Done`
- **Objective:** Define release package criteria and change notes.
- **Acceptance Criteria:**
  - Version tag readiness confirmed.
- **Done Evidence:**
  - Release checklist artifact: `docs/release_checklist_v1.md`
  - Changelog evidence: `ROADMAP.md` section 7 updated with phase completion entries through Phase 8.

### Phase 8 Exit Gates
- [x] Critical defects resolved.
- [x] Docs complete and accurate.
- [x] Release checklist complete.

---

## 6) Backlog (Not In Active Phase)

> Add items here with candidate IDs. Do not implement backlog items during active phase unless approved and re-scoped.

- `BL-T01` Content provider resilience + offline cache (D&D5e primary, Open5e fallback, local-first reads) — `Done` (2026-02-24)
- `BL-T02` Optional bounded flavour enrichment (Datamuse adjectives, env-gated, non-mechanical) — `Done` (2026-02-25)
- `BL-T03` Local SRD JSON provider adapter (offline-first runtime source) — `Done` (2026-02-25)
- `BL-T04` Provider strategy split (runtime vs import order) — `Done` (2026-02-25)
- `BL-T05` Cache prewarm CLI (dry-run + execute, runtime/import strategy) — `Done` (2026-02-25)

---

## 7) Change Log for This Roadmap

- **2026-02-24:** Initial tracked roadmap created with task IDs, per-phase exit gates, and done evidence fields.
- **2026-02-24:** Phase 3 closed: completed live MySQL clean-install and incremental-upgrade migration verification; updated P3-T03 to `Done` and all Phase 3 exit gates to checked.
- **2026-02-24:** Phase 4 started; completed `P4-T01` with event-driven faction influence updates and focused test coverage.
- **2026-02-24:** Completed `P4-T02` minimal quest hooks (trigger/progress/reward) via world/combat events with focused end-to-end tests.
- **2026-02-24:** Phase 4 closed by completing `P4-T03` reward pipeline contract + persistence checks and checking all Phase 4 exit gates.
- **2026-02-24:** Phase 6 closed by completing `P6-T03` error/help UX hardening and checking all Phase 6 exit gates.
- **2026-02-24:** Phase 7 started; completed `P7-T01` by publishing versioned app contract docs/artifact with compatibility tests.
- **2026-02-24:** Phase 7 closed by completing `P7-T02` compatibility guards and validating CLI adapter behavior over contract.
- **2026-02-24:** Phase 8 closed by completing full test-matrix validation, contributor runbook/docs refresh, and release checklist artifact creation.
- **2026-02-24:** Phase 5 started; completed `P5-T01` by centralizing balance constants/formulas into `balance_tables.py` and migrating service usage.
- **2026-02-24:** Phase 5 closed with calibrated difficulty profile tests (`P5-T02`) and progression curve simulation validation (`P5-T03`).
- **2026-02-24:** Phase 6 started; completed `P6-T01` by hardening malformed save-state recovery in MySQL world loading and adding integration coverage.
- **2026-02-24:** Completed `BL-T01` by adding a D&D 5e API infrastructure adapter, retry/backoff HTTP handling, local file cache with TTL/stale fallback, and a D&D5e-primary/Open5e-fallback content client wired into bootstrap and legacy CLI composition roots; validated via focused provider + race-flow regression tests.
- **2026-02-25:** Completed `BL-T02` by adding env-gated Datamuse flavour enrichment for encounter intros with strict bounds (max one extra line), timeout/retry controls, and safe fallback to existing templates; gameplay mechanics/state paths remain unchanged.
- **2026-02-25:** Completed `BL-T03` and `BL-T04` by adding a Local SRD JSON provider adapter and splitting provider factory strategies (runtime local-first vs import API-first), while preserving cache/stale fallback behavior and compatibility with existing service seams.
- **2026-02-25:** Completed `BL-T05` by adding `python -m rpg.infrastructure.prewarm_content_cache` with explicit `dry-run` and `execute` modes, selectable runtime/import provider strategy, target/page planning output, and focused unit coverage.
- **2026-02-25:** Completed `BL-T06` by adding Town Hub + Social v1 (`Visit Town` menu path, NPC interaction intents, deterministic social checks, and persisted NPC disposition/memory state in world flags).
- **2026-02-25:** Completed `BL-T07` by implementing Quest Arc v1 with explicit accept/progress/ready-to-turn-in/completed statuses, quest board interactions in town flow, reward payout on turn-in, and quest-driven world/faction consequence updates.
- **2026-02-25:** Completed `BL-T08` by implementing non-death failure branches (social rebuff, retreat penalties, quest expiry), consequence surfacing in town views, and non-combat quest advancement via social success.
- **2026-02-25:** Completed `BL-T09` by delivering bounded economy/training loop with faction-influenced pricing/availability and interaction unlocks (`Leverage Intel`, `Call In Favor`).
- **2026-02-25:** Completed `BL-T10` by shipping deterministic rumour board intel, faction-influenced rumour mix, and bounded rumour history pruning for replay-safe state growth.
- **2026-02-25:** Completed `BL-T11` by hardening cross-module UX consistency, including location-first root menu hierarchy (`Act`/`Travel`/`Rest`/`Character`/`Quit`) and focused regression verification.
- **2026-02-25:** Added runtime safety hardening for unreachable MySQL (`127.0.0.1:3307` class failures): bootstrap probe + automatic in-memory retry path in `python -m rpg`, with focused startup/error-handling tests.
- **2026-02-25:** Narrative Systems track started (`NS-T01…NS-T06`); completed `NS-T01` by adding deterministic world tension updates and seed-based narrative injection cadence through `StoryDirector` tick handlers (canonical + legacy composition roots).
- **2026-02-25:** Completed `NS-T02` by adding deterministic relationship graph updates with bounded history and integrating relationship-pressure reads into rumour selection.
- **2026-02-25:** Started `NS-T03` with minimal `story_seed` schema injection and first read integration into town/rumour flows.

---

## 8) Post-Core Module Plan (Before New Feature Coding)

### 8.1 Module Separation (Authoritative)

#### `MOD-01` Town Hub Module
- **Domain:** NPC profile/disposition entities, town services, faction-facing state.
- **Application:** `get_town_view_intent`, `get_shop_view_intent`, `accept_quest_intent`, `list_town_npcs_intent`.
- **Infrastructure:** town NPC/content repositories (in-memory + MySQL parity), seed data loaders.
- **Presentation:** single town menu flow (`Talk`, `Shop`, `Quest Board`, `Train`, `Leave`).

#### `MOD-02` Social Interaction Module
- **Domain:** personality archetype, disposition bands, social outcome rules.
- **Application:** `get_npc_interaction_intent`, `submit_social_approach_intent`.
- **Infrastructure:** memory/disposition persistence.
- **Presentation:** 3-option interaction loop (Friendly, Direct, Intimidate) via arrow keys.

#### `MOD-03` Quest Arc Module
- **Domain:** quest definition/state/progress/completion + world flag impact.
- **Application:** trigger/progress/turn-in intents and reward handoff.
- **Infrastructure:** quest state repositories + migration additions.
- **Presentation:** quest board, active quest status, completion prompts.

#### `MOD-04` Consequence & Failure Module
- **Domain:** retreat penalties, quest timeout, social failure effects, mild injury/debuff.
- **Application:** consequence resolution intents after each major action.
- **Infrastructure:** durable consequence state + expiry timestamps.
- **Presentation:** consequence summaries in post-action screen.

#### `MOD-05` Economy & Progression Identity Module
- **Domain:** shop pricing rules, gold sinks, faction price modifiers, non-combat progression unlocks.
- **Application:** buy/sell/train intents + progression effect intents.
- **Infrastructure:** inventory stock persistence + pricing calculators.
- **Presentation:** shop/training menu and clear cost breakdown.

#### `MOD-06` Information & Replayability Module
- **Domain:** rumours/intel quality, seed-driven variation, memory expiry/pruning policy.
- **Application:** rumour board intent and world-awareness summaries.
- **Infrastructure:** event-log compaction and deterministic generation helpers.
- **Presentation:** concise intel board + partial-information indicators.

### 8.2 Module Roadmap Sequence

#### `BL-T06` Town Hub + Social v1 (MOD-01 + MOD-02)
- **Status:** `Done`
- **Objective:** Introduce non-combat interaction loop in town.
- **Acceptance Criteria:**
  - Town menu available from main flow.
  - NPC interaction intent works with deterministic social check outcome.
  - Disposition changes persist and affect next interaction tone.
- **Done Evidence:**
  - Commit/patch refs: Added town/social DTOs in `src/rpg/application/dtos.py`; added `get_town_view_intent`, `get_npc_interaction_intent`, and `submit_social_approach_intent` in `src/rpg/application/services/game_service.py`; added `Visit Town` flow in `src/rpg/presentation/game_loop.py`; updated help text in `src/rpg/presentation/main_menu.py`.
  - Tests run + output summary: `pytest tests/unit/test_town_social_flow.py tests/test_game_logic.py -q` → `10 passed`.
  - Persistence note: NPC social state stores in `world.flags["npc_social"]` via existing world repository save path.

#### `BL-T07` Quest Arc v1 (MOD-03)
- **Status:** `Done`
- **Objective:** Structured quest loop tied to events and rewards.
- **Acceptance Criteria:**
  - Quest can be accepted, progressed, completed, and turned in.
  - Completion triggers reward and at least one world/faction state change.
  - Quest state survives save/load parity (in-memory + MySQL).
- **Done Evidence:**
  - Commit/patch refs: Added quest board DTOs in `src/rpg/application/dtos.py`; added `get_quest_board_intent`, `accept_quest_intent`, and `turn_in_quest_intent` in `src/rpg/application/services/game_service.py`; integrated `Quest Board` UI flow in `src/rpg/presentation/game_loop.py`; updated quest progression statuses in `src/rpg/application/services/quest_service.py` to support explicit turn-in.
  - Tests run + output summary:
    - `pytest tests/unit/test_quest_service.py tests/unit/test_quest_arc_flow.py -q` → `2 passed`
    - `pytest tests/test_game_logic.py -q` → `7 passed`
  - Consequence note: turn-in now grants rewards, sets `world.flags["quest_world_flags"]["first_hunt_turned_in"]`, and applies faction reputation/influence bump.

#### `BL-T08` Consequence & Failure v1 (MOD-04)
- **Status:** `Done`
- **Objective:** Failure branches that change world state (not just retry).
- **Acceptance Criteria:**
  - At least 3 non-death failure outcomes implemented.
  - Failure updates are visible in subsequent intents/views.
  - No combat-only resolution dependency for key quest paths.
- **Done Evidence:**
  - Commit/patch refs: Added consequence visibility to town DTOs in `src/rpg/application/dtos.py`; implemented consequence log helpers, social failure consequences, retreat penalty intent, and non-combat broker quest progression path in `src/rpg/application/services/game_service.py`; added active quest expiry-to-failed branch in `src/rpg/application/services/quest_service.py`; surfaced consequence summaries and flee consequence handling in `src/rpg/presentation/game_loop.py`.
  - Tests run + output summary:
    - `pytest tests/unit/test_failure_consequences.py tests/unit/test_quest_service.py tests/unit/test_quest_arc_flow.py tests/unit/test_town_social_flow.py -q` → `9 passed`
  - Consequence coverage note: Implemented and validated non-death outcomes for social rebuff disposition loss, retreat HP/gold penalty, and active quest timeout failure; added non-combat social success route to ready key quests for turn-in.

#### `BL-T09` Economy + Identity v1 (MOD-05)
- **Status:** `Done`
- **Objective:** Add strategic gold usage and non-combat progression effects.
- **Acceptance Criteria:**
  - Shop + training loop operational with bounded pricing.
  - Faction standing alters at least one price or availability path.
  - Progression unlock changes interaction options, not only stats.
- **Scaffold Evidence (first vertical slice):**
  - Commit/patch refs: Added economy/identity DTO contracts in `src/rpg/application/dtos.py`; added `get_shop_view_intent`, `buy_shop_item_intent`, `get_training_view_intent`, and `purchase_training_intent` plus interaction-unlock handling in `src/rpg/application/services/game_service.py`; wired `Shop` and `Training` town flows in `src/rpg/presentation/game_loop.py`.
  - Tests run + output summary: `pytest tests/unit/test_economy_identity_flow.py tests/unit/test_town_social_flow.py tests/unit/test_failure_consequences.py tests/unit/test_quest_arc_flow.py -q` → `11 passed`.
  - Scope note: This slice establishes bounded pricing, faction-based price adjustment, and a training unlock (`Leverage Intel`) that changes available NPC interaction options.
- **Done Evidence:**
  - Commit/patch refs: Extended training module with `watch_liaison_drills` faction-gated path and `captain_favor` interaction unlock in `src/rpg/application/services/game_service.py`; added training availability messaging contract in `src/rpg/application/dtos.py`; updated training menu state rendering in `src/rpg/presentation/game_loop.py`.
  - Tests run + output summary: `pytest tests/unit/test_economy_identity_flow.py tests/unit/test_town_social_flow.py tests/unit/test_failure_consequences.py tests/unit/test_quest_arc_flow.py -q` → `13 passed`.
  - Acceptance note: Economy now includes bounded shop pricing plus faction-based availability gating (wardens reputation requirement), and identity progression unlocks multiple social options (`Leverage Intel`, `Call In Favor`) that alter interaction choices rather than stats.

#### `BL-T10` Information + Replayability v1 (MOD-06)
- **Status:** `Done`
- **Objective:** Improve world readability and run-to-run variation safely.
- **Acceptance Criteria:**
  - Rumour board/intel path present with partial information.
  - Seed-driven variation affects at least 2 systems (e.g., NPC mood + rumours).
  - Memory/event pruning policy prevents unbounded state growth.
- **Scaffold Evidence (minimal rumour slice):**
  - Commit/patch refs: Added rumour DTO contracts in `src/rpg/application/dtos.py`; implemented `get_rumour_board_intent` with deterministic seed policy in `src/rpg/application/services/game_service.py`; wired `Rumour Board` town path in `src/rpg/presentation/game_loop.py`.
  - Tests run + output summary: `pytest tests/unit/test_rumour_board.py tests/unit/test_economy_identity_flow.py tests/unit/test_town_social_flow.py -q` → `11 passed`.
  - Scope note: Rumours now vary deterministically by world turn/threat and broker social state, include confidence labels for partial intel, and increase depth when intel training is unlocked.
- **Done Evidence:**
  - Commit/patch refs: Added bounded rumour history persistence/pruning (`world.flags["rumour_history"]`) and deterministic faction-standing influence on rumour mix in `src/rpg/application/services/game_service.py`.
  - Tests run + output summary: `pytest tests/unit/test_rumour_board.py tests/unit/test_town_social_flow.py tests/unit/test_economy_identity_flow.py -q` → `13 passed`.
  - Acceptance note: BL-T10 now includes partial-information rumour board UX, deterministic variation inputs spanning world turn/threat + social memory + faction standings, and explicit history pruning to prevent unbounded growth.

#### `BL-T11` Integration Hardening Pass (Cross-Module)
- **Status:** `Done`
- **Objective:** Stabilize module interactions and UX consistency.
- **Acceptance Criteria:**
  - Arrow-key consistency across all new menus.
  - Full targeted test matrix green for new modules.
  - Updated docs include new loop and troubleshooting guidance.
- **Done Evidence:**
  - Commit/patch refs: Refactored root loop to location-first hierarchy (`Act`/`Travel`/`Rest`/`Character`/`Quit`) in `src/rpg/presentation/game_loop.py`; added context/travel intents in `src/rpg/application/services/game_service.py` and `LocationContextView` in `src/rpg/application/dtos.py`; updated help text in `src/rpg/presentation/main_menu.py`; added gameplay loop quick reference and troubleshooting notes in `README.md`.
  - Tests run + output summary: `pytest tests/unit/test_town_social_flow.py tests/unit/test_quest_service.py tests/unit/test_quest_arc_flow.py tests/unit/test_failure_consequences.py tests/unit/test_economy_identity_flow.py tests/unit/test_rumour_board.py tests/test_game_logic.py tests/e2e/test_cli_flow.py -q` → `27 passed`.
  - Additional hardening verification: `pytest tests/unit/test_location_context_flow.py tests/unit/test_town_social_flow.py tests/unit/test_rumour_board.py tests/unit/test_economy_identity_flow.py tests/e2e/test_cli_flow.py -q` → `16 passed`.
  - Integration note: Verified town and submenus remain arrow-menu driven with consistent Back/Leave semantics and intent-only presentation interactions.

### 8.3 Exit Gates for Section 8
- [x] Each BL task links to changed files and tests.
- [x] Presentation remains intent-only (no domain/repo logic leakage).
- [x] Determinism preserved for seeded paths.
- [x] In-memory/MySQL behavior parity validated for new state.
- [x] Changelog evidence updated per completed BL task.

---

## 9) Narrative Systems Pivot (Procedural Narrative Engine)

### 9.1 Dominant Axis
- **Primary axis:** Political faction shifts.
- **Secondary support:** character drama, scarcity pressure, and non-combat moral trade-offs.

### 9.2 Narrative Systems Sequence

#### `NS-T01` Tension + Seed Cadence Foundation
- **Status:** `Done`
- **Objective:** Introduce deterministic narrative pacing primitives before adding new content volume.
- **Acceptance Criteria:**
  - World stores bounded narrative tension state (`0..100`).
  - Story cadence checks are deterministic and seed-derived.
  - Injection cadence cannot spam every turn (minimum spacing enforced).
- **Done Evidence:**
  - Commit/patch refs: Added `src/rpg/application/services/story_director.py` with `StoryDirector` + `register_story_director_handlers`; wired into canonical bootstrap (`src/rpg/bootstrap.py`) and legacy composition root (`src/rpg/infrastructure/legacy_cli_compat.py`).
  - Tests run + output summary: `pytest tests/unit/test_story_director.py tests/unit/test_main_entry_error_handling.py tests/e2e/test_cli_flow.py -q` → `8 passed`.
  - Determinism note: cadence seed uses `derive_seed("story.cadence", ...)` and records deterministic injection markers in `world.flags["narrative"]["injections"]`.

#### `NS-T02` Relationship Graph v1
- **Status:** `Done`
- **Objective:** Add deterministic relationship graph primitives (`faction↔faction`, `npc↔faction`, minimal `npc↔npc`).
- **Acceptance Criteria:**
  - Graph state persisted in world flags/repositories with bounded growth policy.
  - At least one existing flow (social or rumour generation) reads graph state.
  - Deterministic updates covered by focused unit tests.
- **Done Evidence:**
  - Commit/patch refs: Extended `StoryDirector` in `src/rpg/application/services/story_director.py` with deterministic relationship graph initialization and tick updates (`faction_edges`, `npc_faction_affinity`, bounded `history`); integrated first read path in rumour selection via relationship pressure bias in `src/rpg/application/services/game_service.py`.
  - Tests run + output summary: `pytest tests/unit/test_story_director.py tests/unit/test_rumour_board.py tests/unit/test_town_social_flow.py tests/e2e/test_cli_flow.py -q` → `16 passed`.
  - Determinism note: relationship updates derive seeds from `derive_seed("story.relationship.tick", ...)`; same seed + turn sequence produces identical graph snapshots.

#### `NS-T03` Story Seed Model v1
- **Status:** `Done`
- **Objective:** Convert quest-first framing into reusable story seeds (initiator, pressure, escalation, outcomes).
- **Acceptance Criteria:**
  - Seed schema and lifecycle implemented with clear state transitions.
  - At least one active seed can resolve through non-combat and combat branches.
  - Resolution mutates world/faction state and records narrative memory.
- **Scaffold Evidence (minimal seed wiring):**
  - Commit/patch refs: Extended `StoryDirector` in `src/rpg/application/services/story_director.py` to create/update bounded `world.flags["narrative"]["story_seeds"]` entries with deterministic seed metadata; wired active story-seed reads into `get_town_view_intent` and `get_rumour_board_intent` in `src/rpg/application/services/game_service.py`.
  - Tests run + output summary: `pytest tests/unit/test_story_director.py tests/unit/test_rumour_board.py tests/unit/test_town_social_flow.py tests/e2e/test_cli_flow.py -q` → `19 passed`.
  - Scope note: Current slice provides schema + visibility integration only; multi-path seed resolution and state mutation gates remain for completion.
- **Progress Evidence (non-combat resolution path):**
  - Commit/patch refs: Added deterministic non-combat resolution for active `merchant_under_pressure` seeds in `submit_social_approach_intent` (`src/rpg/application/services/game_service.py`), including resolution variant selection, world/faction mutation, seed status updates, and bounded narrative memory entries (`narrative.major_events`).
  - Tests run + output summary: `pytest tests/unit/test_story_seed_resolution.py tests/unit/test_story_director.py tests/unit/test_rumour_board.py tests/unit/test_town_social_flow.py tests/e2e/test_cli_flow.py -q` → `21 passed`.
- **Completion Evidence (combat resolution path):**
  - Commit/patch refs: Added deterministic combat resolution for active `merchant_under_pressure` seeds in `apply_encounter_reward_intent` (`src/rpg/application/services/game_service.py`) via `_resolve_active_story_seed_combat`, including lifecycle transition (`resolved_by = combat`), world/faction mutation, and bounded narrative memory/consequence recording.
  - Tests run + output summary: `pytest tests/unit/test_story_seed_resolution.py tests/unit/test_story_director.py tests/unit/test_rumour_board.py tests/unit/test_town_social_flow.py tests/e2e/test_cli_flow.py -q` → `22 passed`.
  - Acceptance note: Active seeds now resolve through both social and combat branches and are removed from active-seed rumour surfacing once resolved.

#### `NS-T04` Story Director v1
- **Status:** `Done`
- **Objective:** Expand director decisions beyond cadence into event-type selection and repetition controls.
- **Acceptance Criteria:**
  - Director evaluates tension + faction imbalance + recent narrative tag usage.
  - Injection output picks from at least 2 event categories.
  - Repetition guard prevents duplicate category spam in short windows.
- **Done Evidence:**
  - Commit/patch refs: Extended `StoryDirector` in `src/rpg/application/services/story_director.py` with deterministic injection category selection (`story_seed` vs `faction_flashpoint`) using tension, relationship-graph faction imbalance, and recent narrative tags; added short-window repetition guard that blocks back-to-back same-category injections within a bounded window.
  - Tests run + output summary: `pytest tests/unit/test_story_director.py tests/unit/test_story_seed_resolution.py tests/unit/test_rumour_board.py tests/unit/test_town_social_flow.py tests/e2e/test_cli_flow.py -q` → `24 passed`.
  - Determinism note: category selection and repetition fallback are seed-derived (`derive_seed("story.injection.kind", ...)`) and deterministic for identical seed + turn progression.

#### `NS-T05` Narrative Memory + Echoes
- **Status:** `Done`
- **Objective:** Ensure major events echo into future content surfaces.
- **Acceptance Criteria:**
  - Major events persisted with bounded retention and pruning policy.
  - Rumours/dialogue reflect at least one recent major event.
  - Replay tests confirm deterministic memory influence.
- **Done Evidence:**
  - Commit/patch refs: Extended narrative-memory read paths in `src/rpg/application/services/game_service.py` so major events echo into rumour board output (`memory:*` items from `Town Chronicle`), town consequences, and NPC interaction greetings; added deterministic memory fingerprinting/selection seeds for repeatable output and retained bounded memory pruning via `narrative.major_events` cap (`_append_story_memory`, max 20).
  - Tests run + output summary: `pytest tests/unit/test_rumour_board.py tests/unit/test_town_social_flow.py tests/unit/test_replay_harness.py tests/unit/test_story_director.py tests/unit/test_story_seed_resolution.py tests/e2e/test_cli_flow.py -q` → `30 passed`.
  - Determinism note: memory echo selection uses `derive_seed("story.memory.pick", ...)` and rumour-board composition seed includes memory fingerprint context.

#### `NS-T06` Simulation Batch Validation
- **Status:** `Done`
- **Objective:** Validate narrative arc quality and determinism across multi-run simulations.
- **Acceptance Criteria:**
  - Run a fixed batch of seeded simulations and record arc summaries.
  - Confirm deterministic replay under same seed + action script.
  - Document observed arc patterns and failure modes.
- **Done Evidence:**
  - Commit/patch refs: Added fixed-seed narrative simulation batch harness in `tests/unit/test_narrative_simulation_batch.py` (seeded script runner + arc summary extraction for injections/tension/story-seed lifecycle/memory/rumour signatures); documented run outputs and analysis in `docs/narrative_simulation_batch.md`.
  - Tests run + output summary: `pytest tests/unit/test_narrative_simulation_batch.py -q` → `2 passed`.
  - Narrative regression matrix: `pytest tests/unit/test_narrative_simulation_batch.py tests/unit/test_rumour_board.py tests/unit/test_town_social_flow.py tests/unit/test_replay_harness.py tests/unit/test_story_director.py tests/unit/test_story_seed_resolution.py tests/e2e/test_cli_flow.py -q` → `32 passed`.
  - Determinism note: batch replay assertions confirm identical arc summaries for identical seed list + script; summary metrics are driven by seed-policy-derived systems.

### 9.3 Exit Gates for Section 9
- [x] Narrative injections are cadence-limited and deterministic.
- [x] Relationship and memory state include explicit pruning bounds.
- [x] At least one story seed resolves through multi-path outcomes.
- [x] Director decisions are test-covered and traceable from stored state.
- [x] Full narrative-system regression matrix is green.

---

## 10) Narrative Quality Follow-On

### 10.1 Sequence

#### `NQ-T01` Flashpoint Resolution Parity
- **Status:** `Done`
- **Objective:** Ensure `faction_flashpoint` story seeds can resolve through both social and combat branches with deterministic outcomes.
- **Acceptance Criteria:**
  - Active `faction_flashpoint` seeds resolve through at least one non-combat branch.
  - Active `faction_flashpoint` seeds resolve through combat reward branch.
  - Resolution updates lifecycle/memory and suppresses active-seed rumour surfacing.
- **Done Evidence:**
  - Commit/patch refs: Extended social and combat resolution handlers in `src/rpg/application/services/game_service.py` to support both `merchant_under_pressure` and `faction_flashpoint`, with deterministic resolution variants and kind-specific world/faction effects.
  - Test coverage refs: Added flashpoint branch tests in `tests/unit/test_story_seed_resolution.py` for social and combat paths.
  - Tests run + output summary: `pytest tests/unit/test_story_seed_resolution.py tests/unit/test_narrative_simulation_batch.py tests/unit/test_story_director.py tests/unit/test_rumour_board.py tests/unit/test_town_social_flow.py tests/e2e/test_cli_flow.py -q` → `31 passed`.

#### `NQ-T02` Flashpoint Downstream Consequences
- **Status:** `Done`
- **Objective:** Add richer deterministic downstream consequences for `faction_flashpoint` outcomes beyond immediate threat/reputation deltas.
- **Acceptance Criteria:**
  - Flashpoint resolution applies deterministic multi-faction standing changes.
  - Flashpoint downstream effects are persisted in bounded narrative state.
  - A dedicated consequence entry surfaces aftershock outcomes in town-facing consequence feeds.
- **Done Evidence:**
  - Commit/patch refs: Added `_apply_flashpoint_downstream_effects(...)` in `src/rpg/application/services/game_service.py` and invoked it from both social/combat flashpoint resolution paths; persists bounded `narrative.flashpoint_echoes` and appends `flashpoint_aftershock` consequences.
  - Test coverage refs: Extended `tests/unit/test_story_seed_resolution.py` with aftershock assertions for social/combat channels, multi-faction standing impact checks, and same-seed determinism check for recorded echo rows.
  - Tests run + output summary: `pytest tests/unit/test_story_seed_resolution.py tests/unit/test_narrative_simulation_batch.py tests/unit/test_story_director.py tests/unit/test_rumour_board.py tests/unit/test_town_social_flow.py tests/e2e/test_cli_flow.py -q` → `32 passed`.

#### `NQ-T03` Flashpoint Echo Surface Integration
- **Status:** `Done`
- **Objective:** Make `flashpoint_echoes` first-class narrative outputs in rumour and dialogue surfaces.
- **Acceptance Criteria:**
  - Rumour board can emit deterministic flashpoint echo items.
  - NPC interaction greeting can echo flashpoint aftershocks when major-event memory is absent.
  - Rumour composition deterministically changes when flashpoint echo fingerprint changes.
- **Done Evidence:**
  - Commit/patch refs: Extended rumour/dialogue read paths in `src/rpg/application/services/game_service.py` with `_flashpoint_echo_rumour`, `_flashpoint_dialogue_hint`, deterministic selector `_pick_flashpoint_echo`, and fingerprint integration via `flashpoint_fingerprint` in rumour seed context.
  - Test coverage refs: Added flashpoint surfacing assertions in `tests/unit/test_rumour_board.py` and dialogue fallback coverage in `tests/unit/test_town_social_flow.py`.
  - Tests run + output summary: `pytest tests/unit/test_rumour_board.py tests/unit/test_town_social_flow.py tests/unit/test_story_seed_resolution.py tests/unit/test_narrative_simulation_batch.py tests/unit/test_story_director.py tests/e2e/test_cli_flow.py -q` → `35 passed`.

#### `NQ-T04` Flashpoint Severity Bands
- **Status:** `Done`
- **Objective:** Introduce deterministic graded severity bands for flashpoint echoes and surface them in player-facing narrative text.
- **Acceptance Criteria:**
  - Flashpoint echo rows persist normalized severity score and severity band.
  - Rumour and dialogue text include severity-band signal.
  - Deterministic fingerprints include severity so rumour composition remains reproducible under identical state.
- **Done Evidence:**
  - Commit/patch refs: Extended `src/rpg/application/services/game_service.py` with deterministic severity scoring (`_flashpoint_severity_score`) and band mapping (`_flashpoint_severity_band`); persisted `severity_score`/`severity_band` in `narrative.flashpoint_echoes`; threaded severity into `_flashpoint_echo_rumour`, `_flashpoint_dialogue_hint`, and `_flashpoint_echo_fingerprint`.
  - Test coverage refs: Updated `tests/unit/test_story_seed_resolution.py` to assert bounded severity persistence; expanded `tests/unit/test_rumour_board.py` and `tests/unit/test_town_social_flow.py` to validate severity presence in rumour/dialogue output.
  - Tests run + output summary: `pytest tests/unit/test_story_seed_resolution.py tests/unit/test_rumour_board.py tests/unit/test_town_social_flow.py tests/unit/test_narrative_simulation_batch.py tests/unit/test_story_director.py tests/e2e/test_cli_flow.py -q` → `35 passed`.

#### `NQ-T05` Severity-Coupled Simulation Pressure
- **Status:** `Done`
- **Objective:** Couple flashpoint severity into ongoing simulation pressure so severity impacts future narrative pacing and rumour depth.
- **Acceptance Criteria:**
  - StoryDirector tension target includes bounded contribution from recent flashpoint severity bands.
  - Rumour board depth and template priority include recent flashpoint pressure/bias signals.
  - Deterministic behavior remains stable under same seed + state.
- **Done Evidence:**
  - Commit/patch refs: Extended `StoryDirector` (`src/rpg/application/services/story_director.py`) with `_recent_flashpoint_pressure(...)` and integrated it into `_calculate_tension`; extended `GameService` (`src/rpg/application/services/game_service.py`) with flashpoint pressure score/bias helpers and wired them into rumour seed context, template prioritization, and depth selection.
  - Test coverage refs: Added `test_recent_flashpoint_echoes_raise_tension` in `tests/unit/test_story_director.py`; expanded `tests/unit/test_rumour_board.py` with flashpoint pressure depth and bias-priority assertions.
  - Tests run + output summary: `pytest tests/unit/test_story_director.py tests/unit/test_rumour_board.py tests/unit/test_story_seed_resolution.py tests/unit/test_town_social_flow.py tests/unit/test_narrative_simulation_batch.py tests/e2e/test_cli_flow.py -q` → `38 passed`.

#### `NQ-T06` Encounter Severity Coupling
- **Status:** `Done`
- **Objective:** Couple flashpoint severity into encounter-plan weighting/difficulty selection while preserving deterministic replay.
- **Acceptance Criteria:**
  - Explore encounter planning inputs (effective level/max enemies/faction bias) read bounded recent flashpoint pressure.
  - High pressure can raise encounter intensity and use latest flashpoint bias faction for weighting.
  - Low or stale pressure leaves base encounter context unchanged.
- **Done Evidence:**
  - Commit/patch refs: Extended `GameService` (`src/rpg/application/services/game_service.py`) with `_encounter_flashpoint_adjustments(...)` and wired `explore(...)` to use adjusted `player_level`, `max_enemies`, and `faction_bias`; adjustments derive from recent flashpoint severity score and latest flashpoint bias with bounded thresholds.
  - Test coverage refs: Added `test_flashpoint_pressure_adjusts_encounter_difficulty_context` and `test_low_flashpoint_pressure_keeps_base_encounter_context` in `tests/test_game_logic.py`.
  - Tests run + output summary: `pytest tests/test_game_logic.py tests/unit/test_story_director.py tests/unit/test_rumour_board.py tests/unit/test_story_seed_resolution.py tests/unit/test_town_social_flow.py tests/unit/test_narrative_simulation_batch.py tests/e2e/test_cli_flow.py -q` → `47 passed`.

#### `NQ-T07` Semantic Arc Scoring
- **Status:** `Done`
- **Objective:** Add deterministic semantic arc-scoring metrics to simulation batch validation so quality evaluation goes beyond structural counts.
- **Acceptance Criteria:**
  - Batch summaries include normalized semantic score and quality band.
  - Scoring remains deterministic under identical seed list + action script.
  - Validation report surfaces semantic scoring outputs and interpretation.
- **Done Evidence:**
  - Commit/patch refs: Extended `tests/unit/test_narrative_simulation_batch.py` with deterministic semantic scoring (`_semantic_arc_score`) and enriched summary fields (`semantic_arc_score`, `semantic_arc_band`) derived from resolution/event/category/tension/unresolved-pressure signals.
  - Report update refs: Updated `docs/narrative_simulation_batch.md` arc summary table and analysis sections with semantic score/band outputs for fixed seeds.
  - Tests run + output summary: `pytest tests/test_game_logic.py tests/unit/test_narrative_simulation_batch.py tests/unit/test_story_director.py tests/unit/test_rumour_board.py tests/unit/test_story_seed_resolution.py tests/unit/test_town_social_flow.py tests/e2e/test_cli_flow.py -q` → `47 passed`.

#### `NQ-T08` Calibrated Quality Targets + Alerts
- **Status:** `Done`
- **Objective:** Calibrate semantic-score evaluation against explicit design targets and emit threshold-based alerts in batch summaries.
- **Acceptance Criteria:**
  - Batch harness defines explicit target thresholds for semantic score, tension window, unresolved pressure, and event density.
  - Each summary includes deterministic `quality_status` and `quality_alerts` outputs.
  - Validation report documents target set and observed alert outcomes.
- **Done Evidence:**
  - Commit/patch refs: Extended `tests/unit/test_narrative_simulation_batch.py` with calibrated target constants plus deterministic `_quality_alerts(...)` and `_quality_status(...)`; summary outputs now include `quality_status` and `quality_alerts`.
  - Report update refs: Updated `docs/narrative_simulation_batch.md` with calibrated target section, status-rule definitions, and fixed-batch alert outcomes (`warn/pass/pass`).
  - Tests run + output summary: `pytest tests/test_game_logic.py tests/unit/test_narrative_simulation_batch.py tests/unit/test_story_director.py tests/unit/test_rumour_board.py tests/unit/test_story_seed_resolution.py tests/unit/test_town_social_flow.py tests/e2e/test_cli_flow.py -q` → `47 passed`.

#### `NQ-T09` Aggregate Quality Gates + Release Verdict
- **Status:** `Done`
- **Objective:** Add deterministic batch-level quality gates and release-readiness verdicts derived from aggregate pass/warn/fail distribution.
- **Acceptance Criteria:**
  - Batch harness computes aggregate gate metrics (`pass_rate`, `warn_count`, `fail_count`) against explicit target caps.
  - Gate output includes deterministic blockers list and `release_verdict` (`go` or `hold`).
  - Validation report documents aggregate gate targets and fixed-batch verdict.
- **Done Evidence:**
  - Commit/patch refs: Extended `tests/unit/test_narrative_simulation_batch.py` with deterministic `_batch_quality_gate(...)` plus threshold constants (`TARGET_MIN_PASS_RATE`, `TARGET_MAX_WARN_COUNT`, `TARGET_MAX_FAIL_COUNT`) and replay-stability test for gate outputs.
  - Report update refs: Updated `docs/narrative_simulation_batch.md` with batch-level gate target section and fixed-seed gate result (`release_verdict = go`).
  - Tests run + output summary: `pytest tests/test_game_logic.py tests/unit/test_narrative_simulation_batch.py tests/unit/test_story_director.py tests/unit/test_rumour_board.py tests/unit/test_story_seed_resolution.py tests/unit/test_town_social_flow.py tests/e2e/test_cli_flow.py -q` → `48 passed`.

#### `NQ-T10` Profile-Driven Gate Presets
- **Status:** `Done`
- **Objective:** Support deterministic quality-gate preset profiles (`strict`, `balanced`, `exploratory`) for the same simulation batch outputs.
- **Acceptance Criteria:**
  - Batch gate function accepts a profile selector and applies profile-specific threshold caps.
  - Profile selection is deterministic with safe fallback to `balanced` for unknown values.
  - Report includes fixed-batch verdict outcomes per profile.
- **Done Evidence:**
  - Commit/patch refs: Extended `tests/unit/test_narrative_simulation_batch.py` with `QUALITY_PROFILES`, `_quality_profile_thresholds(...)`, and profile-aware `_batch_quality_gate(..., profile=...)`; added test coverage for deterministic strict/balanced/exploratory verdict differences.
  - Report update refs: Updated `docs/narrative_simulation_batch.md` with profile preset targets and fixed-seed profile verdict table (`strict=hold`, `balanced=go`, `exploratory=go`).
  - Tests run + output summary: `pytest tests/test_game_logic.py tests/unit/test_narrative_simulation_batch.py tests/unit/test_story_director.py tests/unit/test_rumour_board.py tests/unit/test_story_seed_resolution.py tests/unit/test_town_social_flow.py tests/e2e/test_cli_flow.py -q` → `49 passed`.

#### `NQ-T11` Externalized Gate Configuration
- **Status:** `Done`
- **Objective:** Externalize gate profile/threshold policy so simulation quality rules can be adjusted without editing code.
- **Acceptance Criteria:**
  - Gate profile defaults can be selected via environment variable.
  - Profile thresholds can be overridden via environment and optional JSON config file.
  - Alert target thresholds can be overridden via environment variables.
- **Done Evidence:**
  - Commit/patch refs: Extended `tests/unit/test_narrative_simulation_batch.py` with env/file-backed config resolution (`_quality_targets`, `_quality_profiles_from_file`, `_resolved_quality_profiles`) and integrated these into quality alerting/profile gate thresholds.
  - Test coverage refs: Added environment and JSON file override tests (`test_default_profile_can_be_selected_via_environment`, `test_profile_thresholds_can_be_overridden_via_environment`, `test_profiles_can_be_loaded_from_json_file`).
  - Report update refs: Updated `docs/narrative_simulation_batch.md` with configuration override variables and JSON schema examples.
  - Tests run + output summary: `pytest tests/test_game_logic.py tests/unit/test_narrative_simulation_batch.py tests/unit/test_story_director.py tests/unit/test_rumour_board.py tests/unit/test_story_seed_resolution.py tests/unit/test_town_social_flow.py tests/e2e/test_cli_flow.py -q` → `52 passed`.

#### `NQ-T12` Runtime Gate Surface + Artifact Export
- **Status:** `Done`
- **Objective:** Expose quality gate/profile configuration through a runtime command/API surface and emit one-shot report artifacts outside the test harness.
- **Acceptance Criteria:**
  - Runtime module provides batch simulation API with deterministic summaries + aggregate gate verdict.
  - CLI command supports seed/script/profile selection and writes JSON artifact to disk.
  - Runtime path respects existing env/file gate profile overrides and has direct unit coverage.
- **Done Evidence:**
  - Commit/patch refs: Added runtime batch API in `src/rpg/application/services/narrative_quality_batch.py` (simulation runner, semantic scoring, alerting, profile-aware aggregate gates, report generation + artifact writer) and CLI entrypoint in `src/rpg/infrastructure/narrative_quality_report.py`.
  - Test coverage refs: Added `tests/unit/test_narrative_quality_report.py` covering deterministic report generation, artifact write path, and environment default-profile behavior.
  - Report update refs: Updated `docs/narrative_simulation_batch.md` with runtime command usage/artifact contract and adjusted remaining-gap notes.
  - README refs: Added runtime command examples in `README.md`.
  - Tests run + output summary: `pytest tests/test_game_logic.py tests/unit/test_narrative_simulation_batch.py tests/unit/test_narrative_quality_report.py tests/unit/test_story_director.py tests/unit/test_rumour_board.py tests/unit/test_story_seed_resolution.py tests/unit/test_town_social_flow.py tests/e2e/test_cli_flow.py -q` → `55 passed`.

### 10.2 Exit Gates for Section 10
- [x] Flashpoint resolution parity and downstream echoes are deterministic and test-covered.
- [x] Severity influences tension, rumours, and encounter planning through bounded state.
- [x] Semantic arc scoring, per-seed alerts, and aggregate release gates are implemented.
- [x] Quality gate profiles and threshold policy are externally configurable (env + JSON profile file).
- [x] Runtime batch quality command/API surface exists and emits deterministic report artifacts.

### 10.3 Roadmap Closeout Snapshot
- All roadmap phases and post-core tracks are now marked `Done`.
- No active implementation tasks remain in this roadmap document.
- Next work should begin by opening a new scoped section (or a v2 roadmap) with fresh task IDs and exit gates.

---

## 11) Roadmap V2 — Runtime Quality Operations

### 11.1 Sequence

#### `V2-T01` Session-End Quality Artifact Hook
- **Status:** `Done`
- **Objective:** Optionally emit a narrative quality artifact at the end of CLI sessions using current world/session context.
- **Acceptance Criteria:**
  - CLI shutdown flow can trigger report emission when explicitly enabled.
  - Hook is opt-in and does not alter gameplay outcomes or deterministic mechanics.
  - Artifact path and profile are configurable via environment variables.
- **Done Evidence:**
  - Commit/patch refs: Added env-gated session hook in `src/rpg/application/services/narrative_quality_batch.py` (`maybe_emit_session_quality_report`) with deterministic seed derivation from session world context and configurable output/profile/seed-count controls.
  - Presentation integration refs: Wired main-menu quit flow in `src/rpg/presentation/main_menu.py` to invoke session-end artifact emission and print saved path when emitted.
  - Test coverage refs: Added `tests/unit/test_session_quality_hook.py` covering no-op default behavior, enabled artifact write behavior, and main-menu quit hook invocation.
  - Tests run + output summary:
    - `pytest tests/unit/test_session_quality_hook.py tests/unit/test_narrative_quality_report.py -q` → `6 passed`.
    - `pytest tests/test_game_logic.py tests/unit/test_narrative_simulation_batch.py tests/unit/test_narrative_quality_report.py tests/unit/test_session_quality_hook.py tests/unit/test_story_director.py tests/unit/test_rumour_board.py tests/unit/test_story_seed_resolution.py tests/unit/test_town_social_flow.py tests/e2e/test_cli_flow.py -q` → `58 passed`.

#### `V2-T02` Report Schema Versioning + Compatibility Guard
- **Status:** `Done`
- **Objective:** Introduce explicit versioning for quality report artifacts and guard readers against incompatible schema changes.
- **Acceptance Criteria:**
  - Report payload includes a schema version field.
  - Loader/validator rejects unsupported versions with clear errors.
  - Existing report generation tests validate stable required keys.
- **Done Evidence:**
  - Commit/patch refs: Added schema contract constants and validation helpers in `src/rpg/application/services/narrative_quality_batch.py` (`REPORT_SCHEMA_NAME`, `REPORT_SCHEMA_VERSION`, `validate_quality_report_payload`, `read_quality_report_artifact`); report generation now emits `schema` metadata and artifact writes validate payload shape/version.
  - Runtime integration refs: Updated `src/rpg/infrastructure/narrative_quality_report.py` to validate generated payloads before write and expose `load_report_artifact(...)` using shared validator/loader.
  - Test coverage refs: Extended `tests/unit/test_narrative_quality_report.py` to assert schema fields on generated artifacts, acceptance of current schema version, and rejection of unsupported versions.
  - Tests run + output summary:
    - `pytest tests/unit/test_narrative_quality_report.py tests/unit/test_session_quality_hook.py -q` → `8 passed`.
    - `pytest tests/test_game_logic.py tests/unit/test_narrative_simulation_batch.py tests/unit/test_narrative_quality_report.py tests/unit/test_session_quality_hook.py tests/unit/test_story_director.py tests/unit/test_rumour_board.py tests/unit/test_story_seed_resolution.py tests/unit/test_town_social_flow.py tests/e2e/test_cli_flow.py -q` → `60 passed`.

#### `V2-T03` Config Surface Consolidation
- **Status:** `Done`
- **Objective:** Centralize narrative quality env/file configuration parsing into a single reusable config contract.
- **Acceptance Criteria:**
  - One module owns env/file parsing and default resolution.
  - Test harness and runtime command share identical config-resolution behavior.
  - Duplicate parsing logic removed without changing outputs.
- **Done Evidence:**
  - Commit/patch refs: Consolidated gate/profile config resolution into `src/rpg/application/services/narrative_quality_batch.py`; test harness now reuses shared `quality_targets(...)` and `quality_profile_thresholds(...)` instead of maintaining duplicate env/file parsing logic.
  - Test harness refs: Refactored `tests/unit/test_narrative_simulation_batch.py` to remove duplicated parsers and added parity assertion (`test_config_resolution_matches_runtime_service`) to confirm shared behavior under env overrides.
  - Runtime compatibility refs: Existing runtime report tests remain green with shared config path (`tests/unit/test_narrative_quality_report.py`).
  - Tests run + output summary:
    - `pytest tests/unit/test_narrative_simulation_batch.py tests/unit/test_narrative_quality_report.py -q` → `13 passed`.
    - `pytest tests/test_game_logic.py tests/unit/test_narrative_simulation_batch.py tests/unit/test_narrative_quality_report.py tests/unit/test_session_quality_hook.py tests/unit/test_story_director.py tests/unit/test_rumour_board.py tests/unit/test_story_seed_resolution.py tests/unit/test_town_social_flow.py tests/e2e/test_cli_flow.py -q` → `61 passed`.

#### `V2-T04` Batch Runner From Named Scripts
- **Status:** `Done`
- **Objective:** Add named script presets (e.g., `baseline`, `exploration_heavy`) to simplify repeatable quality runs.
- **Acceptance Criteria:**
  - CLI command accepts a named script profile in addition to raw action lists.
  - Script definitions are deterministic and documented.
  - Unknown script names fail fast with actionable error text.
- **Done Evidence:**
  - Commit/patch refs: Added named script presets and shared resolver in `src/rpg/application/services/narrative_quality_batch.py` (`SCRIPT_PRESETS`, `resolve_script(...)`) including explicit unknown-profile and conflicting-input validation.
  - Runtime integration refs: Extended `src/rpg/infrastructure/narrative_quality_report.py` with `--script-name` support and parser-level fast-fail errors for invalid script selection.
  - Test coverage refs: Expanded `tests/unit/test_narrative_quality_report.py` with named-profile success path plus failure-path assertions for unknown profiles and simultaneous `--script` + `--script-name` usage.
  - Tests run + output summary:
    - `pytest tests/unit/test_narrative_quality_report.py tests/unit/test_narrative_simulation_batch.py -q` → `16 passed`.
    - `pytest tests/test_game_logic.py tests/unit/test_narrative_simulation_batch.py tests/unit/test_narrative_quality_report.py tests/unit/test_session_quality_hook.py tests/unit/test_story_director.py tests/unit/test_rumour_board.py tests/unit/test_story_seed_resolution.py tests/unit/test_town_social_flow.py tests/e2e/test_cli_flow.py -q` → `64 passed`.

#### `V2-T05` Quality Trend Comparison Utility
- **Status:** `Done`
- **Objective:** Add a small utility to compare two report artifacts and summarize gate/score drift.
- **Acceptance Criteria:**
  - Utility reads two JSON artifacts and outputs deterministic deltas for score bands and gate verdict.
  - Output includes pass-rate delta and changed blocker sets.
  - Non-compatible reports are rejected with clear diagnostics.
- **Done Evidence:**
  - Commit/patch refs: Added `compare_report_artifacts(...)` in `src/rpg/infrastructure/narrative_quality_report.py` to compute deterministic deltas (gate verdict change, pass-rate delta, blocker add/remove sets, semantic band-count deltas) across two artifacts.
  - CLI integration refs: Extended runtime command with compare mode (`--compare-base`, `--compare-candidate`) that loads validated artifacts and renders deterministic JSON comparison output.
  - Compatibility refs: Compare mode reuses existing schema-compatible artifact loader and rejects incompatible artifacts with explicit diagnostics.
  - Test coverage refs: Extended `tests/unit/test_narrative_quality_report.py` with deterministic compare-output assertions, incompatible-schema rejection checks, compare-mode CLI success path, and missing-argument failure path.
  - Tests run + output summary:
    - `pytest tests/unit/test_narrative_quality_report.py -q` → `12 passed`.
    - `pytest tests/test_game_logic.py tests/unit/test_narrative_simulation_batch.py tests/unit/test_narrative_quality_report.py tests/unit/test_session_quality_hook.py tests/unit/test_story_director.py tests/unit/test_rumour_board.py tests/unit/test_story_seed_resolution.py tests/unit/test_town_social_flow.py tests/e2e/test_cli_flow.py -q` → `68 passed`.

#### `V2-T06` Operational Runbook + Release Gate Policy
- **Status:** `Done`
- **Objective:** Publish operational guidance for when to run quality checks and how to interpret `go/hold` outcomes.
- **Acceptance Criteria:**
  - Runbook documents minimal required commands and profile recommendations per workflow.
  - Release policy defines who can waive `hold` and how waivers are recorded.
  - Roadmap references are updated with final v2 evidence links.
- **Done Evidence:**
  - Runbook refs: Added `Narrative Quality Ops (Release Gate)` section in `docs/contributor_runbook.md` with required command sequence (baseline/candidate/compare), workflow profile recommendations, `go/hold` interpretation, and explicit waiver workflow.
  - Policy refs: Updated `docs/narrative_simulation_batch.md` with operational release policy summary and link to runbook policy section.
  - Governance refs: Waiver policy now specifies approvers and mandatory audit fields (artifact paths, blockers, reason, mitigation).
  - Verification note: This task is documentation/policy only; no runtime behavior changes were introduced.

### 11.2 Exit Gates for Section 11
- [x] Runtime quality artifact flow is available for both on-demand and session-end operation.
- [x] Report schema has explicit versioning and compatibility checks.
- [x] Config resolution for profiles/targets is single-source and reused by tests + runtime.
- [x] Named scripts and report comparison utility are deterministic and test-covered.
- [x] Operational runbook and release gate policy are published and linked.

### 11.3 Section 11 Closeout Snapshot
- All V2 tasks (`V2-T01` … `V2-T06`) are complete.
- Section 11 exit gates are fully satisfied.
- Next roadmap iteration should start in a new section with fresh task IDs and explicit exit gates.

---

## 12) Game Flow V3 — Loop Depth and Player Agency

### 12.1 Sequence

#### `GF3-T01` Destination Travel Flow
- **Status:** `Done`
- **Objective:** Replace one-step travel with explicit destination selection and travel outcome messaging.
- **Acceptance Criteria:**
  - Travel action opens a destination menu sourced from application intent data.
  - Selected destination updates location through application service contract only.
  - Canceled travel returns to loop without side effects.
- **Files (expected):**
  - `src/rpg/application/dtos.py`
  - `src/rpg/application/services/game_service.py`
  - `src/rpg/presentation/game_loop.py`
- **Tests:**
  - Add/extend unit tests for destination listing + selection execution.
  - Add CLI flow assertion for travel cancel/confirm branches.
- **Done Evidence:**
  - Commit/patch refs: Added travel destination DTO contract in `src/rpg/application/dtos.py`; added `get_travel_destinations_intent(...)` and destination-aware `travel_intent(..., destination_id=...)` in `src/rpg/application/services/game_service.py`; wired destination selection menu into `src/rpg/presentation/game_loop.py` with cancel-safe `Back` behavior.
  - Test coverage refs: Extended `tests/unit/test_location_context_flow.py` with destination list and explicit destination travel assertions.
  - Tests run + output summary: `pytest tests/unit/test_location_context_flow.py tests/e2e/test_cli_flow.py` → `5 passed`.

#### `GF3-T02` Defeat Consequence Flow
- **Status:** `Done`
- **Objective:** Replace generic blackout text with deterministic defeat consequences (resource loss, relocation, and recovery state).
- **Acceptance Criteria:**
  - Defeat applies bounded consequence package through app intent.
  - Recovery state is visible to player on return to loop.
  - Deterministic replay produces same consequence outcome under same seed/context.
- **Files (expected):**
  - `src/rpg/application/dtos.py`
  - `src/rpg/application/services/game_service.py`
  - `src/rpg/presentation/game_loop.py`
- **Tests:**
  - Unit coverage for consequence rules and persistence.
  - Deterministic replay assertion for defeat outcome.
- **Done Evidence:**
  - Commit/patch refs: Added deterministic defeat consequence application in `src/rpg/application/services/game_service.py` via `apply_defeat_consequence_intent(...)` (bounded gold loss, HP recovery, relocation to town, threat increase, persisted consequence row) and recovery visibility query `get_recovery_status_intent(...)`.
  - Presentation integration refs: Updated `src/rpg/presentation/game_loop.py` explore defeat branch to consume `apply_defeat_consequence_intent(...)` and display recovery status in the loop header path.
  - Test coverage refs: Added `test_defeat_consequence_applies_recovery_and_relocation` in `tests/unit/test_failure_consequences.py`.
  - Tests run + output summary: `pytest tests/unit/test_failure_consequences.py tests/unit/test_location_context_flow.py tests/e2e/test_cli_flow.py` → `10 passed`.

#### `GF3-T03` Quest Journal View
- **Status:** `Done`
- **Objective:** Add an in-loop quest journal screen with active/completed breakdown and progress details.
- **Acceptance Criteria:**
  - Character menu includes quest journal access without bypassing app layer.
  - Journal displays active, ready-to-turn-in, and completed quests with progress.
  - Empty-state messaging exists and returns cleanly to loop.
- **Files (expected):**
  - `src/rpg/application/dtos.py`
  - `src/rpg/application/services/game_service.py`
  - `src/rpg/presentation/game_loop.py`
- **Tests:**
  - Unit tests for journal grouping/sorting payload.
  - CLI flow coverage for open/close journal path.
- **Done Evidence:**
  - Commit/patch refs: Added quest journal DTO contract in `src/rpg/application/dtos.py` (`QuestJournalView`, `QuestJournalSectionView`); implemented grouped/sorted journal query in `src/rpg/application/services/game_service.py` (`get_quest_journal_intent(...)`) with status buckets for ready/active/completed/failed.
  - Presentation integration refs: Added Character submenu path in `src/rpg/presentation/game_loop.py` (`View Sheet`, `Quest Journal`, `Back`) and quest journal renderer with rich/plain fallback.
  - Test coverage refs: Added `tests/unit/test_quest_journal_view.py` for grouped section order and active-quest sorting assertions.
  - Tests run + output summary: `pytest tests/unit/test_quest_journal_view.py tests/unit/test_failure_consequences.py tests/unit/test_location_context_flow.py tests/e2e/test_cli_flow.py` → `11 passed`.

#### `GF3-T04` Equipment Management Screen
- **Status:** `Done`
- **Objective:** Add lightweight equipment management (view equipped + equip from inventory where valid).
- **Acceptance Criteria:**
  - Character screen shows equipment slots and currently equipped items.
  - Equip action validates slot compatibility via app intent.
  - Invalid equip attempts return structured message and no state mutation.
- **Files (expected):**
  - `src/rpg/domain/models/character.py`
  - `src/rpg/application/dtos.py`
  - `src/rpg/application/services/game_service.py`
  - `src/rpg/presentation/game_loop.py`
- **Tests:**
  - Unit tests for equip validation and mutation rules.
  - Regression test for unchanged inventory semantics.
- **Done Evidence:**
  - Commit/patch refs: Added equipment DTO contracts in `src/rpg/application/dtos.py` (`EquipmentView`, `EquipmentItemView`); implemented `get_equipment_view_intent(...)` and `equip_inventory_item_intent(...)` in `src/rpg/application/services/game_service.py` with slot validation and persisted equip state in character flags.
  - Presentation integration refs: Extended Character submenu in `src/rpg/presentation/game_loop.py` with `Equipment` path, equipped-slot/inventory rendering, and equip action loop.
  - Test coverage refs: Added `tests/unit/test_equipment_management.py` covering equipable detection, successful equip persistence, and rejection of non-equipable items.
  - Tests run + output summary: `pytest tests/unit/test_equipment_management.py tests/unit/test_quest_journal_view.py tests/unit/test_failure_consequences.py tests/unit/test_location_context_flow.py tests/e2e/test_cli_flow.py` → `14 passed`.

#### `GF3-T05` Explore Event Variety Pass
- **Status:** `Done`
- **Objective:** Expand explore outcomes with deterministic non-combat events (discoveries, hazards, and minor rewards).
- **Acceptance Criteria:**
  - Explore can yield non-combat event categories through app intent payload.
  - Event outcomes can modify money/items/flags via bounded rules.
  - Combat branch remains intact and deterministic.
- **Files (expected):**
  - `src/rpg/application/dtos.py`
  - `src/rpg/application/services/game_service.py`
  - `src/rpg/presentation/game_loop.py`
- **Tests:**
  - Unit tests for event selection determinism and reward bounds.
  - CLI flow coverage for at least one non-combat event path.
- **Done Evidence:**
  - Commit/patch refs: Added deterministic non-combat explore event pipeline in `src/rpg/application/services/game_service.py` via `_apply_noncombat_explore_event(...)` and wired it through `explore_intent(...)` for no-encounter outcomes; event categories include `discovery`, `cache`, and `hazard` with bounded money/HP/threat effects and persisted event/consequence state.
  - Runtime behavior refs: Existing combat explore branch remains unchanged; non-combat branch now surfaces event-specific messages through `ExploreView.message`.
  - Test coverage refs: Added `tests/unit/test_explore_event_variety.py` for no-encounter event emission, bounded effect assertions, consequence recording, and deterministic same-seed replay expectations.
  - Tests run + output summary: `pytest tests/unit/test_explore_event_variety.py tests/unit/test_equipment_management.py tests/unit/test_quest_journal_view.py tests/unit/test_failure_consequences.py tests/unit/test_location_context_flow.py tests/e2e/test_cli_flow.py` → `16 passed`.

### 12.2 Exit Gates for Section 12
- [x] All `GF3-T01` … `GF3-T05` tasks are complete with done evidence.
- [x] New flow surfaces are exposed via application intents only (no presentation-layer gameplay logic).
- [x] Deterministic behavior is preserved for seeded replay paths.
- [x] Targeted unit/e2e coverage exists for each new flow surface.

### 12.3 Scope Notes
- This section focuses on gameplay flow depth, not new rendering frameworks.
- Keep implementation additive and architecture-safe; avoid parallel duplicate APIs.

### 12.4 Section 12 Closeout Snapshot
- All Game Flow V3 tasks (`GF3-T01` … `GF3-T05`) are complete.
- Core loop now includes destination travel selection, defeat recovery consequences, quest journal access, equipment management, and deterministic non-combat explore events.
- Focused V3 regression suite remains green (`16 passed` on latest combined run).
- Next iteration should start as a new roadmap section with fresh task IDs and exit gates.

---

## 13) Combat + UX Parity V4 — Equipment Fidelity and Explore Readiness

### 13.1 Sequence

#### `V4-T01` Equipment-to-Combat Stat Binding
- **Status:** `Done`
- **Objective:** Make equipped slots authoritative for combat stat derivation (AC/attack/damage modifiers), instead of inventory-string heuristics.
- **Acceptance Criteria:**
  - Combat stat derivation reads equipped slot state first.
  - Inventory presence alone does not grant equipped benefits.
  - Backward compatibility fallback remains safe when no equipment is set.
- **Files (expected):**
  - `src/rpg/application/services/combat_service.py`
  - `src/rpg/application/services/game_service.py`
  - `tests/unit/test_equipment_management.py`
  - `tests/test_game_logic.py`
- **Tests:**
  - Unit tests for equipped weapon/armor effects.
  - Regression for non-equipped inventory items not altering derived stats.
- **Done Evidence:**
  - Commit/patch refs: Updated `src/rpg/application/services/combat_service.py` to make equipped slot state authoritative for weapon profile and AC when equipment flags are present, with safe fallback to existing inventory/class derivation when no equipment slots are set.
  - Integration refs: Existing equipment state from `src/rpg/application/services/game_service.py` is now consumed by combat stat derivation through `player.flags["equipment"]`.
  - Test coverage refs: Extended `tests/unit/test_equipment_management.py` with combat-stat assertions for slot-authoritative behavior and fallback behavior.
  - Tests run + output summary: `pytest tests/unit/test_equipment_management.py tests/test_game_logic.py tests/e2e/test_cli_flow.py` → `15 passed`.

#### `V4-T02` Explore Readiness Fallback Removal
- **Status:** `Done`
- **Objective:** Remove placeholder explore fallback branches and always route through deterministic explore result surfaces.
- **Acceptance Criteria:**
  - Explore flow no longer prints "coming later"/"not ready yet" placeholder branches.
  - Service returns structured explore outcome even when combat is unavailable.
  - Player-facing messaging remains clear and deterministic.
- **Files (expected):**
  - `src/rpg/presentation/game_loop.py`
  - `src/rpg/application/services/game_service.py`
  - `tests/e2e/test_cli_flow.py`
- **Tests:**
  - E2E assertion for explore behavior without combat-ready branch.
  - Unit assertions for deterministic non-combat fallback outcome.
- **Done Evidence:**
  - Commit/patch refs: Updated `src/rpg/application/services/game_service.py` so `explore_intent` now returns a structured deterministic non-combat fallback when enemies are generated but combat is unavailable, rather than surfacing readiness placeholders.
  - Presentation refs: Updated `src/rpg/presentation/game_loop.py` to remove placeholder branches (`encounters coming later` / `combat system is not ready yet`) and rely on the explore intent payload.
  - Test coverage refs: Added deterministic fallback unit coverage in `tests/unit/test_explore_event_variety.py` and placeholder-removal assertion in `tests/e2e/test_cli_flow.py`.
  - Tests run + output summary: `pytest tests/unit/test_explore_event_variety.py tests/e2e/test_cli_flow.py` → `5 passed`.

#### `V4-T03` Quest/Rumour Empty-State UX Upgrade
- **Status:** `Done`
- **Objective:** Replace minimal empty-state text with richer guidance and next-step hints while preserving architecture boundaries.
- **Acceptance Criteria:**
  - Empty quest board includes actionable guidance for unlocking quests.
  - Empty rumour board includes guidance on refresh cadence and influencing factors.
  - Messages originate from app intent or stable presentation templates (no duplicated gameplay rules).
- **Files (expected):**
  - `src/rpg/application/services/game_service.py`
  - `src/rpg/presentation/game_loop.py`
  - `tests/unit/test_quest_journal_view.py`
  - `tests/unit/test_rumour_board.py`
- **Tests:**
  - Unit tests for empty-state payload/message presence.
  - CLI rendering path coverage.
- **Done Evidence:**
  - Commit/patch refs: Added `empty_state_hint` payload fields to `QuestBoardView` and `RumourBoardView` in `src/rpg/application/dtos.py`, and populated them in `src/rpg/application/services/game_service.py` with actionable guidance.
  - Presentation refs: Updated `src/rpg/presentation/game_loop.py` to render app-provided empty-state hints for quest and rumour boards.
  - Test coverage refs: Extended `tests/unit/test_quest_journal_view.py` and `tests/unit/test_rumour_board.py` with empty-state hint assertions; kept CLI path coverage in `tests/e2e/test_cli_flow.py`.
  - Tests run + output summary: `pytest tests/unit/test_quest_journal_view.py tests/unit/test_rumour_board.py tests/e2e/test_cli_flow.py` → `18 passed`.

#### `V4-T04` Section 13 Regression + Determinism Audit
- **Status:** `Done`
- **Objective:** Validate combined Section 13 behavior across equipment, explore, and town surfaces.
- **Acceptance Criteria:**
  - Focused regression suite passes with new behavior.
  - Deterministic replay baseline remains stable for unchanged scripts.
  - Roadmap done evidence records command outputs.
- **Files (expected):**
  - `tests/unit/test_replay_harness.py`
  - `tests/unit/test_equipment_management.py`
  - `tests/e2e/test_cli_flow.py`
  - `ROADMAP.md`
- **Tests:**
  - Focused multi-file pytest run including replay harness + e2e flow.
- **Done Evidence:**
  - Command run: `pytest tests/unit/test_replay_harness.py tests/unit/test_equipment_management.py tests/unit/test_explore_event_variety.py tests/unit/test_quest_journal_view.py tests/unit/test_rumour_board.py tests/e2e/test_cli_flow.py`
  - Output summary: `29 passed`.
  - Determinism signal: `tests/unit/test_replay_harness.py` remains green in the combined Section 13 suite.

### 13.2 Exit Gates for Section 13
- [x] Equipment effects in combat are slot-authoritative and tested.
- [x] Explore flow has no placeholder readiness messaging branches.
- [x] Quest/Rumour empty states are informative and deterministic.
- [x] Focused regression + determinism suite passes and is recorded.

### 13.3 Scope Notes
- Section 13 is a parity/polish pass: no new game systems beyond listed tasks.
- Keep changes bounded to application/presentation contracts without repository contract churn.

---

## 14) UX Guidance Parity V5 — Remaining Empty-State Contract Alignment

### 14.1 Sequence

#### `V5-T01` Quest Journal Empty-State Contractization
- **Status:** `Done`
- **Objective:** Move quest journal empty-state copy from presentation fallback into application intent payloads for consistency with quest/rumour board behavior.
- **Acceptance Criteria:**
  - Quest journal intent includes actionable empty-state guidance.
  - CLI quest journal rendering consumes app-provided message in plain and Rich paths.
  - Unit test verifies hint payload presence/content.
- **Files (expected):**
  - `src/rpg/application/dtos.py`
  - `src/rpg/application/services/game_service.py`
  - `src/rpg/presentation/game_loop.py`
  - `tests/unit/test_quest_journal_view.py`
- **Tests:**
  - Focused unit + e2e adjacency run for quest journal path.
- **Done Evidence:**
  - Commit/patch refs: Added `empty_state_hint` to `QuestJournalView` and populated it in `get_quest_journal_intent`.
  - Presentation refs: Updated quest journal rendering in `src/rpg/presentation/game_loop.py` to display intent-provided guidance in both Rich and plain-text branches.
  - Test coverage refs: Added `test_quest_journal_exposes_empty_state_guidance` in `tests/unit/test_quest_journal_view.py`.
  - Tests run + output summary: `pytest tests/unit/test_quest_journal_view.py tests/e2e/test_cli_flow.py` → `5 passed`.

#### `V5-T02` Faction Standings Empty-State Guidance
- **Status:** `Done`
- **Objective:** Replace hard-coded faction standings empty text with application-owned actionable guidance.
- **Acceptance Criteria:**
  - Intent payload includes deterministic empty-state hint.
  - Presentation shows app hint without embedding gameplay rules.
  - Unit coverage asserts hint presence for no-standings state.
- **Files (expected):**
  - `src/rpg/application/dtos.py`
  - `src/rpg/application/services/game_service.py`
  - `src/rpg/presentation/game_loop.py`
  - `tests/unit/test_faction_influence.py`
- **Tests:**
  - Unit assertions for empty-state hint payload and standings passthrough.
  - CLI adjacency regression path.
- **Done Evidence:**
  - Commit/patch refs: Added `FactionStandingsView` in `src/rpg/application/dtos.py` and introduced `get_faction_standings_view_intent` in `src/rpg/application/services/game_service.py` with deterministic, actionable empty-state guidance.
  - Presentation refs: Updated `src/rpg/presentation/game_loop.py` to render app-provided standings view/hint instead of hard-coded empty text.
  - Test coverage refs: Extended `tests/unit/test_faction_influence.py` with standings view intent tests for empty and populated states.
  - Tests run + output summary: `pytest tests/unit/test_faction_influence.py tests/e2e/test_cli_flow.py` → `6 passed`.

#### `V5-T03` V5 Regression + Determinism Spot Check
- **Status:** `Done`
- **Objective:** Validate all V5 contractized empty-state paths remain deterministic and stable.
- **Acceptance Criteria:**
  - Focused regression suite passes.
  - Replay harness remains green.
  - Roadmap records command + output evidence.
- **Files (expected):**
  - `tests/unit/test_replay_harness.py`
  - `tests/unit/test_quest_journal_view.py`
  - `tests/unit/test_rumour_board.py`
  - `tests/unit/test_faction_influence.py`
  - `ROADMAP.md`
- **Tests:**
  - Focused multi-file pytest run including replay harness + e2e flow.
- **Done Evidence:**
  - Command run: `pytest tests/unit/test_replay_harness.py tests/unit/test_quest_journal_view.py tests/unit/test_rumour_board.py tests/unit/test_faction_influence.py tests/e2e/test_cli_flow.py`
  - Output summary: `26 passed`.
  - Determinism signal: `tests/unit/test_replay_harness.py` remains green in the combined V5 suite.

### 14.2 Exit Gates for Section 14
- [x] Quest journal empty-state guidance is app-owned and rendered by UI.
- [x] Faction standings empty-state guidance follows app contracts.
- [x] Focused regression + determinism spot check passes and is recorded.

### 14.3 Scope Notes
- Section 14 is a targeted consistency pass only; no new gameplay mechanics.
- Keep changes additive and architecture-safe through existing service/view contracts.

---

## 15) Progression Depth V6 — Leveling and Mid-loop Growth

### 15.1 Sequence

#### `V6-T01` XP-to-Level Progression Activation
- **Status:** `Done`
- **Objective:** Activate deterministic level progression so XP rewards from combat and quests can increase character level and survivability.
- **Acceptance Criteria:**
  - XP thresholds are centralized and reusable.
  - Combat and quest reward paths apply level progression.
  - Player-facing reward messaging includes level-up notification when thresholds are crossed.
  - Focused tests cover progression thresholds and reward-path behavior.
- **Files (expected):**
  - `src/rpg/application/services/balance_tables.py`
  - `src/rpg/application/services/game_service.py`
  - `tests/unit/test_balance_tables.py`
  - `tests/test_game_logic.py`
  - `tests/unit/test_quest_arc_flow.py`
- **Tests:**
  - Focused regression for balance + game logic + quest arc + e2e adjacency.
- **Done Evidence:**
  - Commit/patch refs: Added XP progression helpers (`xp_required_for_level`) and thresholds in `balance_tables`; implemented `_apply_level_progression` in `game_service` and wired it into combat (`apply_encounter_reward_intent`/`_resolve_combat`) and quest turn-in reward flow.
  - Messaging refs: Reward responses now include `Level up!` notifications when thresholds are crossed.
  - Test coverage refs: Extended `test_balance_tables.py`, `test_game_logic.py`, and `test_quest_arc_flow.py` with progression assertions.
  - Tests run + output summary: `pytest tests/unit/test_balance_tables.py tests/test_game_logic.py tests/unit/test_quest_arc_flow.py tests/e2e/test_cli_flow.py` → `16 passed`.

#### `V6-T02` Character Sheet Progression Visibility
- **Status:** `Done`
- **Objective:** Expose XP progress and next-level threshold clearly in the character view.
- **Acceptance Criteria:**
  - Character intent/view includes current XP and next threshold.
  - Character sheet rendering shows progress without duplicating rules.
  - Unit/CLI rendering tests cover the new view payload.
- **Files (actual):**
  - `src/rpg/application/dtos.py`
  - `src/rpg/application/services/game_service.py`
  - `src/rpg/presentation/game_loop.py`
  - `tests/test_game_logic.py`
  - `tests/e2e/test_cli_flow.py`
- **Tests:**
  - Unit assertion for progression payload in character sheet intent.
  - CLI rendering assertion for XP/next-level visibility.
- **Done Evidence:**
  - Commit/patch refs: Added `CharacterSheetView` DTO and `get_character_sheet_intent` in `game_service` with `xp`, `next_level_xp`, and `xp_to_next_level` values.
  - Presentation refs: Updated character menu in `game_loop` to use character-sheet intent and display level + XP progress in both Rich and plain rendering paths.
  - Test coverage refs: Added `test_get_character_sheet_intent_exposes_xp_progress` and `test_character_sheet_render_includes_xp_progress`.

#### `V6-T03` V6 Regression + Replay Determinism Audit
- **Status:** `Done`
- **Objective:** Validate progression changes against focused gameplay and replay determinism expectations.
- **Acceptance Criteria:**
  - Replay harness remains stable.
  - Focused progression/quest/combat/CLI suite passes.
  - Roadmap records command output evidence.
- **Tests:**
  - Focused multi-file pytest run including replay harness and CLI rendering path.
- **Done Evidence:**
  - Command run: `pytest tests/test_game_logic.py tests/e2e/test_cli_flow.py tests/unit/test_balance_tables.py tests/unit/test_quest_arc_flow.py tests/unit/test_replay_harness.py`
  - Output summary: `21 passed`.
  - Determinism signal: `tests/unit/test_replay_harness.py` remains green in the combined V6 suite.

### 15.2 Exit Gates for Section 15
- [x] XP-to-level progression is active in reward paths and tested.
- [x] Character view surfaces XP/next-level progress clearly.
- [x] Focused regression + replay determinism audit passes and is recorded.

### 15.3 Scope Notes
- Section 15 focuses on progression depth, not new combat subsystems.
- Keep implementation deterministic and within existing service contracts.

---

## 16) Equipment Lifecycle V7 — Manage, Remove, and Economic Turnover

### 16.1 Sequence

#### `V7-T01` Unequip and Drop Actions in Character Equipment Flow
- **Status:** `Done`
- **Objective:** Expand equipment lifecycle beyond equip-only by supporting deterministic unequip and item drop operations.
- **Acceptance Criteria:**
  - Equipment menu provides `Unequip` and `Drop` actions.
  - Unequipping clears the selected slot state.
  - Dropping removes item from inventory and unequips it when last equipped copy is removed.
  - Focused tests cover new service intents and flow behavior.
- **Files (actual):**
  - `src/rpg/application/services/game_service.py`
  - `src/rpg/presentation/game_loop.py`
  - `tests/unit/test_equipment_management.py`
- **Tests:**
  - Focused regression for equipment + gameplay adjacency + replay stability.
- **Done Evidence:**
  - Commit/patch refs: Added `unequip_slot_intent` and `drop_inventory_item_intent` to `game_service`.
  - Presentation refs: Updated Character → Equipment menu in `game_loop` to expose `Equip`, `Unequip`, and `Drop` actions.
  - Test coverage refs: Extended `test_equipment_management.py` with unequip/drop lifecycle assertions.
  - Tests run + output summary: `pytest tests/unit/test_equipment_management.py tests/test_game_logic.py tests/e2e/test_cli_flow.py tests/unit/test_replay_harness.py` → `25 passed`.

#### `V7-T02` Shop Sell-Back Flow
- **Status:** `Done`
- **Objective:** Add a deterministic inventory sell-back flow to convert carried items into gold.
- **Acceptance Criteria:**
  - Shop interaction supports choosing buy vs sell.
  - Sell operation removes item from inventory and adjusts gold using bounded sell values.
  - Equipped items cannot be sold without explicit unequip or are auto-unequipped with clear messaging.
  - Unit and CLI path tests cover sell behavior.
- **Files (actual):**
  - `src/rpg/application/dtos.py`
  - `src/rpg/application/services/game_service.py`
  - `src/rpg/presentation/game_loop.py`
  - `tests/unit/test_economy_identity_flow.py`
- **Tests:**
  - Unit coverage for sell payout and equipped-item auto-unequip behavior.
  - Focused regression with equipment + game loop + replay harness.
- **Done Evidence:**
  - Commit/patch refs: Added sell DTOs (`SellItemView`, `SellInventoryView`) and new intents (`get_sell_inventory_view_intent`, `sell_inventory_item_intent`) in `game_service` with bounded deterministic sell pricing.
  - Presentation refs: Updated town shop loop in `game_loop` to support mode selection (`Buy`/`Sell`) and sell result messaging.
  - Test coverage refs: Extended `test_economy_identity_flow.py` with sell lifecycle assertions.
  - Tests run + output summary: `pytest tests/unit/test_economy_identity_flow.py tests/unit/test_equipment_management.py tests/test_game_logic.py tests/e2e/test_cli_flow.py tests/unit/test_replay_harness.py` → `32 passed`.

#### `V7-T03` V7 Regression + Determinism Audit
- **Status:** `Done`
- **Objective:** Validate equipment lifecycle changes (equip/unequip/drop/sell) with replay-safe behavior.
- **Acceptance Criteria:**
  - Focused suite passes across equipment, game loop, and replay harness.
  - Determinism checks remain stable.
  - Roadmap captures command output evidence.
- **Done Evidence:**
  - Command run: `pytest tests/unit/test_economy_identity_flow.py tests/unit/test_equipment_management.py tests/test_game_logic.py tests/e2e/test_cli_flow.py tests/unit/test_replay_harness.py`
  - Output summary: `32 passed`.
  - Determinism signal: `tests/unit/test_replay_harness.py` remains green after equipment lifecycle changes.

### 16.2 Exit Gates for Section 16
- [x] Character equipment flow supports equip + unequip + drop with tests.
- [x] Shop sell-back lifecycle is implemented and tested.
- [x] Focused regression + determinism audit passes and is recorded.

### 16.3 Scope Notes
- Section 16 targets inventory/equipment lifecycle depth only.
- Keep economic math bounded and deterministic.

---

## 17) Travel Stakes V8 — Route Risk and On-the-Road Outcomes

### 17.1 Sequence

#### `V8-T01` Deterministic Travel Event Layer
- **Status:** `Done`
- **Objective:** Add deterministic on-the-road events to travel so movement has meaningful risk/reward beyond pure location toggle.
- **Acceptance Criteria:**
  - Travel applies deterministic event outcomes (clear route, delay pressure, cache gain, hazard).
  - Travel messaging includes event summary without removing destination context.
  - Event effects persist through character/world state and consequences history.
  - Unit tests verify deterministic replay for same seed/state.
- **Files (actual):**
  - `src/rpg/application/services/game_service.py`
  - `tests/unit/test_location_context_flow.py`
- **Tests:**
  - Focused travel + loop adjacency + replay suite.
- **Done Evidence:**
  - Commit/patch refs: Added `_apply_travel_event` and integrated it into `travel_intent` with deterministic seed policy (`travel.event`) and bounded effects (money/hp/threat/consequences).
  - State refs: Travel now records `last_travel_event` on character flags and appends travel consequence entries on world flags.
  - Test coverage refs: Extended `test_location_context_flow.py` with deterministic travel-event assertions.
  - Tests run + output summary: `pytest tests/unit/test_location_context_flow.py tests/test_game_logic.py tests/e2e/test_cli_flow.py tests/unit/test_replay_harness.py` → `22 passed`.

#### `V8-T02` Travel Preview Risk Hinting
- **Status:** `Done`
- **Objective:** Surface lightweight risk hints in destination preview cards so travel choices communicate stakes.
- **Acceptance Criteria:**
  - Destination preview includes deterministic risk band text.
  - Risk hint is computed in application intent, not presentation logic.
  - Unit tests verify deterministic hint stability.
- **Files (actual):**
  - `src/rpg/application/services/game_service.py`
  - `tests/unit/test_location_context_flow.py`
- **Tests:**
  - Unit assertions for risk hint presence and deterministic stability.
- **Done Evidence:**
  - Commit/patch refs: Added deterministic `_travel_risk_hint` in `game_service` and integrated risk-band text into destination `preview` payloads.
  - Contract refs: Risk hinting is produced exclusively in application intent (`get_travel_destinations_intent`), preserving presentation simplicity.
  - Test coverage refs: Extended `test_location_context_flow.py` with deterministic risk-hint assertions.

#### `V8-T03` V8 Regression + Determinism Audit
- **Status:** `Done`
- **Objective:** Validate travel-event integration against replay stability and core loop regressions.
- **Acceptance Criteria:**
  - Focused suite passes including replay harness.
  - No regressions in existing location/travel flows.
  - Roadmap records command output evidence.
- **Done Evidence:**
  - Command run: `pytest tests/unit/test_location_context_flow.py tests/test_game_logic.py tests/e2e/test_cli_flow.py tests/unit/test_replay_harness.py`
  - Output summary: `23 passed`.
  - Determinism signal: replay harness remains green while travel risk preview/event layers are active.

### 17.2 Exit Gates for Section 17
- [x] Travel path includes deterministic event outcomes and persistence.
- [x] Destination previews surface deterministic risk hints.
- [x] Focused regression + determinism audit passes and is recorded.

### 17.3 Scope Notes
- Section 17 focuses on travel depth only; no new combat loop additions.
- Keep all outcomes deterministic and bounded through existing service contracts.

---

## 18) Combat Utility V9 — Item Action Depth

### 18.1 Sequence

#### `V9-T01` Expand Combat `Use Item` Beyond Potion-only
- **Status:** `Done`
- **Objective:** Increase combat utility depth by supporting additional consumables through the existing `Use Item` action.
- **Acceptance Criteria:**
  - `Use Item` resolves more than `Healing Potion`.
  - Additional consumables are deterministic and bounded.
  - Existing combat deterministic replay behavior remains stable.
  - Unit test verifies at least one new consumable path.
- **Files (actual):**
  - `src/rpg/application/services/combat_service.py`
  - `tests/test_game_logic.py`
- **Tests:**
  - Focused combat + e2e + replay regression.
- **Done Evidence:**
  - Commit/patch refs: Added `_resolve_use_item` in `combat_service` and expanded item handling to support `Healing Herbs` and `Sturdy Rations` in addition to `Healing Potion`.
  - Test coverage refs: Added `test_combat_use_item_supports_healing_herbs` in `tests/test_game_logic.py`.
  - Tests run + output summary: `pytest tests/test_game_logic.py tests/e2e/test_cli_flow.py tests/unit/test_replay_harness.py` → `17 passed`.

#### `V9-T02` Combat Item Choice UX
- **Status:** `Done`
- **Objective:** Allow explicit item selection when multiple combat-usable items are present.
- **Acceptance Criteria:**
  - Combat action flow supports choosing a specific usable item.
  - Selection payload remains within existing action-intent contract boundaries.
  - Tests cover selection mapping and fallback behavior.
- **Files (actual):**
  - `src/rpg/application/services/game_service.py`
  - `src/rpg/application/services/combat_service.py`
  - `src/rpg/presentation/game_loop.py`
  - `tests/test_game_logic.py`
- **Tests:**
  - Unit coverage for action-intent mapping and selected-item priority.
- **Done Evidence:**
  - Commit/patch refs: Extended `submit_combat_action_intent` to carry item payload for `Use Item`, added `list_combat_item_options` in `game_service`, and updated `combat_service` to honor preferred item selection with deterministic fallback.
  - Presentation refs: Added `_choose_combat_item` in `game_loop` and wired explicit item selection into combat action submission.
  - Test coverage refs: Added `test_submit_combat_action_intent_maps_use_item_with_selected_item` and `test_combat_use_item_honors_selected_item_when_multiple_are_available` in `tests/test_game_logic.py`.

#### `V9-T03` V9 Regression + Determinism Audit
- **Status:** `Done`
- **Objective:** Validate combat item-depth changes across game logic, CLI flow, and replay determinism.
- **Acceptance Criteria:**
  - Focused suite passes.
  - Replay harness remains deterministic.
  - Roadmap records command output evidence.
- **Done Evidence:**
  - Command run: `pytest tests/test_game_logic.py tests/e2e/test_cli_flow.py tests/unit/test_replay_harness.py`
  - Output summary: `18 passed`.
  - Determinism signal: `tests/unit/test_replay_harness.py` remains green after combat item choice additions.

### 18.2 Exit Gates for Section 18
- [x] Combat `Use Item` supports additional bounded consumables.
- [x] Combat item choice flow supports explicit selection.
- [x] Focused regression + determinism audit passes and is recorded.

### 18.3 Scope Notes
- Section 18 targets combat item interaction depth only.
- Keep action handling deterministic and UI-safe through application contracts.

---

## 19) Quest Breadth V10 — Multi-Contract Variety

### 19.1 Sequence

#### `V10-T01` Add Deterministic Multi-Contract Quest Posting
- **Status:** `Done`
- **Objective:** Expand the quest board beyond a single contract while preserving deterministic turn-based posting behavior.
- **Acceptance Criteria:**
  - Quest posting seeds more than one contract.
  - Contract metadata remains application-owned and deterministic.
  - Existing `first_hunt` flow remains backward-compatible.
- **Files (actual):**
  - `src/rpg/application/services/quest_service.py`
  - `src/rpg/application/services/game_service.py`
- **Done Evidence:**
  - Commit/patch refs: Added deterministic quest templates in `quest_service` (`first_hunt`, `trail_patrol`, `supply_drop`) and expanded `_QUEST_TITLES` in `game_service`.
  - Contract refs: Quest template metadata now includes objective kind (`kill_any`, `travel_count`) and bounded rewards/targets.

#### `V10-T02` Generalize Quest Progression Paths
- **Status:** `Done`
- **Objective:** Ensure quest progression logic supports contract-specific progression paths instead of first-hunt-only behavior.
- **Acceptance Criteria:**
  - Monster kills progress active kill contracts deterministically.
  - Tick advancement progresses active travel-count contracts deterministically.
  - Non-combat social quest assist path no longer hardcodes `first_hunt`.
- **Files (actual):**
  - `src/rpg/application/services/quest_service.py`
  - `src/rpg/application/services/game_service.py`
- **Done Evidence:**
  - Commit/patch refs: Refactored quest expiry/progression loops in `quest_service` and generalized Silas non-combat progression in `game_service` to active `kill_any` contracts.

#### `V10-T03` Quest Breadth Regression + Determinism Audit
- **Status:** `Done`
- **Objective:** Validate expanded quest contract behavior across unit, journal/arc, CLI, and replay determinism tests.
- **Acceptance Criteria:**
  - Focused suite passes.
  - Replay harness remains green.
  - Roadmap records command output evidence.
- **Files (actual):**
  - `tests/unit/test_quest_service.py`
  - `tests/unit/test_quest_arc_flow.py`
  - `tests/unit/test_quest_journal_view.py`
  - `tests/e2e/test_cli_flow.py`
  - `tests/unit/test_replay_harness.py`
- **Done Evidence:**
  - Test coverage refs: Added `test_tick_posts_multiple_quest_contracts` and `test_active_travel_contract_progresses_on_ticks` in `tests/unit/test_quest_service.py`.
  - Command run: `pytest tests/unit/test_quest_service.py tests/unit/test_quest_arc_flow.py tests/unit/test_quest_journal_view.py tests/e2e/test_cli_flow.py tests/unit/test_replay_harness.py`
  - Output summary: `13 passed`.

### 19.2 Exit Gates for Section 19
- [x] Quest board contains multiple deterministic contracts.
- [x] Quest progression supports multiple objective kinds.
- [x] Focused regression + determinism audit passes and is recorded.

### 19.3 Scope Notes
- Section 19 focuses on quest breadth/content depth only.
- Keep all quest logic deterministic and application-contract centered.

---

## 20) Quest Clarity V11 — Objective + Urgency Surface

### 20.1 Sequence

#### `V11-T01` Extend Quest View Contract with Objective + Urgency
- **Status:** `Done`
- **Objective:** Improve quest readability so board/journal entries communicate contract intent and time pressure clearly.
- **Acceptance Criteria:**
  - Quest view includes a deterministic objective summary.
  - Active quests expose deterministic urgency labels from expiry windows.
  - Non-active quests avoid misleading urgency labels.
- **Files (actual):**
  - `src/rpg/application/dtos.py`
  - `src/rpg/application/services/game_service.py`
- **Done Evidence:**
  - Commit/patch refs: Added `objective_summary` and `urgency_label` to `QuestStateView` and populated both in `get_quest_board_intent`.
  - Logic refs: Introduced `_quest_objective_summary` and `_quest_urgency_label` helpers to keep formatting deterministic and app-owned.

#### `V11-T02` Render Objective + Urgency in Quest UI Flows
- **Status:** `Done`
- **Objective:** Surface new contract fields in quest board and quest journal without changing interaction controls.
- **Acceptance Criteria:**
  - Quest board options include objective text and urgency where relevant.
  - Quest journal displays objective and urgency columns/lines.
  - Existing quest selection/turn-in flow remains unchanged.
- **Files (actual):**
  - `src/rpg/presentation/game_loop.py`
- **Done Evidence:**
  - Commit/patch refs: Updated `_run_quest_board` and `_render_quest_journal` to show `objective_summary` and `urgency_label` while preserving acceptance/turn-in behavior.

#### `V11-T03` Quest Clarity Regression + Determinism Audit
- **Status:** `Done`
- **Objective:** Validate quest readability contract changes against flow and replay stability.
- **Acceptance Criteria:**
  - Focused quest/journal/CLI/replay suite passes.
  - New tests verify objective summary and urgency labels.
  - Roadmap records command output evidence.
- **Files (actual):**
  - `tests/unit/test_quest_journal_view.py`
  - `tests/unit/test_quest_service.py`
  - `tests/unit/test_quest_arc_flow.py`
  - `tests/e2e/test_cli_flow.py`
  - `tests/unit/test_replay_harness.py`
- **Done Evidence:**
  - Test coverage refs: Added `test_quest_board_includes_objective_summary_and_urgency_for_active_contract` and `test_quest_board_renders_travel_objective_summary_for_supply_drop` in `tests/unit/test_quest_journal_view.py`.
  - Command run: `pytest tests/unit/test_quest_journal_view.py tests/unit/test_quest_service.py tests/unit/test_quest_arc_flow.py tests/e2e/test_cli_flow.py tests/unit/test_replay_harness.py`
  - Output summary: `15 passed`.

### 20.2 Exit Gates for Section 20
- [x] Quest entries expose objective clarity through app contracts.
- [x] Active quests expose deterministic urgency labels.
- [x] Focused regression + determinism audit passes and is recorded.

### 20.3 Scope Notes
- Section 20 targets quest readability only.
- Keep objective/urgency generation deterministic and centralized in application service intents.

---

## 21) Roadmap Finalization

### Final Status
`Done`

### Completion Summary
- All phases in this roadmap are complete and closed with task-level done evidence.
- No open `Not Started`, `In Progress`, or `Blocked` tasks remain.
- Exit gates for the latest section are satisfied and recorded.

### Implementation Freeze (Anti-Overcoding)
- Do not add new abstractions or feature paths unless a new roadmap section is explicitly opened.
- Restrict future changes to bug fixes, maintenance, or user-approved scope additions.
- Any new feature idea should be captured as backlog input before code changes.

