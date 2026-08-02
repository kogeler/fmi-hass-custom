<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# FMI Custom Integration Agent Guide

## Repository Scope

This repository contains the `fmi` custom integration for Home Assistant. It exposes FMI current
weather, hourly/daily forecasts, forecast-backed sensors, optional station observations,
lightning, and sea-level data. The latest published release supports the current stable Home
Assistant line declared in `hacs.json`; do not infer support for older releases or an official Core
quality tier. Read the current project version from `.version`, never from copied documentation.

Preserve user configuration, unique IDs, entity registry records, and customized entity IDs.
Do not refactor for its own sake. Every behavior or structural change needs a documented
correctness, compatibility, testability, migration, security, privacy, or validation reason.

## Layout

- `custom_components/fmi/`: distributed integration, manifest, translations, and brand asset.
- `tests/`: offline unit/contract/HA integration tests plus explicitly marked live probes.
- `docs/USER_GUIDE.md`: end-user installation, configuration, and dashboard guidance.
- `docs/maintenance/`: current technical contracts for future maintenance; never store plan
  progress, session reports, or before/after summaries here.
- `plans/P01/`: completed implementation plan (`PLAN.md`), baseline, decisions, verification, and
  historical handoffs. Use these only when the reason or history of a current contract matters.
- `plans/P02/`: planned location-selection work (`PLAN.md`), its S00-verified baseline, and future
  execution reports, following the same self-contained layout as P01.
- `.github/scripts/` and `.github/workflows/`: tested Python CI helpers and GitHub Actions policy.
- `.version`: only human-maintained release version; the manifest is a synchronized mirror.

## Maintenance Documentation Map

Read the smallest relevant set before changing code, then update the owning document when its
current contract changes. These files describe what must remain true, not how plan P01 was
executed.

| File | Read or update when working on |
|---|---|
| `AVAILABILITY.md` | Setup success, independent source failures, stale-data clearing, recovery, or entity availability |
| `CI.md` | Workflow triggers, permissions, required checks, PR-body automation, branch protection, or release gates |
| `COMPATIBILITY_SECURITY.md` | Supported HA/Python matrix, privacy boundaries, accepted vulnerabilities, diagnostics, logging, or workflow trust |
| `DEPENDENCIES.md` | Requirement-file ownership, selected versions, action/image pins, vulnerability/license policy, or lock changes |
| `DEVELOPMENT.md` | Podman environment, Make targets, dependency regeneration, xdist policy, formatting, linting, or repository layout |
| `FORECAST_SEMANTICS.md` | Hourly/daily schema, timestamps, local-day grouping, precipitation, aggregation, or condition precedence |
| `HACS_RELEASES.md` | HACS layout/discovery, `.version`, manifest synchronization, changelog rules, tags, releases, or remote settings |
| `LIVE_TESTS.md` | Public live locations, request budget, network marker isolation, assertions, or failure classification |
| `MIGRATIONS.md` | Config-entry versioning, registry migration, legacy IDs, collisions, daily entity retention, or upgrade fixtures |
| `OPTIONAL_SOURCES.md` | Lightning/sea-level HTTP, freshness, bounding boxes, geocoding, optional availability, or coordinate disclosure |
| `RECONFIGURATION.md` | Location changes, duplicate checks, mutable coordinates, immutable identity, or reconfigure failures |
| `RUNTIME.md` | Coordinator ownership, lifecycle, executor/I/O boundaries, request cadence, timeout policy, logs, or diagnostics |
| `SENSORS.md` | Sensor metadata, gust-source adapter, device/entity naming, native units, or conservative ID migration |
| `TIME_AND_MISSING_DATA.md` | Home Assistant timezone use, sun events, calendar/DST boundaries, timestamps, or malformed FMI values |

Paths in this table are relative to `docs/maintenance/`.

## Commands

Run supported Python and Home Assistant commands through rootless Podman. The host Python is not a
fallback.

| Task | Command |
|---|---|
| Build/sync environment | `make dev-build` |
| Regenerate complete freeze | `make lock` |
| Format / check | `make format` / `make format-check` |
| Ruff and Pylint | `make lint` |
| Mypy | `make type-check` |
| Fast offline tests | `make test-fast` |
| Full offline coverage | `make test-full` |
| Home Assistant/hassfest/actionlint validation | `make validate` |
| Version metadata | `make version-check` |
| Prove network blocking | `make test-network-block` |
| Live FMI probes | `make live` |
| Stable / prerelease drift | `make compatibility-stable` / `make compatibility-prerelease` |
| Reviewed vulnerability policy / raw inventory | `make audit` / `make audit-raw` |
| License inventory | `make licenses` |

`PYTEST_WORKERS=2` (or another pytest-xdist value) is opt-in for offline tests. Keep the measured
faster single-process default unless a new benchmark justifies changing it. Live probes and the
network-block test stay sequential.

## Test And Network Rules

Ordinary tests must be deterministic and offline. Pytest blocks sockets, and format, lint, typing,
offline tests, and local validation run in containers with `--network=none`. Only tests marked
`live` may contact FMI, using public test locations and the request budget in
`docs/maintenance/LIVE_TESTS.md`. Never use owner coordinates or captured private payloads.

Add coverage proportional to risk. Public behavior, lifecycle, registry migration, source
availability, and user-visible fixes require Home Assistant-level regressions. Do not weaken an
assertion, suppress a checker, or hide an exception to obtain a passing result. Never say a check
passed unless that exact command/run completed successfully.

## Home Assistant Runtime Rules

- Store per-entry runtime ownership in typed `ConfigEntry.runtime_data`; unload and reload must
  remove listeners and preserve independent entries.
- Use coordinators and `CoordinatorEntity` lifecycle APIs. Entity properties read cached memory and
  do no I/O.
- Keep forecast/current, configured station observations, lightning, and sea-level failure
  boundaries independent. Clear invalid stale data and allow later coordinator refreshes to recover.
- Use Home Assistant's shared async HTTP session and bounded timeouts for integration-owned I/O.
  Move unavoidable blocking dependency/parser/geocoder work to the executor; never block the event
  loop or swallow cancellation.
- Keep logs and diagnostics free of configured coordinates, raw external responses, and
  coordinate-derived identity.

Hourly/daily schema, timezone, precipitation, condition, wind, and missing-data rules are
authoritative in `docs/maintenance/FORECAST_SEMANTICS.md`. Availability, runtime, and
optional-source contracts are in `AVAILABILITY.md`, `RUNTIME.md`, and `OPTIONAL_SOURCES.md` in the
same directory.

## Identity And Migration

Config entry version 2 separates immutable `entity_identity` from mutable coordinates and display
place. Never change existing entity/device unique IDs merely to improve naming. Preserve customized,
ambiguous suffixed, and collision-affected entity IDs. Rename only an exact known legacy generated
default when the documented target is free. Reconfigure one entry in place and reject duplicate
coordinates. Follow `docs/maintenance/MIGRATIONS.md` and `RECONFIGURATION.md`.

## Dependencies And Releases

`requirements-direct.txt` is the reviewed direct input for the supported environment; root
`requirements.txt` is a generated complete `pip freeze` and must not be hand-edited.
`requirements-bootstrap.txt` isolates pip. Moving compatibility inputs stay unpinned and generate
separate per-run freezes. Every automated `pip install` consumes a requirements/constraint file,
never inline package names or versions. Follow `docs/maintenance/DEVELOPMENT.md` for updates and
review both vulnerability and license results. Support, privacy, and accepted-risk boundaries are
in `docs/maintenance/COMPATIBILITY_SECURITY.md`.

Every PR to `master` must increment `.version`, synchronize the manifest, and add the matching
dated changelog section. Required CI includes offline coverage, bounded live FMI, validation,
dependency risk, CodeQL, current stable compatibility, and version comparison; prerelease
compatibility is informational. A successful version-incrementing `master` push publishes the tag
and GitHub Release only after trusted repeated gates. Do not publish manually. See
`docs/maintenance/CI.md` and `HACS_RELEASES.md`.

## Working Protocol

Inspect `git status`, relevant code/tests/docs, and unexplained user changes before editing. Never
reset, stash, overwrite, or reformat unrelated work. Do not run Git operations that can require a
hardware token, interactive credentials, or authenticated SSH. Do not commit; the owner commits.

For follow-up maintenance, current code, tests, and the owning `docs/maintenance/` contract are the
sources of truth. Use `plans/*` only to understand historical decisions and verification; do
not extend it as a tracker for unrelated future work. A new implementation plan
gets its own plan/handoff namespace and must be corrected immediately when verified reality differs.
Record only notable release-level changes in `CHANGELOG.md`. New human-authored files use
`Copyright (c) 2026 kogeler` and `SPDX-License-Identifier: MIT` where comments are supported.

Work is done only when the requested behavior is implemented and documented, relevant offline and
Home Assistant tests pass, format/lint/type checks do not regress, migrations and privacy remain
safe, required validation is run, the diff contains no unrelated change, and remaining risk is
stated precisely. End a planned session with one concise suggested owner commit message beginning
with its session ID; do not create the commit yourself.
