<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Compatibility, Security, And Privacy

This document defines the current support and protection boundaries for maintainers. Update it
when the supported Home Assistant line, dependency graph, external services, diagnostics, logging,
or CI trust model changes. Keep historical audit narrative outside this current contract.

Last verified: 2026-08-08.

## Support Matrix

| Environment | Contract |
|---|---|
| Home Assistant 2026.8.1 / Python 3.14.2 | Reproducible release reference. The committed full freeze and complete lifecycle/config/entity/migration suite target this pair; it is not the HACS installation floor. |
| HACS installation floor | The value in `hacs.json` is retained until a reproduced integration or runtime incompatibility requires raising it. A routine reference-lock refresh is not such evidence. |
| Latest Home Assistant stable | Required moving compatibility signal. It resolves, freezes, recreates, and tests the current published stable graph without changing the reference lock. A pass is evidence for that run, not a permanent future-version promise. |
| Latest Home Assistant prerelease | Informational moving signal. No newer installable prerelease is a successful explicit skip; a real beta or helper failure remains visible without blocking the supported release. |

Compatibility claims come from functional lifecycle, configuration, entity, migration, and source
tests. Tests and runtime code must not encode concrete Home Assistant, test-helper, or minimum
version assertions. Exact reference versions live in the reviewed direct requirements and generated
full freeze; the independently maintained HACS floor may be raised only for a demonstrated broken
contract, with regression evidence and documented user impact.

This is a HACS custom integration. It does not claim an official Home Assistant Core quality tier.
The selected FMI client is not fully async; its synchronous work must remain executor-isolated as
defined in `RUNTIME.md`.

## Home Assistant Contracts

- Per-entry state lives in typed `ConfigEntry.runtime_data` and must survive lifecycle operations
  without cross-entry leakage.
- User, options, and reconfigure flows use current Home Assistant APIs, validate FMI connectivity,
  reject duplicate locations, and preserve stable identity.
- Weather entities expose separate hourly and daily async forecast APIs with current feature flags,
  native units, and aware UTC timestamps.
- Sensors use current entity descriptions, device/state classes where applicable, translated names,
  stable unique IDs, and coordinator-driven polling.
- Existing config and registry state follows `MIGRATIONS.md`; do not trade compatibility for cleaner
  generated names.
- Both read-only coordinator platforms keep `PARALLEL_UPDATES = 0`.

## Data And Privacy Boundaries

- FMI necessarily receives configured coordinates for setup validation, current/forecast,
  lightning-area, and sea-level requests. Responses are processed in memory and are not copied to
  diagnostics.
- When lightning is enabled, Nominatim receives only a selected public FMI strike coordinate on a
  cache miss, never the configured home coordinate. The returned address may be shown as the
  lightning sensor value; raw strike coordinates are its documented fallback.
- Logs contain source names, transitions, HTTP status classes, and exception class names only.
  Configured coordinates, coordinate-derived identity, raw responses, and arbitrary external
  exception content are prohibited.
- Diagnostics expose sanitized health/configuration metadata only. They exclude coordinates,
  place/weather values, external payloads, entry IDs, unique IDs, and legacy coordinate identity.
- Entity states intentionally expose configured place and weather data to the Home Assistant user;
  that user-facing behavior is distinct from logs and downloadable diagnostics.

## Accepted Constraints

- Home Assistant 2026.8.1 pins cryptography 48.0.1 with three known advisories. The integration
  neither imports nor declares it. The owner-approved private-testing exception is exact by
  package, version, and advisory ID; `TODO.md` records the upstream removal trigger.
- Public Nominatim usage is accepted only for the owner's small private deployment. It is disabled
  unless lightning is enabled, cached, attributed, limited to one lookup per update, and globally
  bounded to four requests/minute. Before broader distribution, follow the provider/removal work in
  `TODO.md`.
- A live FMI/network outage blocks required CI by explicit policy. Re-run once and classify the
  failure with `LIVE_TESTS.md`; do not weaken assertions or silently make the probe optional.

## Dependency And Workflow Security

- `make audit` passes only when the full reference freeze matches the exact reviewed exception set;
  new findings and stale exceptions fail. `make audit-raw` remains nonzero while the upstream
  cryptography pin is vulnerable. `make licenses` must report no unknown license.
- The integration-declared FMI/geopy runtime closure has no accepted vulnerability exception.
- Workflows use read-only permissions by default, full-SHA action references, immutable container
  digests, bounded timeouts, and cancellation for superseded runs.
- Only the final release job receives `contents: write`; CodeQL receives
  `security-events: write` only to upload results.
- The metadata-only `pull_request_target` workflow executes trusted default-branch code and treats
  the source changelog as bounded inert data. Never check out or execute PR-head code with its write
  token.
- Every repository-authored CI helper is Python under `.github/scripts/`. GitHub API calls use the
  SHA-pinned native `actions/github-script`; workflows do not use `curl`, `gh api`, or a custom HTTP
  client.

## Maintainer Verification

Run `make test-full`, `make type-check`, `make test-network-block`, `make validate`, `make audit`,
and `make licenses` after changing compatibility, logging, diagnostics, dependency, or workflow
boundaries. Run both compatibility targets for a support-policy change, and inspect CodeQL/HACS
results on the pull request.

## References

- [Home Assistant integration quality guidance](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/)
- [Runtime data](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/runtime-data/)
- [Diagnostics and coordinate redaction](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/diagnostics/)
- [Coordinator and polling guidance](https://developers.home-assistant.io/docs/integration_fetching_data/)
- [Weather entity API](https://developers.home-assistant.io/docs/core/entity/weather/)
- [Sensor entity API](https://developers.home-assistant.io/docs/core/entity/sensor/)
- [OSMF Nominatim usage policy](https://operations.osmfoundation.org/policies/nominatim/)
