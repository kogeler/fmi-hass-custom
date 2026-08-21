<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Contract Catalog

This directory is the only normative specification for current, testable repository and
integration behavior. Implementation modules and maintenance runbooks link here instead of
restating these requirements. `AGENTS.md` separately governs agent execution, historical decisions
and completed-plan evidence remain under `plans/`, and user instructions remain in
`docs/USER_GUIDE.md`.

The key words `MUST`, `MUST NOT`, `SHOULD`, `SHOULD NOT`, and `MAY` are interpreted as described
in [BCP 14](https://www.rfc-editor.org/info/bcp14) when they appear in uppercase. Every normative
assertion has a stable ID and links to one or more concrete automated tests. This follows the
requirement/verification traceability structure described by NASA's
[Requirements Verification Matrix](https://www.nasa.gov/reference/system-engineering-handbook-appendix/).
Relative links follow
[GitHub's repository-documentation guidance](https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax#relative-links),
so they remain usable on branches and in local clones. Automated evidence is consistent with Home
Assistant's emphasis on maintaining integration behavior through
[test coverage](https://developers.home-assistant.io/docs/core/integration-quality-scale/).

## Contract Format

Each assertion uses this exact shape:

```markdown
### `ABC-001` — Short title

**Contract:** The implementation MUST ...

**Evidence:**

- [`test_behavior`](../../tests/test_example.py) — `tests/test_example.py::test_behavior`
```

IDs are permanent. Removing or changing an assertion requires reviewing all linked tests and every
implementation/maintenance reference. A link identifies the test definition; a successful
supported Make test run is the execution evidence. External specifications may explain a contract
but never replace repository test evidence.

## Index

| Contract | Prefix | Scope |
|---|---|---|
| [Availability](AVAILABILITY.md) | `AVL` | Setup, source isolation, stale clearing, and recovery |
| [Runtime](RUNTIME.md) | `RUN` | Entry ownership, cadence, I/O, cancellation, and request topology |
| [Sensors](SENSORS.md) | `SNS` | Entity metadata, source adapters, values, and attributes |
| [Forecast semantics](FORECAST_SEMANTICS.md) | `FCS` | Hourly/daily normalization, aggregation, and API shape |
| [Time and missing data](TIME_AND_MISSING_DATA.md) | `TIM` | Timezones, symbols, invalid values, and Best time |
| [Optional sources](OPTIONAL_SOURCES.md) | `OPT` | Lightning and sea-level transport, geometry, freshness, and state |
| [Migrations](MIGRATIONS.md) | `MIG` | Config/device/entity registry upgrade guarantees |
| [Reconfiguration](RECONFIGURATION.md) | `RCF` | Mutable location, immutable identity, duplicates, and atomic failure |
| [Compatibility, security, and privacy](COMPATIBILITY_SECURITY.md) | `CSP` | Support boundaries, XML, logs, diagnostics, and data disclosure |
| [Dependencies](DEPENDENCIES.md) | `DEP` | Manifest ownership, locks, resolver, audit, and confinement |
| [CI and releases](CI.md) | `CIR` | Workflow topology, permissions, versioning, HACS, and publication |
| [Live tests](LIVE_TESTS.md) | `LIV` | Public probes, request budget, assertions, and CI isolation |
