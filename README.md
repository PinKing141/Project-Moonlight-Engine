# Text RPG Skeleton

Minimal deterministic, turn-based RPG scaffold following layered architecture:

- `presentation`: CLI only, depends on application layer
- `application`: services, DTOs, event bus, progression
- `domain`: pure models, events, repository interfaces
- `infrastructure`: concrete adapters (in-memory repos, D&D 5e + Open5e content providers)

Current runtime contract:

- Canonical entrypoint is the arrow-key CLI via `python -m rpg`.
- Presentation should call `GameService` facade/view-model methods rather than reaching repositories directly.
- This keeps the game logic UI-agnostic so a future GUI/web client can be added without changing core rules.

Deterministic seed contract:

- Seed derivation is centralized in `src/rpg/application/services/seed_policy.py` via `derive_seed(namespace, context)`.
- Encounter generation (`encounter.plan`) and combat resolution (`combat.resolve`) must derive seeds only through this policy.
- Context maps are normalized before hashing to keep seed outcomes stable and reproducible.

Content provider runtime contract (solo mode):

- Runtime is local-first for content reads used by gameplay setup flows (e.g., race options).
- Runtime is now offline-first by default (local SRD only, no live HTTP required).
- Remote runtime fallback (`dnd5eapi.co` then Open5e) is opt-in.
- Responses are cached on disk for offline continuity, with stale-cache fallback if both providers fail.
- `CharacterCreationService` still safely falls back to built-in default races if provider calls are unavailable.
- Runtime and import flows now use separate provider strategies:
        - Runtime default order: Local SRD JSON.
        - Runtime opt-in remote order: Local SRD JSON → D&D5e API → Open5e.
        - Import default order: D&D5e API → Open5e → Local SRD JSON.

Cache invalidation contract:

- Content cache writes a versioned manifest at `.rpg_cache/content/manifest.json`.
- If `data_version` mismatches the current runtime data version, cache is rebuilt automatically.
- Data version is controlled by `RPG_CONTENT_DATA_VERSION` (default `0.1.0`).

Content provider environment variables:

- `RPG_CONTENT_TIMEOUT_S` (default `10`)
- `RPG_CONTENT_RETRIES` (default `2`)
- `RPG_CONTENT_BACKOFF_S` (default `0.2`)
- `RPG_CONTENT_CACHE_TTL_S` (default `86400`)
- `RPG_CONTENT_CACHE_DIR` (default `.rpg_cache/content`)
- `RPG_CONTENT_DATA_VERSION` (default `0.1.0`)
- `RPG_LOCAL_SRD_ENABLED` (default `1`)
- `RPG_LOCAL_SRD_DIR` (default `data/srd/2014`)
- `RPG_LOCAL_SRD_PAGE_SIZE` (default `50`)
- `RPG_CONTENT_RUNTIME_REMOTE_ENABLED` (default `0`)
- `RPG_IMPORT_INCLUDE_LOCAL_SRD` (default `1`)
- `RPG_HTTP_CIRCUIT_BREAKER_ENABLED` (default `1`)
- `RPG_HTTP_CIRCUIT_FAILURE_THRESHOLD` (default `3`)
- `RPG_HTTP_CIRCUIT_RESET_SECONDS` (default `120`)

Local SRD files are optional and expected as JSON in `RPG_LOCAL_SRD_DIR`:

- `races.json`
- `classes.json`
- `spells.json`
- `monsters.json`

Each file may be either a raw array of objects or an object containing `results`.

Spells data consolidation note:

- Unified canonical spells dataset is at `data/spells/unified_spells.json`.
- Source reference folder `data/spells_reference` has been retired; preservation artifacts are kept at:
        - `data/spells/spells_reference_manifest.json`
        - `data/spells/spells_reference_full_backup.zip`

Optional flavour enrichment (bounded, non-mechanical):

- `RPG_FLAVOUR_DATAMUSE_ENABLED` (default `0`)
- `RPG_FLAVOUR_TIMEOUT_S` (default `2`)
- `RPG_FLAVOUR_RETRIES` (default `1`)
- `RPG_FLAVOUR_BACKOFF_S` (default `0.1`)
- `RPG_FLAVOUR_MAX_LINES` (default `1`)

When enabled, Datamuse is used only to append at most one short descriptive flavour line to encounter intros.
Combat outcomes and game state remain deterministic and unchanged.

Optional mechanical flavour enrichment (deterministic, no rules impact):

- `RPG_MECHANICAL_FLAVOUR_DATAMUSE_ENABLED` (default `0`)
- `RPG_FLAVOUR_MAX_WORDS` (default `8`)

When enabled, Datamuse-backed vocabulary is used to add deterministic flavour lines to combat exchanges and biome hazard messaging.
Rules outcomes remain unchanged.

Run locally (prefers MySQL persistence, falls back to in-memory if unreachable):

```bash
python -m rpg
```

Optional dependency groups:

- Dev/testing tools:
        ```bash
        pip install -e .[dev]
        ```
- CLI/UI enhancements:
        ```bash
        pip install -e .[ui]
        ```
- Ops/config/perf tools:
        ```bash
        pip install -e .[ops]
        ```
- Install all optional groups:
        ```bash
        pip install -e .[dev,ui,ops]
        ```

Use MySQL schema + Open5e import:

1) Export `RPG_DATABASE_URL`, e.g. `mysql+mysqlconnector://user:pass@localhost:3306/rpg_game`.
2) Apply schema + migrations via Python runner (portable; no `mysql` CLI required):
        ```bash
        python -m rpg.infrastructure.db.mysql.migrate
        ```
        Notes:
        - Runs in strict linear mode (`001_*.sql`, `002_*.sql`, ...), rejecting gaps/out-of-order files.
        - Tracks applied files in `schema_migrations` to avoid re-applying migrations.
        - Legacy chain scripts are deprecated and not part of the default execution path.
   Optional verification-only pass:
        ```bash
        python -m rpg.infrastructure.db.mysql.migrate --dry-run
        ```
3) Import monsters from Open5e into MySQL (optionally pin them to the first location):
        ```bash
        python -m rpg.infrastructure.db.mysql.import_open5e_monsters --pages 2 --location-id 1
        ```
4) Import canonical magic items/equipment into MySQL item tables:
        ```bash
        python -m rpg.infrastructure.db.mysql.import_open5e_items --pages 2
        ```
4) Run game pointing at MySQL (world state persists via `world` table):
        ```bash
        set RPG_DATABASE_URL=mysql+mysqlconnector://user:pass@localhost:3306/rpg_game
        python -m rpg
        ```

Prewarm content cache (optional):

1) Preview planned cache warm calls (no network execution):
        ```bash
        python -m rpg.infrastructure.prewarm_content_cache --mode dry-run --targets all --pages 1
        ```
2) Execute warm calls for selected targets/pages:
        ```bash
        python -m rpg.infrastructure.prewarm_content_cache --mode execute --strategy runtime --targets races classes spells monsters --pages 2
        ```

Contributor quickstart + troubleshooting runbook:
- `docs/contributor_runbook.md`

Full gameplay feature/function reference:
- `docs/game_features_and_functions_reference.md`

Narrative simulation batch validation report:
- `docs/narrative_simulation_batch.md`

Generate runtime narrative quality report artifact (deterministic fixed-batch by default):

```bash
python -m rpg.infrastructure.narrative_quality_report --output artifacts/narrative_quality_report.json
```

Optional profile selection and seed override:

```bash
python -m rpg.infrastructure.narrative_quality_report --profile strict --seeds 101,202,303
```

Optional named script preset:

```bash
python -m rpg.infrastructure.narrative_quality_report --script-name exploration_heavy --profile exploratory
```

Compare two report artifacts (drift summary):

```bash
python -m rpg.infrastructure.narrative_quality_report --compare-base artifacts/base.json --compare-candidate artifacts/candidate.json
```

Report artifacts include a versioned `schema` object and are validated for compatibility before write/load.

Validate dialogue tree content file:

```bash
python -m rpg.infrastructure.dialogue_content_validator --path data/world/dialogue_trees.json
```

Optional session-end artifact hook (on main-menu quit):

```bash
set RPG_NARRATIVE_SESSION_REPORT_ENABLED=1
set RPG_NARRATIVE_SESSION_REPORT_OUTPUT=artifacts/narrative_quality_session_report.json
set RPG_NARRATIVE_SESSION_REPORT_PROFILE=balanced
python -m rpg
```

Gameplay loop quick reference:
- Main loop: Act, Travel, Rest, Character, Quit.
- Act is location-aware: Town Activities in town, Explore Area in wilderness.
- Town loop: Talk, Quest Board, Rumour Board, Shop, Training, View Factions.
- Menu controls are consistent across screens: Up/Down (or W/S), Enter to confirm, Esc/Q to back out.

Gameplay troubleshooting:
- If a submenu appears stale after state-changing actions, leave and re-enter the town menu to refresh intent views.
- If MySQL connectivity is unstable during playtesting, unset `RPG_DATABASE_URL` to switch to in-memory mode for deterministic local iteration.
- If deterministic checks differ between runs, verify the same world turn and action sequence are used before comparing outcomes.

Next steps:
- Flesh out domain stats, factions, and encounter tables
- Add tests under `tests/`
