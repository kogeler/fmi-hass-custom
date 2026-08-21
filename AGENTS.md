<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# FMI Custom Integration Agent Guide

## Repository Scope

This repository contains the `fmi` custom integration for Home Assistant. It exposes FMI current
weather, hourly/daily forecasts, forecast-backed sensors, optional station observations,
lightning, and sea-level data. The `homeassistant` value in `hacs.json` is the installation floor,
not the current test target; preserve it unless a reproduced integration incompatibility requires
raising it. Do not infer an official Core quality tier. Read the current project version from
`.version`, never from copied documentation.

Preserve user configuration, unique IDs, entity registry records, and customized entity IDs.
Do not refactor for its own sake. Every behavior or structural change needs a documented
correctness, compatibility, testability, migration, security, privacy, or validation reason.

## Layout

- `custom_components/fmi/`: distributed integration, manifest, translations, and brand asset.
- `tests/`: offline unit/contract/HA integration tests plus explicitly marked live probes.
- `docs/USER_GUIDE.md`: end-user installation, configuration, and dashboard guidance.
- `docs/contracts/`: only normative source for current integration/repository behavior; every
  assertion has a stable ID and links to its automated test evidence.
- `docs/maintenance/`: rationale, change checklists, runbooks, and external references that link to
  the normative contracts; never duplicate contract assertions or store session reports here.
- `plans/README.md`: archive boundary and index for completed P01–P04 plans, dated baselines,
  decisions, verification, and historical handoffs. Use these only when the reason or history of a
  current contract matters.
- `.github/scripts/` and `.github/workflows/`: tested Python CI helpers and GitHub Actions policy.
- `containers/toolbox/` and `make/container.mk`: content-addressed rootless Podman environment,
  tar-stream transport, confinement policy, and OCI cache operations.
- `pyproject.toml` and `tools/lint/pyproject.toml`: the only direct Python dependency manifests;
  the three root `requirements*.txt` files are generated hash locks.
- `.version`: only human-maintained release version; the manifest is a synchronized mirror.

## Contract Documentation Map

Read the smallest relevant contract set before changing code. Update the owning assertion and its
test evidence together when behavior deliberately changes. Contract IDs are permanent; maintenance
runbooks and implementation modules link to them instead of restating them.

| File | Read or update when working on |
|---|---|
| `AVAILABILITY.md` | Setup success, independent source failures, stale-data clearing, recovery, or entity availability |
| `CI.md` | Workflow triggers, permissions, required checks, PR-body automation, versioning, HACS layout, or release gates |
| `COMPATIBILITY_SECURITY.md` | HA/Python reference boundaries, privacy, diagnostics, logging, XML safety, or data disclosure |
| `DEPENDENCIES.md` | Manifest ownership, locks, resolver bootstrap, audit, Dependency Submission, confinement, or xdist policy |
| `FORECAST_SEMANTICS.md` | Hourly/daily schema, timestamps, local-day grouping, precipitation, aggregation, or condition precedence |
| `LIVE_TESTS.md` | Public live locations, request budget, network marker isolation, assertions, or failure classification |
| `MIGRATIONS.md` | Config-entry versioning, registry migration, legacy IDs, collisions, daily entity retention, or upgrade fixtures |
| `OPTIONAL_SOURCES.md` | Lightning/sea-level HTTP, freshness, bounding boxes, local geometry, optional availability, or coordinate disclosure |
| `RECONFIGURATION.md` | Location changes, duplicate checks, mutable coordinates, immutable identity, or reconfigure failures |
| `RUNTIME.md` | Coordinator ownership, lifecycle, executor/I/O boundaries, request cadence, timeout policy, logs, or diagnostics |
| `SENSORS.md` | Sensor metadata, gust-source adapter, device/entity naming, native units, or conservative ID migration |
| `TIME_AND_MISSING_DATA.md` | Home Assistant timezone use, sun events, calendar/DST boundaries, timestamps, or malformed FMI values |

Paths in this table are relative to `docs/contracts/`. Use the same-named file under
`docs/maintenance/` for change procedures/rationale; use `DEVELOPMENT.md`, `HACS_RELEASES.md`, and
`HA_RELEASE_MAINTENANCE.md` there for their specialized runbooks.

## Commands

Run supported Python and Home Assistant commands through rootless Podman. The host Python is not a
fallback.

Agents must invoke repository tooling, Python, Home Assistant, validators, dependency operations,
and containers only through supported `make` targets. Never invoke `podman`, `docker`, a container
image, or a tool inside an image directly, including for one-off inspection or diagnostics. If the
required operation has no suitable target, first extend the repository Make tooling with a
reviewable target that preserves the documented confinement, network, archive-transport, and
artifact rules, then use that target. Read-only host inspection with tools such as `git`, `rg`, and
`sed`, and file edits through the supported patch mechanism, remain allowed.

| Task | Command |
|---|---|
| Verify rootless Podman | `make doctor` |
| Build/sync environment | `make dev-build` |
| Inspect locked FMI/HA contracts | `make reference-contracts` |
| Regenerate all three hash locks | `make lock` |
| Check lock reproducibility | `make freeze-check` |
| Format / check | `make format` / `make format-check` |
| Ruff and Pylint | `make lint` |
| Mypy | `make type-check` |
| Bandit / shell checks | `make bandit` / `make syntax` / `make shellcheck` |
| Fast offline tests | `make test-fast` |
| Full offline coverage | `make test-full` |
| Prepare immutable validator images | `make validator-images` |
| Home Assistant/hassfest/actionlint validation | `make validate` |
| Version metadata | `make version-check` |
| Prove network blocking | `make test-network-block` |
| Live FMI probes | `make live` |
| Stable / prerelease drift | `make compatibility-stable` / `make compatibility-prerelease` |
| Reviewed vulnerability policy / raw inventory | `make audit` / `make audit-raw` |
| License inventory | `make licenses` |
| Build all three Dependency Submission manifests | `make dependency-snapshot` |
| Prove container confinement | `make confinement-test` |

`make compatibility-stable` and `make compatibility-prerelease` are expensive final moving-target
gates. Do not run either during iterative implementation, at intermediate plan/session boundaries,
or merely to reconfirm an unchanged result. First finish code, tests, documentation, and release
metadata, then pass every other required static, offline, validation, security, dependency,
confinement, and live gate. Run each moving compatibility target once, last, against that unchanged
final candidate; record its exact result so later work can reuse the evidence. Repeat one only when
an earlier run failed and a relevant fix was applied, or when runtime code, tests, dependency
metadata/locks, compatibility tooling, or the upstream channel changed after that run. Documentation,
plan, or report-only edits do not invalidate successful compatibility evidence. When a prerelease
run reports the explicit successful no-newer-prerelease skip, do not rerun it in the same work
session without evidence that the upstream channel changed. Compatibility-tooling diagnosis and an
explicit owner request are the only reasons to invoke these targets before final-gate order.

Every pytest path uses pytest-xdist with `PYTEST_WORKERS=auto` by default and
`--dist=worksteal`, including offline, network-block, live, and moving compatibility runs. Xdist
derives the automatic count from the CPU resources visible inside the container. An explicit
`PYTEST_WORKERS=<N>` is diagnostic only; do not introduce a serial default or a special serial
suite. Live workers share one cross-process twelve-attempt budget and two-request semaphore. Make
serializes its target graph even if invoked with `-j`; test parallelism belongs inside xdist, not
across competing toolbox containers and shared artifacts.

## Test And Network Rules

Ordinary tests must be deterministic and offline. Pytest blocks sockets, and every project-aware
command except Ruff runs in a rootless container. The default test, analysis, and local-validator
contours use `--network=none`; dependency resolution/audit, HACS validation, moving compatibility,
outdated-package inventory, and marked live probes use explicit purpose-limited online contours.
Ruff alone uses the hash-locked host `venv-lint/`. Source is streamed into private tmpfs; never
bind-mount the checkout, Git metadata, a host virtual environment, or a Podman socket. Only tests
marked `live` may contact FMI, using public test locations and the request budget in
`docs/contracts/LIVE_TESTS.md`. Never use owner coordinates or captured private payloads.

Add coverage proportional to risk. Public behavior, lifecycle, registry migration, source
availability, and user-visible fixes require Home Assistant-level regressions. Do not weaken an
assertion, suppress a checker, or hide an exception to obtain a passing result. Never say a check
passed unless that exact command/run completed successfully.

## Home Assistant Runtime Rules

Obey the linked `RUN-*`, `AVL-*`, `FCS-*`, `SNS-*`, `TIM-*`, `OPT-*`, and `CSP-*` assertions in
`docs/contracts/`. Do not add a runtime behavior comment or maintenance rule that restates one of
those assertions; link its ID instead. Public behavior, lifecycle, and privacy changes require
Home Assistant-level evidence linked from the owning assertion.

## Identity And Migration

Follow `docs/contracts/MIGRATIONS.md` and `docs/contracts/RECONFIGURATION.md`. Any identity,
registry, collision, or reconfiguration change must update the owning `MIG-*`/`RCF-*` assertion and
its Home Assistant test evidence before implementation is considered complete.

## Dependencies And Releases

Follow `docs/contracts/DEPENDENCIES.md`, `docs/contracts/COMPATIBILITY_SECURITY.md`, and
`docs/contracts/CI.md` for normative dependency, support, privacy, workflow, version, and
publication requirements. Operational procedures are in `docs/maintenance/DEVELOPMENT.md`,
`DEPENDENCIES.md`, `CI.md`, `HACS_RELEASES.md`, and `HA_RELEASE_MAINTENANCE.md`. Review both
vulnerability and license results. Never publish manually.

## Working Protocol

Inspect `git status`, relevant code/tests/docs, and unexplained user changes before editing. Never
reset, stash, overwrite, or reformat unrelated work. Do not run Git operations that can require a
hardware token, interactive credentials, or authenticated SSH. Never create a commit unless the
owner explicitly commands it in the current conversation. Never push under any circumstances;
only the owner pushes. Never override or bypass values inherited from global Git configuration,
including author, committer, identity, signing, hooks, credentials, or transport settings (for
example through command-line `-c`, environment variables, or repository-local configuration).
Commit messages and suggested commit messages must describe the completed change without plan,
session, or step identifiers such as `P03`, `S04`, or `P03-S04`.

For follow-up maintenance, current code, tests, and the owning `docs/contracts/` assertion are the
sources of truth. Use `plans/*` only to understand historical decisions and verification; do
not extend it as a tracker for unrelated future work. A new implementation plan
gets its own plan/handoff namespace. When execution finds a plan error or deliberately departs from
the plan, correct the plan immediately before continuing the affected work; do not defer that
correction to a report or final review.
Record only notable release-level or unreleased HA-reference maintenance changes in
`CHANGELOG.md`. New human-authored files use `Copyright (c) 2026 kogeler` and
`SPDX-License-Identifier: MIT` where comments are supported.

Work is done only when the requested behavior is implemented and documented, relevant offline and
Home Assistant tests pass, format/lint/type checks do not regress, migrations and privacy remain
safe, required validation is run, the diff contains no unrelated change, and remaining risk is
stated precisely. End a planned session with one concise suggested owner commit message; that
suggestion does not authorize creating the commit.
