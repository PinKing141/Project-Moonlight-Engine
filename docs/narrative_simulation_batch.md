# Narrative Simulation Batch Validation (NS-T06)

## Batch Definition
- Date: 2026-02-25
- Fixed seeds: `101`, `202`, `303`
- Fixed script (16 actions):
  1. rest
  2. rumour
  3. travel
  4. rest
  5. social (broker_silas, Friendly)
  6. travel
  7. rest
  8. rumour
  9. explore
  10. social (broker_silas, Friendly)
  11. rest
  12. travel
  13. rest
  14. travel
  15. rumour
  16. rest

## Arc Summaries

| Seed | Final Turn | Threat | Tension | Injections | Injection Kinds | Story Seeds (Total / Resolved / Active) | Major Events | Semantic Arc (Score / Band) | Quality Status | Quality Alerts | Rumour Signature |
| --- | ---: | ---: | ---: | ---: | --- | --- | ---: | --- | --- | --- | --- |
| 101 | 11 | 7 | 56 | 2 | story_seed, story_seed | 2 / 1 / 1 | 1 | 50 / stable | warn | semantic_below_target | memory:3:merchant-under-pressure, black_fletch, bridge_toll, crypt_lights |
| 202 | 11 | 9 | 66 | 4 | faction_flashpoint, story_seed, faction_flashpoint, story_seed | 2 / 1 / 1 | 1 | 63 / stable | pass | none | seed:seed_7_2399, memory:6:faction-flashpoint, flashpoint:6:social, bridge_toll |
| 303 | 11 | 8 | 64 | 5 | story_seed, faction_flashpoint, story_seed, faction_flashpoint, story_seed | 3 / 2 / 1 | 2 | 86 / strong | pass | none | seed:seed_7_6989, memory:6:faction-flashpoint, flashpoint:6:social, crypt_lights |

## Calibrated Targets
- `semantic_arc_score >= 55`
- `45 <= tension_level <= 75`
- `story_seed_active <= 1`
- `major_event_count >= 1`

## Quality Status Rules
- `pass`: no threshold alerts.
- `warn`: one or more alerts, but not both `semantic_below_target` and `low_event_density` together.
- `fail`: both `semantic_below_target` and `low_event_density` are present.

## Batch-Level Gate Targets
- `pass_rate >= 0.66`
- `warn_count <= 1`
- `fail_count <= 0`

## Batch-Level Gate Result (Fixed Seeds)
- `total = 3`
- `pass_count = 2`
- `warn_count = 1`
- `fail_count = 0`
- `pass_rate = 0.6667`
- `blockers = none`
- `release_verdict = go`

## Profile Presets
- `strict`: `pass_rate >= 0.80`, `warn_count <= 0`, `fail_count <= 0`
- `balanced`: `pass_rate >= 0.66`, `warn_count <= 1`, `fail_count <= 0`
- `exploratory`: `pass_rate >= 0.50`, `warn_count <= 2`, `fail_count <= 1`

## Profile Verdicts (Fixed Seeds)
- `strict`: `hold` (`blockers = pass_rate_below_target, too_many_warnings`)
- `balanced`: `go` (`blockers = none`)
- `exploratory`: `go` (`blockers = none`)

## Configuration Overrides
- Default profile selector:
  - `RPG_NARRATIVE_GATE_DEFAULT_PROFILE` (e.g., `strict`, `balanced`, `exploratory`)
- Optional JSON profile file:
  - `RPG_NARRATIVE_GATE_PROFILE_FILE`
  - Expected shape:
    - `{ "profiles": { "strict": { "min_pass_rate": 0.8, "max_warn_count": 0, "max_fail_count": 0 }, ... } }`
    - or direct map `{ "strict": { ... }, "balanced": { ... } }`
- Per-profile environment overrides:
  - `RPG_NARRATIVE_GATE_STRICT_MIN_PASS_RATE`
  - `RPG_NARRATIVE_GATE_STRICT_MAX_WARN_COUNT`
  - `RPG_NARRATIVE_GATE_STRICT_MAX_FAIL_COUNT`
  - Same pattern supported for `BALANCED` and `EXPLORATORY`.
- Alert target environment overrides:
  - `RPG_NARRATIVE_GATE_TARGET_SEMANTIC_MIN`
  - `RPG_NARRATIVE_GATE_TARGET_TENSION_MIN`
  - `RPG_NARRATIVE_GATE_TARGET_TENSION_MAX`
  - `RPG_NARRATIVE_GATE_TARGET_MAX_ACTIVE_SEEDS`
  - `RPG_NARRATIVE_GATE_TARGET_MIN_MAJOR_EVENTS`
- Resolution source:
  - Runtime command and simulation harness now use the same shared config resolver in `rpg.application.services.narrative_quality_batch`.

## Runtime Report Artifact Command
- Command:
  - `python -m rpg.infrastructure.narrative_quality_report`
- Optional arguments:
  - `--seeds 101,202,303`
  - `--script rest,rumour,travel,...`
  - `--script-name baseline|exploration_heavy`
  - `--profile strict|balanced|exploratory`
  - `--output artifacts/narrative_quality_report.json`
  - `--print-json`
  - `--compare-base path/to/base.json`
  - `--compare-candidate path/to/candidate.json`
- Artifact contract:
  - Writes deterministic JSON containing `schema`, `seeds`, `script`, per-seed `summaries`, `quality_targets`, selected `profile`, `profile_thresholds`, and `aggregate_gate` verdict fields.

## Named Script Presets
- `baseline`:
  - Canonical 16-step balanced script used by existing fixed-seed validation runs.
- `exploration_heavy`:
  - Explore-biased 16-step script with increased `explore` action density for stress-testing encounter-facing narrative pressure.
- Selection rules:
  - Use either `--script` or `--script-name`.
  - Unknown `--script-name` values fail fast with a clear error listing supported preset names.

## Report Comparison Utility
- Compare mode command:
  - `python -m rpg.infrastructure.narrative_quality_report --compare-base artifacts/base.json --compare-candidate artifacts/candidate.json`
- Compare output includes deterministic deltas for:
  - aggregate gate verdict change (`base` vs `candidate`)
  - pass-rate (`base`, `candidate`, `delta`)
  - blockers (`added`, `removed`)
  - semantic arc band counts (`weak`, `fragile`, `stable`, `strong`) and per-band deltas.
- Compatibility behavior:
  - Both artifacts must pass schema validation; incompatible schema/version artifacts are rejected with clear diagnostics.

## Operational Release Policy
- Operational runbook reference:
  - `docs/contributor_runbook.md` section `Narrative Quality Ops (Release Gate)`
- Policy summary:
  - `release_verdict = go` allows promotion when other CI checks are green.
  - `release_verdict = hold` blocks release unless blockers are resolved or a documented waiver is approved.
  - Waivers require maintainer + narrative/system reviewer approval and must record artifact paths, blockers, reason, and mitigation.

## Report Schema Contract
- Current schema object:
  - `schema.name = narrative_quality_report`
  - `schema.version = 1.0`
- Compatibility behavior:
  - Runtime loader/validator rejects unsupported schema names or versions with explicit `ValueError` diagnostics.
  - Artifact writes validate required top-level keys and schema compatibility before persisting.

## Session-End Artifact Hook (CLI)
- Opt-in environment controls:
  - `RPG_NARRATIVE_SESSION_REPORT_ENABLED` (`1/true/yes/on` to enable; default disabled)
  - `RPG_NARRATIVE_SESSION_REPORT_OUTPUT` (default `artifacts/narrative_quality_session_report.json`)
  - `RPG_NARRATIVE_SESSION_REPORT_PROFILE` (optional gate profile override)
  - `RPG_NARRATIVE_SESSION_REPORT_SEED_COUNT` (default `3`)
- Behavior:
  - On `Quit` from the main menu, when enabled, the CLI emits a deterministic session-end artifact using world/session context-derived seeds.
  - Default behavior remains a no-op (no artifact emission) when disabled.

## Determinism Check
- Re-ran the same batch (`111`, `222`, `333`) twice with the same script.
- Arc summaries matched exactly across both runs.
- Determinism source: centralized seed policy (`derive_seed`) plus fixed script and bounded narrative state, including deterministic semantic arc scoring.

## Observed Arc Patterns
- Higher-turn tension settled in the `56–64` range for this script and baseline threat.
- Story outcomes diverged across seeds (different injection counts/kinds and rumour signatures) while remaining deterministic per seed.
- Memory echoes (`memory:*`) and flashpoint echoes (`flashpoint:*`) surfaced when seeds reached resolved paths and wrote narrative memory/aftershock state.
- Semantic arc scores separated runs by coherence intensity (`stable` vs `strong`) using deterministic weighted signals (resolution count, major events, category diversity, tension window, unresolved pressure).
- Threshold alerts now provide deterministic guardrails: in this batch, seed `101` emitted a `warn` due to `semantic_below_target` while the other seeds passed.
- Aggregate gate rules produce a deterministic release-readiness verdict (`go` for this fixed batch) from pass-rate and warn/fail caps.
- Profile presets provide deterministic policy variance over the same batch (`strict` holds while `balanced`/`exploratory` go).

## Observed Failure Modes / Gaps
- Some seeds can finish with active unresolved seeds and zero major events (e.g., seed `202`), reducing narrative echo density.
- Thresholding and alerts are now calibrated, but target/weight values remain heuristic and should be tuned against playtest-driven quality expectations.
- Runtime report command, session-end artifact hook, schema compatibility guard, shared config resolution, named script presets, report comparison utility, and operational release policy are all documented.
