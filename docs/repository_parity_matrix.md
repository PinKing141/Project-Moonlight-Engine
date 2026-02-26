# Repository Parity Audit Matrix (P3-T01)

## Scope
This matrix covers repository methods currently used by `src/rpg/application/**` services and verifies parity between active runtime adapters:

- In-memory adapters under `src/rpg/infrastructure/inmemory`
- MySQL adapters in `src/rpg/infrastructure/db/mysql/repos.py`

## Application-used repository methods

| Repository Interface | Application-used methods |
|---|---|
| `CharacterRepository` | `get`, `list_all`, `save`, `create`, `find_by_location` |
| `WorldRepository` | `load_default`, `save` |
| `EntityRepository` | `get_many`, `list_by_location`, `list_for_level`, `list_by_level_band` |
| `LocationRepository` | `get`, `list_all`, `get_starting_location` |
| `ClassRepository` | `list_playable` |
| `SpellRepository` | `get_by_slug` (optional wiring; used when spell repo exists) |

## Adapter parity matrix

| Interface | Method | In-memory | MySQL | Notes |
|---|---|---|---|---|
| CharacterRepository | `get` | ✅ | ✅ | Required for player/session lookup |
| CharacterRepository | `list_all` | ✅ | ✅ | Used in continue/load flows |
| CharacterRepository | `save` | ✅ | ✅ | Used after rest/combat and state writes |
| CharacterRepository | `create` | ✅ | ✅ | Character creation path |
| CharacterRepository | `find_by_location` | ✅ | ✅ | Used by progression/domain behavior |
| WorldRepository | `load_default` | ✅ | ✅ | World tick/read path |
| WorldRepository | `save` | ✅ | ✅ | World tick persistence |
| EntityRepository | `get_many` | ✅ | ✅ | Encounter table/entity hydration |
| EntityRepository | `list_by_location` | ✅ | ✅ | Primary encounter sourcing |
| EntityRepository | `list_for_level` | ✅ | ✅ | Fallback encounter sourcing |
| EntityRepository | `list_by_level_band` | ✅ | ✅ | Encounter planner/path parity |
| LocationRepository | `get` | ✅ | ✅ | Character location/context |
| LocationRepository | `list_all` | ✅ | ✅ | Creation and location listings |
| LocationRepository | `get_starting_location` | ✅ | ✅ | Character spawn point |
| ClassRepository | `list_playable` | ✅ | ✅ | Character creation class options |
| SpellRepository | `get_by_slug` | N/A runtime | ✅ | In-memory runtime currently does not wire a spell repo |

## Findings

- No adapter-specific imports/assumptions should exist in `src/rpg/application/**`.
- Runtime parity for currently used app methods is present for in-memory and MySQL adapters.
- `SpellRepository` is optional in in-memory runtime wiring; `GameService` already guards this with nullable behavior.

## Evidence

- Static audit tests: `tests/unit/test_repository_parity_audit.py`
- Runtime regression suite: `tests/test_game_logic.py`, `tests/e2e/test_cli_flow.py`
