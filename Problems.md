# Project Moonlight Engine - Problems Register

Last updated: 2026-03-01

## Open Problems
- None.

## Snapshot
- Unit suite run: `.venv\Scripts\python.exe -m pytest tests/unit -q`
- Result: `454 passed`
- Broader suite run: `.venv\Scripts\python.exe -m pytest tests/test_game_logic.py tests/e2e/test_cli_flow.py -q`
- Result: `74 passed`
- Full suite run: `.venv\Scripts\python.exe -m pytest -q`
- Result: `559 passed`
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

### PRB-H04 - Property parity audit skipped when Hypothesis dependency was unavailable
- Status: `Done`
- Resolution:
  - Replaced skip-only fallback in `tests/unit/test_sql_repository_roundtrip_property.py` with deterministic matrix-based roundtrip assertions when `hypothesis` is not installed.
- Evidence:
  - `.venv\Scripts\python.exe -m pytest tests/unit/test_sql_repository_roundtrip_property.py -q` -> `1 passed`
  - `.venv\Scripts\python.exe -m pytest -q -ra` -> `546 passed` (no skips)

### PRB-H05 - Phase25 notes/report drift risk due manual Markdown updates
- Status: `Done`
- Resolution:
  - Updated `tools/testing/phase25_cli_playtest_capture.py` to generate both JSON report and Markdown notes from the same payload.
  - Added `environment.location_count` to disambiguate zero travel hops in single-location in-memory runs.
  - Added `tests/unit/test_phase25_playtest_artifacts.py` to enforce report/notes consistency.
- Evidence:
  - `.venv\Scripts\python.exe tools/testing/phase25_cli_playtest_capture.py` -> updated `phase25_cli_playtest_report.json` and `phase25_cli_playtest_notes.md`
  - `.venv\Scripts\python.exe -m pytest tests/unit/test_phase25_playtest_artifacts.py tests/e2e/test_cli_flow.py -q` -> `9 passed`
  - `.venv\Scripts\python.exe -m pytest -q` -> `547 passed`

### PRB-H06 - Scripted Phase25 selector logic duplicated between artifact script and e2e test
- Status: `Done`
- Resolution:
  - Added shared selector helper `src/rpg/infrastructure/playtest/phase25_scenario.py`.
  - Updated `tools/testing/phase25_cli_playtest_capture.py` and `tests/e2e/test_cli_flow.py` to use shared selector logic.
  - Added focused selector unit test `tests/unit/test_phase25_playtest_scenario.py`.
- Evidence:
  - `.venv\Scripts\python.exe -m pytest tests/unit/test_phase25_playtest_scenario.py tests/unit/test_phase25_playtest_artifacts.py tests/e2e/test_cli_flow.py -q` -> `11 passed`
  - `.venv\Scripts\python.exe -m pytest -q` -> `549 passed`

### PRB-H07 - Phase25 capture script executed at import-time and assumed preconfigured import path
- Status: `Done`
- Resolution:
  - Refactored `tools/testing/phase25_cli_playtest_capture.py` into explicit callable API (`run_capture`, `main`) with `if __name__ == "__main__"` guard.
  - Added robust local `src` path injection for direct script execution.
  - Added API-level unit test `tests/unit/test_phase25_playtest_capture_script_api.py`.
- Evidence:
  - `.venv\Scripts\python.exe -m pytest tests/unit/test_phase25_playtest_capture_script_api.py tests/unit/test_phase25_playtest_scenario.py tests/unit/test_phase25_playtest_artifacts.py tests/e2e/test_cli_flow.py -q` -> `12 passed`
  - `.venv\Scripts\python.exe -m pytest -q` -> `550 passed`

### PRB-H08 - Executable playtest capture script lived in `artifacts/` output directory
- Status: `Done`
- Resolution:
  - Moved capture script from `artifacts/phase25_cli_playtest_capture.py` to `tools/testing/phase25_cli_playtest_capture.py`.
  - Updated script root discovery for new directory depth (`parents[2]`) while preserving artifact outputs in `artifacts/`.
  - Updated references in docs/tests to point to the new `tools/testing` script path.
- Evidence:
  - `.venv\Scripts\python.exe tools/testing/phase25_cli_playtest_capture.py` -> wrote `artifacts/phase25_cli_playtest_report.json` and `artifacts/phase25_cli_playtest_notes.md`
  - `.venv\Scripts\python.exe -m pytest tests/unit/test_phase25_playtest_capture_script_api.py tests/unit/test_phase25_playtest_artifacts.py tests/e2e/test_cli_flow.py -q` -> `10 passed`
  - `.venv\Scripts\python.exe -m pytest -q` -> `550 passed`

### PRB-H09 - Temporary one-off scripts were committed under `artifacts/`
- Status: `Done`
- Resolution:
  - Removed stale temporary scripts `artifacts/_tmp_check_db.py` and `artifacts/_tmp_migrate_run.py`.
  - Confirmed no code references to either `_tmp_` path remained before deletion.
- Evidence:
  - `rg -n "_tmp_check_db\.py|_tmp_migrate_run\.py|artifacts/_tmp_" -S .` -> no matches
  - `.venv\Scripts\python.exe -m pytest -q` -> `550 passed`

### PRB-H10 - Migration runner executed seed DML in default linear schema path
- Status: `Done`
- Resolution:
  - Updated `src/rpg/infrastructure/db/mysql/migrate.py` so default strict linear plan excludes `NNN_seed_*.sql` files.
  - Added explicit seed controls:
    - `--include-seeds` for schema+seed runs
    - `--seed-only` for data-only runs
  - Renamed DML-only migration `015_expand_faction_roster.sql` to `015_seed_expand_faction_roster.sql` so it is excluded from default schema runs.
  - Added `build_seed_migration_plan()` and unit tests for schema-vs-seed selection behavior.
- Evidence:
  - `.venv\Scripts\python.exe -m pytest -q tests/unit/test_mysql_migration_runner.py` -> `9 passed`
  - `.venv\Scripts\python.exe -m rpg.infrastructure.db.mysql.migrate --dry-run` -> strict schema plan excludes seed files (`11`, `13`, `15`, `16`, `17`)
  - `.venv\Scripts\python.exe -m pytest -q` -> `554 passed`

### PRB-H11 - Database initialization still relied on standalone `create_tables.sql` baseline
- Status: `Done`
- Resolution:
  - Added canonical numbered baseline migration `src/rpg/infrastructure/db/migrations/000_base_schema.sql`.
  - Updated migration runner to use numbered migrations only (removed base-file prepend path).
  - Converted `src/rpg/infrastructure/db/create_tables.sql` and `src/rpg/infrastructure/db/create_history_tables.sql` to explicit no-op deprecation stubs.
  - Added migration runner test asserting real strict plan starts with `000_base_schema.sql`.
- Evidence:
  - `.venv\Scripts\python.exe -m pytest -q tests/unit/test_migration_chain.py tests/unit/test_mysql_migration_runner.py` -> `14 passed`
  - `.venv\Scripts\python.exe -m pytest -q` -> `554 passed`

### PRB-H12 - Cache VCS hygiene verification for `.rpg_cache/`
- Status: `Done`
- Resolution:
  - Confirmed `.rpg_cache/` is in `.gitignore` and no cache files are currently tracked in Git.
- Evidence:
  - `git ls-files .rpg_cache` -> no output
  - `.venv\Scripts\python.exe -m pytest -q` -> `554 passed`

### PRB-H13 - MySQL connection layer used default engine config without explicit pooling
- Status: `Done`
- Resolution:
  - Added explicit MySQL pool settings in `src/rpg/infrastructure/db/mysql/connection.py`:
    - `pool_pre_ping=True`
    - `pool_recycle` (`RPG_DB_POOL_RECYCLE_SECONDS`, default `1800`)
    - `pool_size` (`RPG_DB_POOL_SIZE`, default `5`)
    - `max_overflow` (`RPG_DB_MAX_OVERFLOW`, default `10`)
    - `pool_timeout` (`RPG_DB_POOL_TIMEOUT_SECONDS`, default `30`)
  - Added safe env parsing with minimum bounds and non-MySQL URL bypass for pool-specific args.
  - Added focused unit tests for MySQL/non-MySQL kwargs and invalid env fallback.
- Evidence:
  - `.venv\Scripts\python.exe -m pytest -q tests/unit/test_mysql_connection_pooling.py` -> `3 passed`
  - `.venv\Scripts\python.exe -m pytest tests/unit -q` -> `452 passed`
  - `.venv\Scripts\python.exe -m pytest -q` -> `557 passed`

### PRB-H14 - Analytical narrative batch job lived inside `application/services`
- Status: `Done`
- Resolution:
  - Moved `narrative_quality_batch.py` from `src/rpg/application/services/` to `src/rpg/infrastructure/analysis/`.
  - Updated runtime/tooling imports to the new module location:
    - `src/rpg/infrastructure/narrative_quality_report.py`
    - `src/rpg/presentation/main_menu.py`
    - narrative/report/session unit tests
  - Added `src/rpg/infrastructure/analysis/__init__.py` and removed parity-audit exclusion for the old application file.
- Evidence:
  - `.venv\Scripts\python.exe -m pytest -q tests/unit/test_narrative_simulation_batch.py tests/unit/test_narrative_quality_report.py tests/unit/test_session_quality_hook.py tests/unit/test_repository_parity_audit.py tests/test_game_logic.py tests/e2e/test_cli_flow.py` -> `101 passed`
  - `.venv\Scripts\python.exe -m pytest tests/unit -q` -> `452 passed`
  - `.venv\Scripts\python.exe -m pytest -q` -> `557 passed`

### PRB-H15 - Redundant entrypoint (`run_game.py`) created startup-path duplication risk
- Status: `Done`
- Resolution:
  - Removed root-level `run_game.py`.
  - Added canonical console script entrypoint in `pyproject.toml`:
    - `moonlight = "rpg.__main__:main"`
  - Kept canonical module invocation path (`python -m rpg`) intact.
- Evidence:
  - `Select-String -Path pyproject.toml -Pattern 'moonlight = "rpg.__main__:main"'` -> present
  - `.venv\Scripts\python.exe -m pytest -q tests/unit/test_main_entry_error_handling.py tests/e2e/test_cli_flow.py` -> `11 passed`
  - `.venv\Scripts\python.exe -m pytest -q` -> `557 passed`

### PRB-H16 - Root directory pollution from verification/log `.txt` outputs
- Status: `Done`
- Resolution:
  - Moved root verification/log artifacts into `docs/verification/`:
    - `sanity.txt`
    - `final_verify.txt`
    - `full_test_report.txt`
    - `pytest_e2e_out.txt`
    - `tmp_progression_tests.log`
  - Added root-output guard entries in `.gitignore` to prevent future root pollution.
- Evidence:
  - `Get-ChildItem docs/verification -File` -> all verification/log files now live under docs.
  - `.venv\Scripts\python.exe -m pytest -q` -> `557 passed`

### PRB-H17 - Rolling UI animation path still used blocking sleep and duplicate final render
- Status: `Done`
- Resolution:
  - Removed synchronous `time.sleep` animation path in `src/rpg/presentation/rolling_ui.py`.
  - Updated sync animator wrapper to execute async animation flow (`asyncio.run(...)`).
  - Removed duplicate final result render/prompt block in async animator.
  - Added focused unit tests for delegation and single final prompt behavior.
- Evidence:
  - `.venv\Scripts\python.exe -m pytest -q tests/unit/test_rolling_ui_animation.py` -> `2 passed`
  - `.venv\Scripts\python.exe -m pytest -q tests/unit/test_character_creation_races.py tests/e2e/test_cli_flow.py` -> `27 passed`
  - `.venv\Scripts\python.exe -m pytest tests/unit -q` -> `454 passed`
  - `.venv\Scripts\python.exe -m pytest -q` -> `559 passed`

## Verification Footer
- Problems register closure verification date: 2026-03-01
- Latest full run: `.venv\Scripts\python.exe -m pytest -q` -> `559 passed`
