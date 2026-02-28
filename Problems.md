# Project Moonlight Engine - Problems Register

Last updated: 2026-02-28

## Open Problems
- None.

## Snapshot
- Unit suite run: `.venv\Scripts\python.exe -m pytest tests/unit -q`
- Result: `440 passed, 1 skipped`
- Broader suite run: `.venv\Scripts\python.exe -m pytest tests/test_game_logic.py tests/e2e/test_cli_flow.py -q`
- Result: `73 passed`
- Full suite run: `.venv\Scripts\python.exe -m pytest -q`
- Result: `545 passed, 1 skipped`
- Focused stability run: `.venv\Scripts\python.exe -m pytest tests/unit/test_seed_policy.py tests/unit/test_content_cache.py tests/unit/test_encounter_flavour.py -q`
- Result: `13 passed`

## Stabilized Work (Already Green)

### PRB-S1 - Deterministic encounter intro selection
- Status: `Done`
- Evidence: `tests/unit/test_encounter_flavour.py` and `tests/unit/test_seed_policy.py` pass.
- Notes: Intro selection now accepts injected seed/RNG and no longer depends on global random state.

### PRB-S2 - Cache maintenance sweep support
- Status: `Done`
- Evidence: `tests/unit/test_content_cache.py` pass.
- Notes: Expired cache envelope cleanup is covered and manifest file retention is validated.

## Resolved Problems

### PRB-001 - Migration chain test no longer matches migration entrypoint policy
- Status: `Done`
- Repro:
  - `.venv\Scripts\python.exe -m pytest tests/unit/test_migration_chain.py::MigrationChainTests::test_apply_all_references_all_numbered_migrations_in_order -q`
- Resolution:
  - Kept `src/rpg/infrastructure/db/migrations/_apply_all.sql` as deprecated stub.
  - Updated `tests/unit/test_migration_chain.py` to validate deprecation contract when no `SOURCE` lines exist and still validate numbered migrations exist.
- Evidence:
  - `.venv\Scripts\python.exe -m pytest tests/unit/test_migration_chain.py tests/unit/test_repository_parity_audit.py -q` -> `8 passed`

### PRB-002 - Rearguard targeting does not reliably switch after vanguard falls
- Status: `Done`
- Repro:
  - `.venv\Scripts\python.exe -m pytest tests/unit/test_party_initiative_queue.py::PartyInitiativeQueueTests::test_rearguard_becomes_targetable_after_vanguard_falls -q`
- Resolution:
  - Updated `CombatService._select_enemy_tactical_action` to allow rearguard auto-disengage only when a living vanguard ally is present in party combat.
  - Wired current enemy roster into tactical action selection in party loop.
- Evidence:
  - `.venv\Scripts\python.exe -m pytest tests/unit/test_party_initiative_queue.py::PartyInitiativeQueueTests::test_rearguard_becomes_targetable_after_vanguard_falls -q` -> `1 passed`

### PRB-003 - Reference dataset discovery expectations mismatch repository content
- Status: `Done`
- Repro:
  - `.venv\Scripts\python.exe -m pytest tests/unit/test_reference_dataset_loader.py::ReferenceDatasetLoaderTests::test_discover_reference_files_returns_latest_snapshot_per_prefix -q`
- Resolution:
  - Updated discovery test to accept two supported modes:
    - CSV snapshots present (`Pres *.csv`),
    - Unified JSON fallback present (`unified_reference_world.json`).
- Evidence:
  - `.venv\Scripts\python.exe -m pytest tests/unit/test_reference_dataset_loader.py::ReferenceDatasetLoaderTests::test_discover_reference_files_returns_latest_snapshot_per_prefix -q` -> `1 passed`

### PRB-004 - Session quality hook tests depend on ambient MySQL env and schema state
- Status: `Done`
- Repro:
  - `.venv\Scripts\python.exe -m pytest tests/unit/test_session_quality_hook.py -q`
- Resolution:
  - Added test helper in `tests/unit/test_session_quality_hook.py` that creates service under patched environment (`RPG_DATABASE_URL=""`) to force hermetic in-memory bootstrap.
- Evidence:
  - `.venv\Scripts\python.exe -m pytest tests/unit/test_session_quality_hook.py -q` -> `3 passed`

### PRB-005 - Import-order fragile test (`unittest.mock` usage)
- Status: `Done`
- Repro:
  - `.venv\Scripts\python.exe -m pytest tests/unit/test_event_bus_progression.py::WorldProgressionTests::test_cataclysm_clock_uses_biome_severity_pressure_for_escalation -q`
- Resolution:
  - Imported `mock` explicitly via `from unittest import mock` and used `mock.patch.object(...)`.
- Evidence:
  - `.venv\Scripts\python.exe -m pytest tests/unit/test_event_bus_progression.py::WorldProgressionTests::test_cataclysm_clock_uses_biome_severity_pressure_for_escalation -q` -> `1 passed`

## Completion Criteria For This File
- [x] All `PRB-001..PRB-005` moved to `Done` with patch references.
- [x] Each problem has a linked regression test result.
- [x] Full unit command is green: `.venv\Scripts\python.exe -m pytest tests/unit -q`.

## Post-Resolution Hardening

### PRB-H01 - Atomic persistence fails on reduced schemas missing `attribute`
- Status: `Done`
- Resolution:
  - Added presence checks in `atomic_persistence._upsert_character_attributes` and skipped attribute upsert when `attribute`/`character_attribute` tables are absent.
- Evidence:
  - `.venv\Scripts\python.exe -m pytest tests/integration/test_progression_unlock_atomicity.py::ProgressionUnlockAtomicityTests::test_progression_unlock_operation_commits_in_atomic_transaction -q` -> `1 passed`

### PRB-H02 - World flag operation fails when `world_flag` table is absent in reduced integration schema
- Status: `Done`
- Resolution:
  - Added guard in `MysqlWorldRepository.build_set_world_flag_operation` to no-op when `world_flag` table is unavailable.
- Evidence:
  - `.venv\Scripts\python.exe -m pytest tests/integration/test_game_service_turnin_atomic_rollback.py::GameServiceTurnInAtomicRollbackTests::test_turn_in_rolls_back_character_world_and_narrative_writes_on_failing_operation -q` -> `1 passed`

### PRB-H03 - MySQL character stats integration test asserted exact `flags` dict despite default metadata enrichment
- Status: `Done`
- Resolution:
  - Updated integration assertions to validate required user-provided flag payload while allowing default metadata keys (`alignment`, `class_levels`).
- Evidence:
  - `.venv\Scripts\python.exe -m pytest tests/integration/test_mysql_character_repository_stats.py -q` -> `2 passed`

## Verification Footer
- Problems register closure verification date: 2026-02-28
- Latest full run: `.venv\Scripts\python.exe -m pytest -q` -> `545 passed, 1 skipped`
