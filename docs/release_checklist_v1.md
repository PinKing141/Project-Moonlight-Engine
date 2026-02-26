# Release Checklist v1.0 CLI Core

## Build Quality

- [x] Unit test suite passes
- [x] Integration test suite passes
- [x] E2E suite passes
- [x] Root-level regression suites pass

## Runtime Quality

- [x] Canonical entrypoint verified: `python -m rpg`
- [x] CLI input/navigation consistency validated
- [x] Friendly runtime error/help surface verified (no raw tracebacks in handled flows)

## Persistence Quality

- [x] Migration chain portable and complete (`_apply_all.sql` includes `001..003`)
- [x] Atomic character/world persistence path covered
- [x] Migration clean-install + incremental-upgrade checks completed

## Contract Quality

- [x] Versioned application contract documented
- [x] Contract compatibility tests guard command/query names and DTO fields

## Documentation

- [x] README updated for runtime + migration usage
- [x] Contributor runbook available (`docs/contributor_runbook.md`)

## Release Decision

- [x] Ready to tag `v1.0.0-cli-core` when desired
