# Contributor Runbook

This runbook is the quickest path to run Project Moonlight from a clean checkout.

## 1) Environment

- Windows or any environment with Python 3.14+
- Virtual environment at `.venv` (or your own active environment)

## 2) Install dependencies

```bash
C:/Users/Favour/Documents/Github/project-moonlight-main/.venv/Scripts/python.exe -m pip install -e .
```

## 3) Run with in-memory persistence (zero external services)

```bash
set RPG_DATABASE_URL=
python -m rpg
```

## 4) Run with MySQL persistence

1. Set DB URL:

```bash
set RPG_DATABASE_URL=mysql+mysqlconnector://root@127.0.0.1:3307/rpg_game
```

2. Apply schema + migrations:

```bash
python -m rpg.infrastructure.db.mysql.migrate
```

3. Launch the game:

```bash
python -m rpg
```

## 5) Validate test matrix

```bash
python -m pytest tests/unit -q
python -m pytest tests/integration -q
python -m pytest tests/e2e -q
python -m pytest tests/test_game_logic.py tests/test_inmemory_repositories.py tests/test_mysql_repositories.py -q
```

## 6) Troubleshooting

- `Can't connect to MySQL server`: confirm `RPG_DATABASE_URL` host/port and that MySQL is reachable.
- Migration syntax errors: run latest repo migrations (`002`, `003`) and avoid stale local copies.
- CLI exits with handled runtime error: check printed help surface and retry with in-memory mode by clearing `RPG_DATABASE_URL`.

## 7) Narrative Quality Ops (Release Gate)

### Required command set

1. Generate baseline artifact (balanced profile):

```bash
python -m rpg.infrastructure.narrative_quality_report --profile balanced --output artifacts/narrative_quality_base.json
```

2. Generate candidate artifact (target profile/script for current change):

```bash
python -m rpg.infrastructure.narrative_quality_report --profile strict --script-name baseline --output artifacts/narrative_quality_candidate.json
```

3. Compare drift:

```bash
python -m rpg.infrastructure.narrative_quality_report --compare-base artifacts/narrative_quality_base.json --compare-candidate artifacts/narrative_quality_candidate.json
```

### Recommended profile by workflow

- Feature implementation PRs: `balanced`
- Tuning/rebalance PRs: `strict`
- Exploratory narrative design spikes: `exploratory` (not release-blocking unless promoted)

### Release verdict policy

- `go`: merge/release may proceed if all other CI checks pass.
- `hold`: release is blocked until either:
	- blockers are removed, or
	- an explicit waiver is approved.

### Waiver policy (`hold` override)

- Required approvers:
	- one code owner (or maintainer), and
	- one narrative/system reviewer.
- Required record fields (add to PR description or release notes):
	- date/time (UTC),
	- compared artifact paths,
	- blocker list,
	- waiver reason,
	- mitigation/rollback note.
- Waiver validity:
	- single release window only; must be re-approved for subsequent releases.
