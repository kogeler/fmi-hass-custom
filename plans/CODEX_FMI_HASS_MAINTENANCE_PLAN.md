# Codex Implementation Plan: Stabilize, Test, and Maintain `fmi-hass-custom`

> **Target repository:** a local clone of the owner's fork of [`anand-p-r/fmi-hass-custom`](https://github.com/anand-p-r/fmi-hass-custom)  
> **Intended executor:** OpenAI Codex  
> **Plan baseline date:** 2026-07-31  
> **Execution model:** one bounded session per Codex invocation  
> **Canonical durable agent entry point:** `AGENTS.md` at the repository root

---

## 1. How to use this plan

Keep this file at the canonical repository path:

```text
plans/CODEX_FMI_HASS_MAINTENANCE_PLAN.md
```

For the first Codex session, use this prompt:

```text
Read plans/CODEX_FMI_HASS_MAINTENANCE_PLAN.md in full. Execute Session S00 only.
Follow the session protocol, update the session tracker in that file, create the
required handoff, and stop after S00 is complete. Do not start S01.
```

For every later session, use this prompt:

```text
Read AGENTS.md and plans/CODEX_FMI_HASS_MAINTENANCE_PLAN.md in full. Inspect git status,
the latest commits, and the previous session handoff. Execute exactly the next
session whose status is NOT_STARTED and whose prerequisites are DONE. Update the
tracker and write the required handoff. Do not start a later session.
```

To request a specific session:

```text
Read AGENTS.md and plans/CODEX_FMI_HASS_MAINTENANCE_PLAN.md in full. Execute Session SXX
only, provided that all of its prerequisites are DONE. Update the tracker and
write the required handoff. Do not perform work assigned to another session.
```

### Context-safety rule

Each session below is deliberately limited to one coherent engineering concern. Never combine sessions unless the repository owner explicitly asks for that. If a session unexpectedly expands beyond its stated concern:

1. Stop at a green, documented checkpoint that is ready for the repository owner to commit.
2. Add sub-rows such as `S08-A` and `S08-B` to the tracker.
3. Document the split and remaining work in the current handoff.
4. Mark the original session `IN_PROGRESS`, not `DONE`.
5. Continue in a new Codex invocation.

A session must not silently absorb unrelated cleanup, broad modernization, or work assigned to a later session.

---

## 2. Mission

Bring the fork to a state where it can be confidently used and maintained as a modern Home Assistant custom integration backed by Finnish Meteorological Institute data.

The work must:

1. Upgrade all runtime, development, test, and CI dependencies to the newest stable versions available at implementation time, subject only to demonstrated compatibility constraints.
2. Upgrade `fmi-weather-client` from the repository's current pin to its newest stable release and adapt the integration to its current API.
3. Add comprehensive automated tests for all critical behavior:
   - focused unit tests;
   - Home Assistant integration tests using Home Assistant's public setup/config-entry interfaces;
   - dependency contract tests;
   - opt-in live tests that call FMI's real Open Data API and verify the data exposed to Home Assistant.
4. Reproduce and resolve all currently known repository issues listed in this plan, including the two enhancement issues that are necessary for a complete maintenance release.
5. Review the open polar-day/polar-night pull request, adopt or reimplement the correct behavior, and add regression tests.
6. Perform an evidence-based audit for additional critical defects and fix every confirmed critical or high-severity defect discovered within the integration's existing feature set.
7. Build reliable CI for validation, tests, coverage, dependency/security checks, Home Assistant compatibility, HACS validation, and scheduled live FMI checks.
8. Create and finalize a concise root-level `AGENTS.md` as the durable entry point for all future coding agents and maintenance sessions.
9. Preserve user configurations, entity identities, automations, and dashboards wherever technically possible. Any unavoidable compatibility break must be explicitly documented and protected by migration logic where Home Assistant supports it.

---

## 3. Non-goals and scope boundaries

### 3.1 No refactoring for its own sake

Do not perform broad cleanup, stylistic rewrites, directory reshuffling, class renaming, architecture replacement, or abstraction work merely because the current code could look cleaner.

A refactor is allowed only when at least one of the following is true:

- it is required to fix a reproduced defect;
- it is required to support the current Home Assistant API;
- it is required to upgrade a dependency safely;
- it is required to make a critical behavior testable;
- it is required to isolate partial service failures correctly;
- it is required to preserve stable config-entry/entity identities during migration;
- it is required by current HACS or hassfest validation;
- it removes blocking synchronous I/O from the Home Assistant event loop;
- it removes a confirmed security, privacy, or reliability risk.

Every structural change must be explained in the session handoff with the issue, failing test, current API requirement, or CI rule that made it necessary.

### 3.2 Features outside this plan

Do not add unrelated weather products, custom Lovelace cards, maps, radar visualizations, alerts, new marine products, new external providers, or an official Home Assistant Core submission.

Do not fork or vendor `fmi-weather-client` by default. Prefer its newest stable release plus a narrow integration-side compatibility adapter. A library fork or vendored patch is permitted only if:

- a release-blocking defect is reproduced in the latest library;
- the defect cannot be safely isolated in the integration;
- the exact upstream issue and attempted solution are documented;
- the repository owner explicitly approves the fork/vendor approach.

### 3.3 Frontend scope

The integration does not need browser-level screenshot tests of Home Assistant's weather card. “Correct display” in this plan means that the integration exposes correct entity states, attributes, units, availability, and forecast data through Home Assistant APIs consumed by standard dashboards and cards.

---

## 4. Engineering constraints

### 4.1 Evidence before change

For every bug fix:

1. Reproduce the problem in a test or minimal diagnostic script.
2. Record the root cause.
3. Add a regression test that fails before the fix.
4. Implement the smallest reliable fix.
5. Run the relevant focused tests and the repository-wide offline suite.

Do not close a problem based only on code inspection when a deterministic test is possible.

### 4.2 Offline tests are the default

Normal unit and Home Assistant integration tests must not access the network. Block unexpected network access in the test suite. Use saved, sanitized public FMI fixtures and explicit mocks/fakes.

Only tests marked `live` may call external services. Live tests must never run as a required pull-request check.

### 4.3 Async and Home Assistant lifecycle correctness

- Do not block the Home Assistant event loop with synchronous network, geocoding, file, or CPU-heavy operations.
- Use current Home Assistant coordinator/config-entry/entity lifecycle patterns.
- Register and unregister listeners through the correct lifecycle hooks.
- Do not create duplicate coordinator listeners.
- Mark only the affected entities unavailable during partial outages.
- Recover automatically when a source becomes available again.
- Avoid repeated log spam: log a transition to unavailable and a transition back to available rather than the same expected failure every update.

### 4.4 Stable identity and migration safety

Coordinates and reverse-geocoded place names are mutable. They must not remain the sole long-term identity of a config entry or entity after location editing is implemented.

Any change to config-entry unique IDs, entity unique IDs, device identifiers, suggested object IDs, or entity naming must include migration tests from an actual v0.6.2-style entry/registry fixture.

Never blindly rename user-customized entity IDs. A registry migration may rename an old generated default only when the target is collision-free and the old value is demonstrably integration-generated. Preserve customized IDs.

### 4.5 Dependency policy

At the time each dependency session runs:

- determine the newest stable release from authoritative package/project sources;
- do not assume that versions mentioned in this plan are still latest;
- use prereleases only in a separate scheduled compatibility job;
- pin direct runtime requirements according to current Home Assistant custom-integration rules;
- maintain a reproducible development/test dependency lock;
- inspect the fully resolved transitive graph under the supported Home Assistant environment;
- do not copy every transitive dependency into `manifest.json` merely to pin it;
- remove unused or redundant direct requirements, especially packages already provided by Home Assistant Core, when current Home Assistant guidance supports removal;
- record dependency versions, licenses, compatibility decisions, and any justified exception.
- After the direct runtime and development/test dependencies have been upgraded to their selected newest stable versions, generate the repository-root `requirements.txt` from a clean supported development/test environment using `python -m pip freeze`. It must be a complete transitive freeze with exact versions, not a hand-maintained list of only direct dependencies.
- Keep the intended direct development/test dependencies in a separate human-maintained source such as `pyproject.toml` or an input requirements file. Treat `requirements.txt` as generated output: do not edit it manually, and regenerate it from a clean environment whenever a selected direct dependency changes.

A dependency may remain below newest stable only when the incompatibility is reproduced and documented with exact versions, traceback/test output, and an upstream reference or local compatibility analysis. Such a case is `BLOCKED` or an explicit owner-approved exception, not a silent pin.

### 4.6 Security and privacy

- Use least-privilege GitHub Actions permissions.
- Pin third-party actions to full immutable commit SHAs, with a comment identifying the corresponding release tag. If the reviewed commit has no corresponding tag, comment its upstream branch/date and record the latest available tag plus the reason it was not selected.
- Never expose secrets to pull requests from forks.
- Do not log exact user coordinates at normal log levels.
- Sanitize diagnostics and test artifacts.
- Do not add telemetry.
- Treat reverse geocoding as an optional external dependency; its failure must not disable core FMI weather data.
- Check runtime and development dependencies for known vulnerabilities.

### 4.7 Living-plan and owner-controlled Git rules

- Treat this plan as a living project record. As soon as verified evidence shows an inaccuracy, a mismatch with the real repository/code, or a necessary scope expansion, update the affected plan text, tracker, issue matrix, or session specification immediately. Do not defer a known correction until session end.
- Record every material plan correction or scope expansion in the current handoff. A scope expansion must still obey the context-safety rule and may require explicit sub-sessions; editing the plan does not authorize silently absorbing unrelated work.
- Do not run any Git operation that may require a hardware token, interactive credential prompt, or authenticated SSH access. Use local read-only Git commands and anonymous public HTTPS/API access for remote inspection. Do not contact a credentialed remote unless the repository owner explicitly performs or authorizes that exact operation.
- Codex must not create commits. The repository owner owns all commits. At session end, leave a reviewed working tree and provide exactly one concise suggested commit message beginning with `SXX:`.
- While the owner-controlled commit is pending, use `OWNER_TO_COMMIT` in commit fields. A session may be marked `DONE` when all non-commit acceptance criteria pass, its handoff is complete, and the suggested commit message is recorded. A later session should replace `OWNER_TO_COMMIT` with the owner's resulting SHA when it is available.
- Use rootless Podman containers for all local commands that require the project's supported Python or Home Assistant version. Pin the container base image, run repository commands through the documented Podman entry point, and do not silently fall back to the host Python. Host tools may be used only for version discovery or checks that do not depend on the supported Python environment.

---

## 5. Baseline snapshot to verify in S00

This is a planning snapshot, not a substitute for inspecting the fork at execution time.

As of 2026-07-31, upstream appears to have the following characteristics:

- integration version: `0.6.2`;
- code stored in the repository root and installed by HACS using `"content_in_root": true`;
- runtime requirements in `manifest.json`:
  - `fmi-weather-client==0.7.0`;
  - `geopy>=2.1.0`;
- basic CI only:
  - Python 3.12 and 3.13;
  - `flake8`;
  - `pylint`;
  - no pytest suite, coverage gate, Home Assistant setup test, hassfest job, HACS validator, dependency audit, or live FMI job;
- latest known `fmi-weather-client` release at plan authoring time: `1.0.0`; the executing agent must check again;
- six open issues and one open pull request, listed below.

S00 must refresh this snapshot against:

- the fork's actual default branch and commit history;
- current upstream open and recently closed issues;
- current open pull requests;
- current Home Assistant stable and beta releases;
- current Home Assistant Python requirement;
- current HACS and hassfest rules;
- current `fmi-weather-client` release and API;
- current FMI Open Data documentation and service limits;
- whether Home Assistant Core has introduced an official integration using the `fmi` domain.

If an official Core integration now owns the same domain, stop and mark the plan `BLOCKED` pending an explicit migration/domain decision.

### S00 verified refresh (2026-07-31)

- Local `master`, `origin/master` for `kogeler/fmi-hass-custom`, and upstream `anand-p-r/fmi-hass-custom` `master` all resolve to `77a265cf910050aa6e2e37a4eb57d951bddc2910`; the fork has no commits absent upstream.
- Upstream still has six open issues (`#110`, `#111`, `#112`, `#114`, `#115`, and `#117`) and one open pull request (`#116`); the closure matrix below remains current.
- Latest Home Assistant stable is `2026.7.4`; latest beta is `2026.8.0b2`; both the stable and development source declare Python `>=3.14.2`.
- Latest stable `fmi-weather-client` remains `1.0.0`, requires Python `>=3.10`, and publishes Python 3.10 through 3.14 classifiers.
- Home Assistant Core's `dev` tree contains no `homeassistant/components/fmi` integration, so no domain conflict blocks this plan.
- HACS documentation still explicitly permits a root-content integration when `hacs.json` sets `"content_in_root": true`; hassfest/HACS execution against this repository remains assigned to S01.
- Full evidence, dependency versions, command results, and authoritative source links are recorded in `docs/maintenance/BASELINE.md`.

---

## 6. Known issue and pull-request closure matrix

The status, test, and commit fields in this table are living project records and must be updated by Codex.

| Reference | Classification | Required outcome | Owning session | Regression test | Fix commit | Status | Notes |
|---|---|---|---|---|---|---|---|
| [#110](https://github.com/anand-p-r/fmi-hass-custom/issues/110) Lightning max age | Enhancement/reliability | Add a user-configurable maximum strike age; discard older items safely; preserve a documented backward-compatible default | S09 | TBD | TBD | NOT_STARTED | Test exact boundary, timezone-aware timestamps, missing/malformed timestamps, and option migration |
| [#111](https://github.com/anand-p-r/fmi-hass-custom/issues/111) Wind gust unavailable | Regression | Restore a correctly typed and available wind-gust sensor when FMI provides valid gust data; do not invent a value when data is absent | S06 | `tests/test_fmi_contract.py::test_current_client_maps_three_second_wind_gust_field`; `tests/test_forecast_characterization.py::test_wind_gust_sensor_uses_current_client_field` | TBD | CHARACTERIZED | Client 0.7.0 maps `WindGust` to `WeatherData.wind_gust` in m/s; `wind_max` is unsupported and `None`. S06 must reproduce the full Home Assistant issue before fixing it. |
| [#112](https://github.com/anand-p-r/fmi-hass-custom/issues/112) Sensors not grouped/named by location | Regression | Restore location-aware grouping and appropriate generated names for new entities while preserving customized/existing IDs through safe migration | S06/S11 | TBD | TBD | NOT_STARTED | Include collision and customized-ID cases |
| [#114](https://github.com/anand-p-r/fmi-hass-custom/issues/114) Incorrect daily forecast | Correctness | Replace first-sample-of-day behavior with documented, deterministic daily aggregation, including summing hourly precipitation amounts | S05 | `tests/test_forecast_characterization.py` | `OWNER_TO_COMMIT` | IMPLEMENTED | The former strict xfail now passes. Hourly/daily schema, local-date/DST grouping, precipitation, temperature, condition, wind, averages, missing values, partial days, ordering, duplicates, and HA subscriber exposure are covered; policy is in `docs/maintenance/FORECAST_SEMANTICS.md`. Mark `DONE` after owner commit and CI. |
| [#115](https://github.com/anand-p-r/fmi-hass-custom/issues/115) Location selection/editing | User-facing maintenance | Add a current Home Assistant reconfigure flow that updates an existing entry's coordinates without forcing users to rebuild automations | S07/S11 | TBD | TBD | NOT_STARTED | Dynamic tracking of the Home zone is optional; safe coordinate editing is mandatory |
| [#117](https://github.com/anand-p-r/fmi-hass-custom/issues/117) Forecast failure disables observations | Availability | Degrade gracefully: observations/current conditions remain usable when forecast WFS fails; forecast entities/data show unavailable/empty appropriately and recover automatically | S04 | `tests/test_availability.py` | `ad0c997ea70f2316195808347501de4b4e8f58ea` | IMPLEMENTED | Setup/retry, fallback, stale-data, recovery, lifecycle, listener, and log-transition policy is documented in `docs/maintenance/AVAILABILITY.md` and covered offline. Mark `DONE` after CI passes. |
| [PR #116](https://github.com/anand-p-r/fmi-hass-custom/pull/116) `None` sunrise/sunset near poles | Correctness | Review, adopt or reimplement the guard; add deterministic polar-day and polar-night tests | S08 | `tests/test_forecast_characterization.py::test_clear_condition_handles_missing_polar_sun_events` (`strict xfail`) | TBD | REPRODUCED | Synthetic high-latitude fixture deterministically reproduces the `None.astimezone` failure. Convert the strict xfail in S08. |
| New issues discovered after 2026-07-31 | Triage | Classify all new open issues; fix any critical/high correctness, availability, migration, security, or compatibility defect in this maintenance effort | S00/S13 | TBD | TBD | NOT_STARTED | Add rows rather than hiding new scope |

### Closure policy

- Bugs and regressions in the matrix must be fixed.
- #110 and #115 are included as required deliverables, not optional backlog items.
- A row may be marked `BLOCKED` only with reproducible evidence of an external limitation or a decision that genuinely requires the repository owner.
- Do not mark a row `DONE` until its regression test passes in CI and the fix commit is recorded.
- Do not use `SKIPPED` without explicit written approval from the repository owner.

---

## 7. Candidate critical risks to investigate

The following are audit hypotheses based on the upstream code snapshot. They are not permission for speculative rewrites. Confirm each with current code and a test or concrete execution trace before changing behavior.

1. Forecast initialization may be coupled to the whole config-entry setup, causing observations to be lost during forecast-only failures.
2. A failed refresh may leave stale forecast/current data looking fresh instead of explicitly tracking source success and availability.
3. Observation fetches returning `None` may be treated as successful refreshes.
4. Daily grouping may compare only day-of-month values instead of full local calendar dates, which can fail across month/year boundaries.
5. “Best time of day” next-day logic may use arithmetic on `day` fields and fail at month/year boundaries.
6. Missing, `None`, NaN, or unexpected numeric types from FMI may raise exceptions during entity value conversion or daily aggregation.
7. High-latitude sunrise/sunset lookups may return `None`.
8. Wind-gust data may use a different field in current `fmi-weather-client` models than the sensor code expects.
9. Manual coordinator listeners may duplicate the lifecycle already handled by `CoordinatorEntity` or may not be removed correctly.
10. Auxiliary lightning or sea-level HTTP/parsing/geocoding failures may incorrectly fail the core weather refresh.
11. Auxiliary HTTP requests may not check status codes, apply bounded timeouts, or distinguish malformed/error responses.
12. Lightning timeout/age calculations may mix seconds and milliseconds.
13. Lightning response arrays may be assumed to have identical lengths without validation.
14. Reverse geocoding every strike may create avoidable rate-limit, privacy, latency, or availability problems.
15. Integration code may call `logging.basicConfig`, changing global Home Assistant logging behavior.
16. Legacy Home Assistant weather/sensor properties or forecast APIs may be deprecated or semantically incorrect on current Home Assistant.
17. Supported forecast feature flags may not match the actual hourly/daily methods exposed by each entity.
18. Coordinates embedded in config-entry/entity unique IDs may make safe reconfiguration impossible without registry migration.
19. Exact coordinates may appear in logs, diagnostics, or CI artifacts.
20. The repository's runtime/development requirements may contain unused, redundant, unbounded, or vulnerable packages.

Confirmed critical/high defects belong in S13. Medium/low observations may be documented for a later maintenance plan unless they are trivial and directly adjacent to an in-scope fix.

---

## 8. Required test architecture

The exact paths may follow the final repository layout, but the resulting suite must provide these layers.

### 8.1 Unit tests

Cover pure or narrowly isolated behavior such as:

- weather-code mapping;
- robust extraction of optional numeric values;
- hourly-to-daily aggregation;
- local-date grouping;
- condition selection policy;
- precipitation accumulation;
- wind-gust extraction;
- strike age filtering;
- timezone/DST handling;
- polar sunrise/sunset behavior;
- options/default migration helpers;
- error classification.

### 8.2 Dependency contract tests

Create a narrow adapter boundary around `fmi-weather-client` only if necessary. Contract tests must verify the exact objects/fields/types used by the integration against the installed newest stable client.

Contract tests must catch future changes to:

- forecast and observation call signatures;
- synchronous versus asynchronous APIs;
- forecast collection shape;
- timestamp timezone awareness;
- temperature, precipitation, wind, gust, pressure, humidity, cloud, and symbol fields;
- exceptions raised for client/server/parse failures;
- `None`/empty result behavior.

These tests are offline unless explicitly marked `live`.

### 8.3 Home Assistant integration tests

Use Home Assistant's public interfaces, especially config-entry setup, instead of testing only internal classes.

At minimum, test:

- initial config flow success and all meaningful errors;
- duplicate entry prevention;
- options flow;
- reconfigure flow;
- setup, first refresh, unload, reload, and removal lifecycle;
- multiple entries;
- forecast-only failure, observation-only failure, auxiliary-source failure, and recovery;
- entity creation, availability, state, units, attributes, and device/entity registry data;
- hourly and daily forecast APIs used by Home Assistant;
- observation station behavior;
- migration from v0.6.2-style config entries/options/entity registries;
- coordinate changes without breaking stable entity identity;
- generated versus user-customized entity IDs;
- collisions during proposed renames;
- absence of unexpected network traffic.

### 8.4 Live FMI tests

Live tests must exercise the complete path from the installed integration/client to real FMI endpoints and back into Home Assistant entity/forecast state.

Requirements:

- use `pytest` marker `live` or an equally explicit marker;
- excluded from the default offline test command;
- run only by manual dispatch and a modest schedule on the default branch;
- use public, documented test locations, never the owner's home coordinates;
- cover at least:
  - a southern Finnish location;
  - a northern/high-latitude Finnish location;
  - a known observation station discovered from current FMI metadata;
- assert invariants, not exact weather values;
- verify timezone-aware, monotonically ordered forecast timestamps;
- verify that at least one usable forecast/current/observation field is exposed when FMI returns data;
- verify units and broad physically plausible ranges only for fields that are present;
- compare the integration's live daily precipitation result with the sum of the corresponding live hourly `PrecipitationAmount1h`-derived values, using the documented local-day rules;
- verify that Home Assistant receives the same semantic values that dashboards consume;
- use bounded request timeouts and a small, bounded retry policy;
- report whether failure appears to be transport/service availability, upstream contract drift, parsing, or Home Assistant exposure;
- never use `continue-on-error`; scheduled failures must be visible, but they must not block pull requests;
- stay far below FMI request limits and document current limits/licensing in `docs/maintenance/LIVE_TESTS.md`.

### 8.5 Coverage target

By final verification:

- all integration modules: at least 95% line coverage;
- critical modules (`config_flow`, setup/coordinators, weather, sensors, migrations, parsing/aggregation utilities): at least 95% line coverage and at least 90% branch coverage;
- config/reconfigure/options flows: every meaningful branch covered;
- every fixed issue: at least one explicit regression test whose name or comment references the issue number;
- no decrease in coverage in future pull requests.

Generated translations, fixture data, and deliberately unreachable defensive assertions may be excluded only with a documented reason. Do not game coverage with blanket pragmas or tests that merely execute lines without checking behavior.

### 8.6 Type-check debt burn-down

At the end of S04, `make type-check` reports the verified inherited baseline of 18 errors in four production files. This is temporary tracked debt, not an accepted final state. Resolve it alongside the sessions that already own the affected behavior so annotations follow the final implementation rather than code that will immediately be replaced:

| Owning session | File/area | S04 baseline | Required result |
|---|---|---:|---|
| S05 | `custom_components/fmi/weather.py` and Home Assistant forecast/coordinator contracts | 4 | Zero errors in this file; repository total no greater than 14 |
| S06 | `custom_components/fmi/sensor.py` and heterogeneous sensor/coordinator contracts | 7 | Zero errors in this file; repository total no greater than 7 |
| S08 | `custom_components/fmi/utils.py`, including optional sun events and the `const` name collision | 3 | Zero errors in this file; repository total no greater than 4 |
| S09 | `custom_components/fmi/__init__.py` lightning/sea-level parser structures | 4 | Zero repository errors; `make type-check` passes |
| S14 | Full supported-environment compatibility audit | 0 expected | Confirm the zero baseline and fix any newly discovered real integration error without broad ignores |

The counts are checkpoints, not permission to trade one error for another. If edits move a diagnostic to another line or module, ownership follows the behavior in this table. Every intervening session must run `make type-check`, must not increase either the repository total or the errors outside its owned area, and must not use broad ignores, exclude production files, or weaken mypy configuration to satisfy a checkpoint.

---

## 9. CI and repository quality target

The final repository must provide fast required pull-request checks and separate scheduled compatibility/live checks.

### Required on pull request and default-branch push

- dependency installation from a reproducible environment;
- formatting check;
- lint/static correctness check;
- one real type-checking job appropriate for the current Home Assistant ecosystem;
- offline unit tests;
- Home Assistant integration tests;
- coverage thresholds;
- manifest/import/install/setup smoke test;
- hassfest validation;
- HACS repository validation;
- dependency vulnerability review/audit;
- GitHub Actions syntax/security linting;
- verification that ordinary tests made no external network calls.

### Scheduled/manual checks

- latest Home Assistant stable against the locked supported dependency set;
- current Home Assistant beta/prerelease as an early warning, clearly separated from the release gate;
- newest compatible dependency resolution check;
- live FMI end-to-end tests;
- optional check for newly opened upstream issues, FMI changelog changes, and dependency releases, if it can be implemented without credentials or noisy automation.

### Workflow security and behavior

- default `GITHUB_TOKEN` permissions should be read-only;
- grant a narrower write permission only in a job that demonstrably needs it;
- do not use `pull_request_target` to execute untrusted fork code;
- pin external actions by full commit SHA;
- add concurrency cancellation for superseded pull-request runs;
- set job timeouts;
- cache safely without making correctness depend on cache state;
- upload useful, sanitized test/coverage/live diagnostics;
- use Dependabot or an equivalent repository-native updater for both Python and GitHub Actions dependencies;
- do not auto-merge dependency updates unless separately approved by the owner.

---

## 10. Session tracker

Allowed status values:

- `NOT_STARTED`
- `IN_PROGRESS`
- `BLOCKED`
- `DONE`
- `SUPERSEDED` (only when replaced by explicitly recorded sub-sessions)

A session is not `DONE` unless its acceptance criteria pass, its handoff exists, and either the owner's commit SHA or `OWNER_TO_COMMIT` plus the suggested commit message is recorded.

| ID | Session | Prerequisites | Status | Started UTC | Completed UTC | Commit(s) | Handoff / notes |
|---|---|---|---|---|---|---|---|
| S00 | Bootstrap, refresh baseline, and create initial `AGENTS.md` | None | DONE | 2026-07-31T06:44:16Z | 2026-07-31T06:55:14Z | `389c67901085efe6b53bee1474a2f89bfab20867` | `docs/agent-handoffs/S00.md` |
| S01 | Reproducible development/test environment and validation skeleton | S00 | DONE | 2026-07-31T06:59:13Z | 2026-07-31T08:09:34Z | `b4fb80808884cdd746714829d1616c4160b94c91` | `docs/agent-handoffs/S01.md`; committed with S02 |
| S02 | FMI fixture corpus, contract boundary, and characterization tests | S01 | DONE | 2026-07-31T08:10:37Z | 2026-07-31T08:34:20Z | `b4fb80808884cdd746714829d1616c4160b94c91` | `docs/agent-handoffs/S02.md`; committed with S01 |
| S03 | Upgrade all dependencies and adapt to newest stable FMI client | S02 | DONE | 2026-07-31T09:41:16Z | 2026-07-31T10:24:24Z | `eb073830b03b80922d607c855f5b4e440d10e217` | `docs/agent-handoffs/S03.md`; temporary HA-pinned vulnerability exception tracked in `TODO.md` |
| S04 | Coordinator/setup resilience and issue #117 | S03 | DONE | 2026-07-31T10:36:22Z | 2026-07-31T11:02:16Z | `ad0c997ea70f2316195808347501de4b4e8f58ea` | `docs/agent-handoffs/S04.md` |
| S05 | Correct hourly/daily forecast semantics and issue #114 | S04 | DONE | 2026-07-31T11:23:32Z | 2026-07-31T12:04:36Z | `OWNER_TO_COMMIT` | `docs/agent-handoffs/S05.md` |
| S06 | Sensor/entity correctness and issues #111/#112 | S05 | NOT_STARTED | — | — | — | `docs/agent-handoffs/S06.md` |
| S07 | Location reconfigure flow and issue #115 | S06 | NOT_STARTED | — | — | — | `docs/agent-handoffs/S07.md` |
| S08 | Polar sun, time boundaries, and missing-data robustness; PR #116 | S07 | NOT_STARTED | — | — | — | `docs/agent-handoffs/S08.md` |
| S09 | Lightning/sea-level hardening and issue #110 | S08 | NOT_STARTED | — | — | — | `docs/agent-handoffs/S09.md` |
| S10 | Full Home Assistant config/lifecycle integration tests | S09 | NOT_STARTED | — | — | — | `docs/agent-handoffs/S10.md` |
| S11 | Registry migration, stable identity, and multi-entry tests | S10 | NOT_STARTED | — | — | — | `docs/agent-handoffs/S11.md` |
| S12 | Live FMI end-to-end test suite and scheduled probe | S11 | NOT_STARTED | — | — | — | `docs/agent-handoffs/S12.md` |
| S13 | Evidence-based critical runtime correctness audit and fixes | S12 | NOT_STARTED | — | — | — | `docs/agent-handoffs/S13.md` |
| S14 | Home Assistant compatibility, dependency, security, and privacy audit | S13 | NOT_STARTED | — | — | — | `docs/agent-handoffs/S14.md` |
| S15 | Production CI/CD, HACS validation, and release verification | S14 | NOT_STARTED | — | — | — | `docs/agent-handoffs/S15.md` |
| S16 | Documentation, final verification, and final `AGENTS.md` | S15 | NOT_STARTED | — | — | — | `docs/agent-handoffs/S16.md` |

---

## 11. Standard session protocol

Every session must follow this protocol.

### 11.1 Start of session

1. Read the applicable `AGENTS.md` instruction chain and this plan.
2. Read the previous session handoff.
3. Run:

   ```bash
   git status --short --branch
   git log --oneline --decorate -n 12
   ```

4. Do not overwrite, delete, reset, stash, or reformat unexplained user changes.
5. Confirm that prerequisite sessions are `DONE` and their handoffs are present. Record an owner-created commit SHA when available; `OWNER_TO_COMMIT` is acceptable under Section 4.7.
6. Change the current tracker row from `NOT_STARTED` to `IN_PROGRESS` and set `Started UTC`.
7. State the bounded objective in the session handoff draft.
8. Run the fastest relevant baseline check before editing.

### 11.2 During session

- Stay inside the listed scope.
- Prefer a failing regression test before the production change.
- Keep each session's working-tree diff logically coherent for the owner's commit.
- Correct this plan immediately when verified evidence reveals an inaccuracy, repository/code mismatch, or necessary scope expansion.
- Update root `CHANGELOG.md` in every session that introduces a significant user-visible, release-level, compatibility, security, or major maintenance change. Record only notable outcomes; do not turn the changelog into a list of minor edits, internal mechanics, or every touched file.
- Do not change public behavior without a test and documentation.
- Do not silently suppress exceptions, linters, type errors, or test failures.
- Follow the type-check burn-down in Section 8.6: run `make type-check` after production changes, do not increase the current checkpoint, and resolve the errors owned by the current session.
- Do not weaken an assertion simply to make a test pass.
- Do not make live network tests part of the ordinary suite.
- When external documentation is needed, use authoritative sources and record the URL and access date in the relevant maintenance document.

### 11.3 End of session

1. Run every verification command listed for the session.
2. Run the repository's standard fast offline suite.
3. Review the diff for unrelated changes:

   ```bash
   git diff --check
   git status --short
   ```

4. Update relevant issue/decision tables in this plan.
5. Write `docs/agent-handoffs/SXX.md` using the template in Section 13.
6. Do not create a commit. Add one concise suggested commit message beginning with `SXX:` to the handoff and report it to the repository owner.
7. Record `OWNER_TO_COMMIT`, the completion time, and the handoff path in the tracker. Replace it with the owner-created SHA in a later session when known.
8. Mark the session `DONE` only when all exit criteria pass.
9. Stop. Do not begin the next session.

Do not push, open pull requests, publish releases, close upstream issues, or create tags unless the repository owner explicitly requests it.

---

# 12. Detailed session specifications

## Session S00 — Bootstrap, refresh baseline, and create initial `AGENTS.md`

### Objective

Create durable project memory and replace planning assumptions with a verified repository baseline. Make no functional production-code changes.

### Required work

1. Inspect the fork, upstream repository, default branch, tags, recent commits, open issues, recently closed issues likely related to regressions, and open pull requests.
2. Record the exact base commit and upstream relationship.
3. Verify whether the fork contains changes not present in upstream.
4. Verify current versions and requirements from authoritative sources:
   - latest Home Assistant stable and beta;
   - Home Assistant's current Python version/support policy;
   - current Home Assistant custom-integration testing guidance;
   - current HACS validation/repository rules;
   - current hassfest action guidance;
   - latest stable `fmi-weather-client` and its supported Python versions/API;
   - latest direct development/test dependencies already used by the repo;
   - current FMI Open Data WFS documentation, terms, limits, and changelog.
5. Check whether Home Assistant Core now contains an official integration with domain `fmi`.
6. Create `docs/maintenance/BASELINE.md` containing:
   - base commit and date;
   - repository tree and approximate module responsibilities;
   - current install layout;
   - current dependencies and CI;
   - refreshed issue/PR inventory;
   - current support assumptions;
   - commands that currently work or fail;
   - known gaps and risks;
   - authoritative source links with access dates.
7. Create `docs/agent-handoffs/`.
8. Create an initial root-level **uppercase** `AGENTS.md`. Codex automatically discovers `AGENTS.md`; do not use lowercase `agents.md` as the primary file on a case-sensitive filesystem.
9. Keep initial `AGENTS.md` concise and include:
   - project purpose;
   - instruction to read this plan and the latest handoff;
   - no-refactoring-for-its-own-sake rule;
   - no-network-by-default testing rule;
   - git/user-change safety rules;
   - known command placeholders marked `TBD` where S01 has not established them;
   - handoff/tracker protocol;
   - prohibition on claiming unrun checks passed.
10. Update the baseline and known-issue tables in this plan if upstream changed.

### Verification

- Confirm `AGENTS.md` is nonempty, under Codex's project instruction size limit, and located at the Git root.
- Confirm all links and issue numbers in `BASELINE.md` are current.
- Run the existing repository validation commands without changing their configuration; record success/failure exactly.
- Run `git diff --check`.

### Exit criteria

- Verified baseline is complete and ready for the repository owner to commit.
- Initial `AGENTS.md` is complete and ready for the repository owner to commit.
- Tracker and issue matrix reflect current reality.
- No production behavior changed.
- If a Core `fmi` domain conflict exists, mark S00 `BLOCKED` with evidence and stop.

### Do not do

- Do not upgrade packages.
- Do not move files.
- Do not fix issues.
- Do not replace existing lint configuration yet.

---

## Session S01 — Reproducible development/test environment and validation skeleton

### Objective

Create a reproducible local developer environment and the smallest useful automated test/validation skeleton without changing runtime behavior.

### Required work

1. Use rootless Podman as the mandatory local execution environment for the current supported Python/Home Assistant version. Pin the base image, provide a simple repository command that builds/runs it, and document why the selected dependency/locking approach fits this standalone repository. Do not use the host Python as a fallback for project checks.
2. Separate concerns clearly:
   - runtime requirements installed by Home Assistant from `manifest.json`;
   - development/test tooling;
   - reproducible lock/resolution for local and CI testing;
   - a human-maintained direct dependency source and a complete generated root `requirements.txt` freeze, as required by Section 4.5.
3. Determine the repository layout strategy:
   - first test whether the current root layout plus `content_in_root` remains supported by current HACS and hassfest;
   - retain it if fully supported and not materially blocking reliable imports/tests;
   - migrate to `custom_components/fmi/` only if current validation/tooling requires it or the test harness would otherwise rely on fragile import hacks;
   - if a layout migration is necessary, isolate it in a behavior-neutral commit and add an installation-layout smoke test.
4. Add a modern `pyproject.toml` or equivalent single source of configuration for:
   - pytest;
   - coverage;
   - formatting/linting;
   - test markers, including `live`;
   - selected type checker;
   - development dependency groups.
5. Use the current recommended Home Assistant custom-component pytest support package or equivalent. Verify that it matches the target Home Assistant release.
6. Add a minimal Home Assistant setup smoke test using a mocked FMI client and a mock config entry.
7. Add a mechanism that fails ordinary tests on unexpected network access.
8. Establish stable developer commands. They may be scripts, a `Makefile`, or direct package-manager commands, but they must be simple and documented. Required logical commands:
   - environment setup/sync;
   - format;
   - lint;
   - type check;
   - fast offline tests;
   - full offline tests with coverage;
   - validations;
   - live tests.
9. Add a minimal PR CI skeleton that runs the setup smoke test and basic validation. S15 will harden/finalize CI.
10. Replace `TBD` command placeholders in `AGENTS.md` with the commands established here.
11. Use Ruff as the sole flake8-style linter and formatter:
   - remove active flake8 dependencies, configuration, CI, and developer commands;
   - configure a documented Ruff rule set rather than preserving only the former flake8 fatal-error subset;
   - apply Ruff formatting and safe fixes to the repository;
   - make both `make format-check` and `make lint` pass;
   - retain factual flake8 references only in historical S00/baseline evidence.
12. Store this maintenance plan at `plans/CODEX_FMI_HASS_MAINTENANCE_PLAN.md` and update every active repository reference to its canonical path.

### Verification

- Create a clean environment from repository files only.
- Install/sync dependencies successfully.
- Run the setup smoke test.
- Run the initial formatter/linter/type-check command, recording any pre-existing failures rather than masking them.
- Verify Ruff format and lint checks pass with no active flake8 configuration, dependency, or command remaining.
- Run hassfest locally against the chosen layout. Add the official HACS validation job to preliminary CI and verify it after the owner creates the session commit; the HACS action validates a GitHub ref through the GitHub API and cannot validate an uncommitted local tree anonymously. Do not request or use an owner token merely to bypass that limitation.
- Verify ordinary tests fail if a test tries to access the network unexpectedly.

### Exit criteria

- One documented command can create/sync the development environment.
- One documented command runs the offline tests.
- Home Assistant can load a mocked config entry in a test.
- The repository layout has a documented, evidence-based decision.
- Ruff is the only active flake8-style lint/format tool, and both Ruff gates pass.
- The plan lives under `plans/` and active links point to its canonical path.
- No intentional runtime behavior change.

---

## Session S02 — FMI fixture corpus, contract boundary, and characterization tests

### Objective

Build an offline data corpus and characterize critical current behavior before the dependency upgrade and bug fixes.

### Required work

1. Inspect how the installed current `fmi-weather-client` represents:
   - current weather;
   - forecast collections;
   - observations;
   - missing values;
   - timestamps;
   - wind gusts;
   - exceptions.
2. Create a narrow client boundary/fake only where it improves testability or shields the integration from an external model API. Do not redesign the whole integration.
3. Create sanitized, compact fixtures representing:
   - a normal hourly forecast across at least three local dates;
   - a month boundary and a year boundary;
   - a DST transition relevant to Europe/Helsinki;
   - precipitation beginning after the first forecast sample of a day;
   - missing/NaN values;
   - empty forecast and empty observation results;
   - observation-station data;
   - wind gust data using the actual current-client field shape;
   - forecast/client/server/parse errors;
   - lightning and sea-level success/error payloads used by existing features;
   - a high-latitude sunrise/sunset case.
4. When fixtures contain FMI public data, add attribution and capture metadata required by the current FMI data license. Do not include the owner's coordinates.
5. Add characterization tests for current public entity behavior, but do not encode known incorrect behavior as permanently passing expectations.
6. Represent known defects using strict `xfail` tests or clearly failing branch-specific tests tied to issue numbers. A strict `xfail` must be converted to a normal passing test in the owning fix session.
7. Add offline dependency contract tests for exactly the fields/methods the integration consumes.
8. Ensure fixture-building helpers are deterministic and do not call the network during ordinary test collection.

### Verification

- Full offline suite passes with only explicitly documented strict `xfail` cases for known issues.
- An unexpected contract shape fails with a useful message.
- Fixtures contain no secrets or private coordinates.
- All fixture files are small enough to review.

### Exit criteria

- Reusable fixture corpus committed.
- Known problems are reproducible without live network access.
- Contract tests provide a safety net for S03.
- No known bug is accidentally “accepted” as correct behavior.

---

## Session S03 — Upgrade all dependencies and adapt to newest stable FMI client

### Objective

Upgrade runtime, development, test, and existing CI dependencies to their newest stable releases available during this session, with a reproducible resolved graph.

### Required work

1. Produce `docs/maintenance/DEPENDENCIES.md` with a table containing:
   - dependency/action name;
   - purpose;
   - direct or transitive classification;
   - old version/constraint;
   - newest stable version found;
   - selected version;
   - license;
   - source URL and access date;
   - compatibility notes;
   - reason for any exception.
2. Upgrade `fmi-weather-client` to the newest stable release. Do not assume `1.0.0` is still latest.
3. Inspect its changelog/source/public API and adapt only the integration boundary required for compatibility.
4. Upgrade all direct development/test tools and existing GitHub Actions dependencies to newest stable releases.
5. Resolve and lock transitive development/test dependencies using the chosen environment tool.
6. After selecting the newest stable direct dependencies, create a clean supported environment, install the selected development/test dependency set, and regenerate the root `requirements.txt` with `python -m pip freeze`. Verify that every installed transitive dependency is present with an exact version and that no unrelated package leaked in from the executor's global environment.
7. Inspect the runtime graph as Home Assistant resolves it. Do not redundantly add Home Assistant Core dependencies to the manifest.
8. Remove unused or duplicate requirements only after proving they are unused and current Home Assistant supplies any needed shared package.
9. Use exact production requirement pins when current Home Assistant custom-integration rules require them.
10. Update the Python support matrix to match current Home Assistant, not an arbitrary set of Python versions.
11. Run dependency vulnerability and license inventory checks.
12. Convert any compatibility-related strict `xfail` test to passing behavior.
13. If newest stable cannot be used:
    - add a test reproducing the incompatibility;
    - document exact versions and output;
    - search/file/reference an upstream issue;
    - mark S03 `BLOCKED` or request an owner-approved exception.

### Verification

- Clean environment sync from the lock succeeds.
- Recreating the environment from the direct dependency source produces the committed `requirements.txt` exactly via `python -m pip freeze`.
- All offline characterization/contract tests pass except issue-specific `xfail` tests assigned to later sessions.
- Home Assistant setup smoke test passes with upgraded dependencies.
- `pip-audit` or the selected equivalent reports no unaddressed critical/high vulnerability in the resolved supported environment.
- Manifest/HACS/hassfest validation passes.
- No package remains outdated without a documented reason.

### Exit criteria

- Newest stable FMI client is in use or a demonstrated blocker is recorded.
- Direct and transitive dependency state is reproducible and documented.
- Runtime behavior changes are limited to required compatibility adaptations.

---

## Session S04 — Coordinator/setup resilience and issue #117

### Objective

Make forecast and observation availability independent enough that a forecast WFS incident does not unnecessarily disable usable current observations.

### Required work

1. Reproduce #117 using offline fixtures/exceptions.
2. Define and document the source availability policy:
   - which data is required for initial entry setup;
   - what current conditions use when forecast data is unavailable;
   - how forecast unavailability is represented;
   - how observation unavailability is represented;
   - when a full config entry must enter retry;
   - how recovery occurs.
3. Refactor setup/coordinator boundaries only as needed so forecast, observation, and optional sources do not share an all-or-nothing failure path.
4. Ensure a valid observation response can keep current weather/sensor entities available when forecast fetching fails.
5. Ensure forecast output is unavailable/empty rather than stale-looking when freshness cannot be guaranteed. If retaining stale data is preferable for a specific entity, expose age/freshness and document the policy.
6. Treat `None`/empty client results as explicit failures or no-data states, not successful refreshes.
7. Ensure automatic recovery on a later successful refresh without requiring a restart/reload.
8. Ensure expected repeated outages do not flood logs.
9. Remove duplicate/manual coordinator listeners only if they are confirmed to cause lifecycle or update problems; cover listener registration/removal in tests.
10. Add a failing offline reproduction for #117, then make it a normal passing regression test. S02 did not add a #117 strict `xfail`; do not claim one exists.

### Required tests

- forecast fails, observation succeeds at initial setup;
- forecast succeeds, observation fails;
- both fail at initial setup;
- forecast fails after prior success;
- source recovers on next refresh;
- stale data/availability semantics;
- unload/reload during a partial outage;
- no duplicate update callbacks;
- log transition behavior where practical.

### Exit criteria

- #117 behavior is fixed and tested.
- Partial service failure affects only dependent data.
- Setup/retry behavior is explicit and documented.
- Full offline suite passes.

---

## Session S05 — Correct hourly/daily forecast semantics and issue #114

### Objective

Make hourly and daily forecasts semantically correct, deterministic, timezone-aware, and compatible with current Home Assistant weather APIs.

### Required work

1. Read current FMI parameter documentation and the current `fmi-weather-client` model definitions for every forecast field used.
2. Read current Home Assistant `WeatherEntity` forecast schema and service/method requirements.
3. Create `docs/maintenance/FORECAST_SEMANTICS.md` documenting the selected aggregation policy and supporting sources.
4. Replace grouping by partial date fields with full timezone-aware local calendar dates.
5. At minimum, implement and test:
   - daily high temperature = maximum valid hourly temperature;
   - daily low temperature = minimum valid hourly temperature;
   - daily precipitation amount = sum of valid one-hour precipitation amounts for that local day;
   - `None` precipitation when no valid precipitation sample exists, rather than fabricated zero unless FMI semantics justify zero;
   - deterministic daily wind speed/gust policy based on valid samples;
   - deterministic wind-bearing policy associated with the chosen wind aggregate or a documented vector method;
   - deterministic condition policy that does not simply copy the first sample of the day;
   - explicit policy for humidity, pressure, cloud coverage, and any field that Home Assistant permits in daily forecasts;
   - correct daily timestamp representation;
   - partial first/last day behavior.
6. The condition policy must be explainable and tested. Prefer a documented severity/representativeness algorithm based on available FMI symbols. Do not invent meteorological probability data that the API does not provide.
7. Verify hourly and daily feature flags/methods match what each weather entity actually supports.
8. Remove or adapt legacy forecast properties only when current Home Assistant requires it.
9. Handle missing values without exceptions or silently corrupting aggregates.
10. Convert #114's strict `xfail` into passing tests.
11. Resolve the four inherited `weather.py` mypy errors while establishing the final Home Assistant forecast/coordinator types; do not merely cast incorrect runtime shapes or add ignores.
12. Preserve the complete one-hour FMI source series needed to sum `Precipitation1h`; a configured coarser presentation/legacy interval must not make daily totals silently incomplete.
13. Remove the deprecated `forecast` property and make every retained weather entity's hourly/daily methods match its advertised features. Preserve the legacy optional daily entity until S11 can test a registry-safe removal or migration.

### Required tests

- rain starts after midnight/after the first daily sample;
- mixed rain/snow/clear conditions;
- no precipitation samples versus explicit zero samples;
- negative temperatures;
- missing min/max source values;
- month/year boundary;
- Europe/Helsinki DST start and end;
- partial local day;
- unordered or duplicate timestamps;
- hourly and daily methods return the correct forecast granularity;
- expected Home Assistant dictionary keys and units.

### Exit criteria

- #114 fixed.
- Aggregation policy documented and reproducible.
- No first-sample shortcut remains for fields requiring aggregation/selection.
- `weather.py` is mypy-clean and the repository total is no greater than 14 errors.
- Offline and coverage tests pass.

---

## Session S06 — Sensor/entity correctness and issues #111/#112

### Objective

Restore correct sensor values and location-aware entity organization while respecting modern Home Assistant entity conventions and user customizations.

### Required work

1. Reproduce #111 against the upgraded FMI client and identify the authoritative gust field(s), units, and missing-data behavior.
2. Restore wind-gust state when valid data exists. If the current client has multiple gust/max-wind fields, define an explicit precedence based on their documented semantics.
3. When gust data is absent, represent absence correctly; do not substitute ordinary wind speed or a fabricated zero.
4. Reproduce #112 on a fresh-entry fixture.
5. Implement current Home Assistant entity naming/device grouping conventions:
   - use location/device context appropriately;
   - ensure generated entity IDs for new entries are location-aware where Home Assistant permits;
   - use `has_entity_name` and entity descriptions correctly if applicable;
   - keep unique IDs stable and independent of display names as migration work permits.
6. Add a conservative migration path for existing generated entity IDs if needed:
   - rename only integration-generated defaults;
   - preserve user-customized IDs;
   - detect target collisions;
   - never delete/recreate entities merely to change a name.
7. Verify every sensor's device class, state class, native unit, native value type, availability, and extra attributes against current Home Assistant requirements.
8. Use current `SensorEntity` patterns if required for correctness/compatibility. Do not perform unrelated sensor abstraction work.
9. Convert #111 and the fresh-install portion of #112 from strict `xfail` to passing tests. Complete registry migration coverage in S11.
10. Resolve the seven inherited `sensor.py` mypy errors using the final entity/coordinator types and an explicitly heterogeneous entity collection; do not add broad ignores.

### Required tests

- valid gust, missing gust, NaN gust, zero gust, client field fallback;
- fresh install generated names/grouping;
- two locations with same sensor types;
- location names containing non-ASCII characters and punctuation;
- user-customized entity ID preserved;
- generated-ID target collision;
- entity availability through coordinator failures/recovery;
- correct units/types for all existing sensors.

### Exit criteria

- #111 fixed.
- #112 fixed for new entries and migration design implemented sufficiently for S11 verification.
- No entity is recreated unnecessarily.
- `sensor.py` is mypy-clean and the repository total is no greater than 7 errors.
- Full offline suite passes.

---

## Session S07 — Location reconfigure flow and issue #115

### Objective

Allow users to change coordinates of an existing FMI config entry without deleting it or rebuilding automations.

### Required work

1. Implement the current Home Assistant reconfigure flow for latitude/longitude.
2. Validate coordinates and verify FMI connectivity/data availability before committing the change, using current Home Assistant flow patterns.
3. On failed validation, keep the original entry unchanged and show a useful translated error.
4. Separate immutable entry/entity identity from mutable coordinates and reverse-geocoded place name.
5. Design and implement config-entry migration from the v0.6.2 coordinate-based unique-ID scheme.
6. Preserve existing entities and automations:
   - keep stable entity unique IDs through coordinate changes;
   - update device/location titles and generated display names safely;
   - preserve user-customized entity IDs;
   - avoid duplicate entries for the same configured location according to the documented duplicate policy.
7. Decide whether to offer a “use Home zone coordinates” mode:
   - safe coordinate editing is mandatory and is sufficient to resolve #115;
   - dynamic ongoing tracking of Home zone changes is optional and must not be added if it introduces lifecycle or identity complexity disproportionate to this maintenance effort;
   - if implemented, document when updates occur and test them.
8. Reload only the affected config entry after a successful reconfiguration.
9. Add translations and user-facing documentation for the reconfigure flow.
10. Convert #115's regression/acceptance tests to passing.

### Required tests

- successful coordinate change;
- invalid latitude/longitude;
- FMI validation failure leaves old entry intact;
- place-name change after coordinate change;
- stable config-entry/entity identity;
- customized entity IDs preserved;
- duplicate location attempt;
- collision during migration;
- reconfigure followed by reload and new data;
- migration from a realistic v0.6.2 config entry.

### Exit criteria

- Existing entry can be safely moved.
- Automations referencing existing entity IDs remain valid in tested migration scenarios.
- #115 is resolved by documented behavior.
- Full offline suite passes.

---

## Session S08 — Polar sun, time boundaries, and missing-data robustness; PR #116

### Objective

Eliminate crashes and incorrect date/time behavior around polar day/night, calendar boundaries, DST, and incomplete FMI values.

### Required work

1. Review PR #116 and its exact diff. Credit the contributor in release notes if the implementation is adopted or materially derived.
2. Add deterministic tests where Home Assistant's sunrise or sunset helper returns `None`.
3. Select and document a safe fallback symbol policy when day/night cannot be determined. Do not crash.
4. Audit all current local-date/time comparisons in the integration, especially:
   - “best time of day” selection;
   - next-day selection;
   - forecast aggregation;
   - strike age filtering preparation;
   - timestamp conversion.
5. Replace day-of-month arithmetic with timezone-aware date/datetime operations where confirmed.
6. Make value extraction robust to `None`, NaN, infinities, numeric strings if the dependency can emit them, and unexpected/missing fields. Reject invalid values rather than propagating exceptions or false data.
7. Handle empty forecast lists and partially missing forecasts gracefully.
8. Ensure all datetimes exposed to Home Assistant are timezone-aware and use current Home Assistant helpers.
9. Add tests for unknown FMI weather symbols/codes and a safe fallback.
10. Convert the PR #116 regression tests to normal passing tests.
11. Resolve the three inherited `utils.py` mypy errors as part of the optional-sun and time-helper fixes, including the `const` name collision; do not hide an unsafe `None` path with a cast.

### Required tests

- midnight sun;
- polar night;
- missing only sunrise;
- missing only sunset;
- month end, year end, leap day;
- DST forward/back transitions;
- empty forecast;
- all-NaN field;
- mixed valid/invalid fields;
- unknown symbol code;
- best-time selection across midnight and month boundary.

### Exit criteria

- PR #116's failure mode is fixed with automated tests.
- No confirmed day-of-month arithmetic bug remains.
- Missing FMI data does not crash entity updates.
- `utils.py` is mypy-clean and the repository total is no greater than 4 errors.
- Full offline suite passes.

---

## Session S09 — Lightning/sea-level hardening and issue #110

### Objective

Make optional lightning and sea-level features safe, bounded, independently available, and resistant to malformed or unavailable external data.

### Required work

1. Implement #110 with a translated user option for maximum lightning-strike age.
2. Define units, allowed range, default, and migration behavior. Preserve existing behavior by default unless the existing behavior is demonstrably unsafe; document any changed default.
3. Filter strikes using timezone-aware timestamps and an exact, tested boundary rule.
4. Confirm and fix any seconds/milliseconds error in timeout or age calculations.
5. For every direct HTTP request used by lightning/sea-level features:
   - use a current Home Assistant-supported HTTP session or an executor only when unavoidable;
   - set bounded connect/read/total timeouts;
   - check HTTP status;
   - classify transport, server, client, and parse errors;
   - validate response shape and parallel-array lengths;
   - avoid unbounded retries.
6. Ensure lightning or sea-level failure cannot make core forecast/observation data unavailable.
7. Review reverse-geocoding behavior:
   - treat geocoding as optional metadata;
   - cache/deduplicate requests where appropriate;
   - do not reverse-geocode each strike repeatedly on every refresh;
   - preserve useful strike distance/direction/time data when geocoding fails;
   - respect the current geocoder service usage policy.
8. Define clear availability/freshness behavior for optional entities.
9. Add malformed XML/error response fixtures and tests.
10. Convert #110 acceptance tests to passing.
11. Resolve the four inherited `__init__.py` mypy errors in the lightning/sea-level parsing structures using the validated final data shapes.

### Required tests

- strike just inside, exactly at, and just outside max age;
- missing/malformed strike timestamp;
- unequal response array lengths;
- HTTP 4xx/5xx, timeout, invalid XML, empty response;
- geocoder failure and cache behavior;
- sea-level failure while weather remains available;
- lightning failure while weather remains available;
- option migration/default;
- no blocking network work on the event loop.

### Exit criteria

- #110 implemented and documented.
- Optional source failures are isolated.
- Network requests are bounded and validated.
- `make type-check` passes with zero repository errors; later sessions preserve this zero baseline.
- Full offline suite passes.

---

## Session S10 — Full Home Assistant config/lifecycle integration tests

### Objective

Complete broad Home Assistant integration coverage for config flows, setup, lifecycle, availability, and public entity behavior.

### Required work

1. Expand tests to exercise the integration through Home Assistant public interfaces rather than constructing entities directly wherever practical.
2. Cover every meaningful branch in:
   - initial config flow;
   - options flow;
   - reconfigure flow;
   - setup/first refresh;
   - platform forwarding;
   - unload/reload;
   - update listeners;
   - error/retry states.
3. Verify translated error keys and abort reasons.
4. Test current weather, hourly forecast, daily forecast, normal sensors, observation sensors, lightning, and sea-level entities through Home Assistant state/entity APIs.
5. Exercise source failure/recovery combinations from S04 and S09.
6. Test that update listeners are added once and removed on unload.
7. Test that reloads do not duplicate entities or callbacks.
8. Test two simultaneously loaded locations with independent data/failures.
9. Test disabled optional entities/features and later option changes.
10. Raise coverage for config flow/setup/coordinators/entities to target levels without artificial assertions.

### Verification

- No ordinary test accesses the network.
- Config-flow branch coverage is complete.
- Setup/unload/reload tests pass under current Home Assistant stable.
- Coverage report identifies no untested critical error path.

### Exit criteria

- All config/lifecycle behavior is protected by Home Assistant-level tests.
- Coverage targets are met or only explicitly documented migration gaps remain for S11.
- Full offline suite passes.

---

## Session S11 — Registry migration, stable identity, and multi-entry tests

### Objective

Prove that upgrades and coordinate changes preserve config entries, devices, entities, and user customizations across realistic Home Assistant registry states.

### Required work

1. Create realistic serialized/in-memory fixtures representing v0.6.2-style:
   - config entry data/options/version/minor version;
   - coordinate-based config unique ID;
   - coordinate/name-based entity unique IDs;
   - generated entity IDs;
   - customized entity IDs;
   - multiple entries and collisions.
2. Test config-entry migration and entity-registry migration separately and together.
3. Verify idempotency: running migration twice changes nothing the second time.
4. Verify rollback/failure behavior when a target identifier already exists.
5. Verify that coordinate reconfiguration after migration keeps stable identity.
6. Verify that changing reverse-geocoded location name does not recreate entities.
7. Verify that two entries at different coordinates but with the same reverse-geocoded place text do not collide.
8. Verify that a duplicate-coordinate policy behaves consistently before and after migration.
9. Complete #112 migration acceptance tests.
10. Document migration rules and any intentionally preserved legacy entity IDs in `docs/maintenance/MIGRATIONS.md`.
11. Decide and test the registry-safe disposition of the legacy optional daily weather entity retained in S05: preserve it intentionally, disable it through a migration, or remove it only with proven entity-reference behavior. Do not silently orphan a customized entity.

### Verification

- Run migration tests against current Home Assistant's config-entry/entity/device registry APIs.
- Run the migration suite multiple times to prove idempotency.
- Review resulting registry snapshots/diffs for unexpected deletions.

### Exit criteria

- Existing users retain functional entity references in all tested normal/customized cases.
- Migrations are collision-safe and idempotent.
- #112 and #115 migration portions are complete.
- Full offline suite passes and coverage targets are met.

---

## Session S12 — Live FMI end-to-end test suite and scheduled probe

### Objective

Add controlled real-network verification that detects FMI API/client contract drift and confirms parsed data reaches Home Assistant correctly.

### Required work

1. Re-read current FMI WFS documentation, stored-query guidance, changelog, terms/license, and request limits.
2. Select public test locations and an observation station from current FMI metadata. Record why each was chosen.
3. Create `docs/maintenance/LIVE_TESTS.md` containing:
   - exact commands;
   - locations/station IDs;
   - FMI endpoints/stored queries indirectly or directly exercised;
   - request count per run;
   - current service limits;
   - retry/timeout policy;
   - expected assertions;
   - failure classification;
   - license/attribution;
   - privacy rules.
4. Add opt-in live tests at two levels:
   - dependency/API contract probe;
   - full Home Assistant config-entry/entity/forecast probe.
5. Ensure the full probe checks the state/forecast data consumed by Home Assistant dashboards, not only raw client objects.
6. Add broad, stable invariants:
   - response is structurally usable;
   - timestamps are timezone-aware and ordered;
   - present numeric values are finite and broadly plausible;
   - current/observation data is not implausibly old according to documented source cadence;
   - daily precipitation agrees with the integration's documented sum of matching hourly values;
   - entity units and availability are correct.
7. Do not assert exact temperature, condition, precipitation, or station values.
8. Add a manual/scheduled workflow draft or minimal workflow. S15 will security-harden and integrate it.
9. Bound requests and retries so one run uses only a tiny fraction of FMI's published limits.
10. Ensure live logs/artifacts contain only public test coordinates.

### Verification

- Run the live suite once from the development environment.
- Run the offline suite afterward to prove marker separation.
- Simulate an offline environment and confirm live tests are skipped unless explicitly selected.
- Confirm a deliberately malformed contract fixture fails with actionable diagnostics.

### Exit criteria

- Real FMI forecast and observation data successfully reaches Home Assistant test entities.
- Daily-vs-hourly live semantic check passes.
- Live tests are opt-in and rate-limit-conscious.
- Failure output distinguishes likely outage from contract/parsing/exposure errors as far as evidence permits.

---

## Session S13 — Evidence-based critical runtime correctness audit and fixes

### Objective

Search for additional critical/high runtime defects in the existing feature set and fix only confirmed problems with regression tests.

### Required work

1. Review the candidate-risk list in Section 7 against current code.
2. Review all open issues discovered in S00 and recent closed issues/PRs for unresolved regressions.
3. Perform a focused audit of:
   - event-loop blocking;
   - coordinator/listener lifecycle;
   - first-refresh and stale-data semantics;
   - exception boundaries;
   - retries/timeouts;
   - malformed/partial response handling;
   - timestamp/timezone handling;
   - entity availability;
   - option validation;
   - multiple-entry isolation;
   - update intervals and accidental request amplification;
   - global logging side effects;
   - unknown/changed FMI values;
   - Home Assistant deprecation warnings visible in tests/logs.
4. Use targeted dynamic tests, monkeypatching, fake clocks, and property-based tests only where they provide clear value. Do not add a large testing framework for one trivial case.
5. Classify findings in `docs/maintenance/RUNTIME_AUDIT.md`:
   - critical;
   - high;
   - medium;
   - low;
   - not reproducible;
   - expected behavior.
6. For every critical/high finding:
   - reproduce;
   - add regression test;
   - implement focused fix;
   - document root cause and commit.
7. Medium/low findings may be left for a later plan only when documented with rationale and no interaction with an in-scope critical fix.
8. Remove `logging.basicConfig` or comparable global side effects if confirmed in current code.
9. Confirm there are no unexpected direct network calls left outside controlled client/session boundaries.

### Verification

- Run full offline tests with coverage.
- Run event-loop blocking detection available in current Home Assistant tests where practical.
- Run with warnings/deprecations treated as errors for integration code where feasible.
- Re-run live tests only if a runtime fix changed request/parse behavior.

### Exit criteria

- No known reproducible critical/high runtime correctness defect remains unaddressed or unexplained.
- Every fixed finding has a regression test.
- Audit report is committed.
- No broad refactor was introduced without a documented necessity.

---

## Session S14 — Home Assistant compatibility, dependency, security, and privacy audit

### Objective

Validate the integration against current Home Assistant standards and identify supply-chain, CI, privacy, and compatibility problems before final CI hardening.

### Required work

1. Compare the integration against the current relevant Home Assistant Integration Quality Scale rules, using them as guidance for a custom integration rather than claiming an official tier.
2. Verify current patterns for:
   - `ConfigEntry.runtime_data` or the current recommended equivalent;
   - typed config entries where applicable;
   - config flow/reconfigure/options flow;
   - coordinator entities;
   - weather forecast APIs;
   - sensor native values/units;
   - device/entity naming;
   - unload/reload;
   - diagnostics and privacy;
   - polling interval and parallel updates.
3. Run static/type analysis, verify the Section 8.6 zero-error baseline, and resolve any newly discovered real integration errors. Do not perform cosmetic type-driven rewrites outside touched code or hide failures with broad ignores.
4. Run dependency vulnerability and license checks on the locked graph.
5. Audit GitHub workflow dependencies and action sources.
6. Audit logs/diagnostics for exact coordinates and external-service payloads.
7. Add sanitized Home Assistant diagnostics if current quality guidance and scope justify it; otherwise document why it is deferred. Diagnostics must redact or reduce coordinates sufficiently to avoid exposing a home location.
8. Review reverse-geocoder privacy and failure behavior.
9. Check install/upgrade behavior on:
   - current Home Assistant stable;
   - the explicitly supported previous stable, if retained by support policy;
   - current beta/prerelease as an informational compatibility run.
10. Create `docs/maintenance/COMPATIBILITY_SECURITY_AUDIT.md` with findings and decisions.
11. Fix every critical/high compatibility, security, or privacy issue discovered. Do not hide failures with broad ignores.

### Verification

- Type/static checks pass under the selected supported environment.
- No unaddressed critical/high dependency vulnerability.
- No normal log or diagnostic artifact exposes precise private coordinates.
- Stable Home Assistant compatibility suite passes.
- Beta findings are clearly separated from stable release blockers.

### Exit criteria

- Support matrix and known compatibility limits are explicit.
- Critical/high security/privacy/compatibility findings are fixed or formally blocked with evidence.
- Audit report committed.

---

## Session S15 — Production CI/CD, HACS validation, and release verification

### Objective

Turn all established checks into secure, reliable, maintainable GitHub Actions workflows and verify the repository can be installed and started as distributed.

### Required work

1. Replace the preliminary CI with a clear workflow set. Recommended logical separation:
   - `ci.yml`: format, lint, type check, offline tests, coverage, import/setup/install smoke;
   - `validate.yml`: hassfest and HACS validation;
   - `dependency-review.yml`: dependency/security review where supported;
   - `compatibility.yml`: scheduled stable/beta and dependency-resolution checks;
   - `live-fmi.yml`: manual and modest scheduled live FMI tests.
2. Use a matrix only where it tests a declared support dimension. Avoid redundant matrices that multiply CI time without increasing confidence.
3. Pin all external actions to full commit SHAs and annotate the release tag/version in comments. Inspect composite and container actions for nested action/image references; replace, digest-pin, or explicitly block any mutable nested reference such as an image tag.
4. Apply least-privilege permissions at workflow/job level.
5. Add concurrency cancellation, job timeouts, and safe caching.
6. Ensure pull requests from forks cannot access secrets or write tokens.
7. Add action syntax/security validation, such as `actionlint` and a current GitHub Actions security analyzer where practical.
8. Add Dependabot configuration for:
   - Python/dev dependencies;
   - GitHub Actions;
   - grouped updates where useful without hiding breaking changes.
9. Enforce coverage thresholds in CI.
10. Ensure live FMI and beta jobs are not required pull-request checks, but scheduled failures remain visible.
11. Add a clean installation/package-layout test that simulates what HACS/manual installation delivers to `<config>/custom_components/fmi/`.
12. Boot/setup a minimal Home Assistant test configuration with the installed artifact and mocked network.
13. Validate release metadata:
   - `manifest.json` versioning;
   - `hacs.json`;
   - repository topics/files expected by HACS;
   - release archive layout if releases are used;
   - changelog linkability.
14. Document recommended branch-protection required checks in `docs/maintenance/CI.md`. Do not change remote settings unless explicitly authorized.
15. Do not publish a release or push a tag in this session.

### Verification

- Run workflows locally where tooling allows and then inspect an actual GitHub Actions run if the environment has authorized access; otherwise validate YAML/actions and record that remote execution remains owner-run.
- All required PR jobs pass from a clean checkout.
- Scheduled live workflow can be manually triggered and uses no secrets.
- HACS and hassfest validations pass.
- Installation/setup smoke test passes.

### Exit criteria

- CI covers buildability/installability, startability/setup, lint, type checks, tests, coverage, validation, and dependency risk.
- Workflows follow documented security practices.
- Dependency automation is configured.
- No release has been published without owner approval.

---

## Session S16 — Documentation, final verification, and final `AGENTS.md`

### Objective

Produce a release-ready maintenance result, finalize durable agent instructions, and prove all requirements from this plan are complete.

### Required work

1. Update `README.md` with accurate:
   - purpose and data sources;
   - supported Home Assistant/Python versions;
   - HACS/manual installation;
   - configuration, options, and reconfiguration;
   - forecast versus observation behavior;
   - hourly/daily aggregation summary;
   - optional lightning/sea-level behavior;
   - update intervals and external services;
   - troubleshooting;
   - privacy/coordinates note;
   - removal instructions;
   - development/test commands;
   - live-test disclaimer.
2. Create or update `CHANGELOG.md` with a release-candidate entry mapping fixes to #110, #111, #112, #114, #115, #117, and PR #116, plus confirmed audit fixes.
3. Complete `docs/maintenance/FINAL_REPORT.md` containing:
   - base and final commits;
   - dependency before/after summary;
   - issue closure matrix;
   - test/coverage results;
   - live test result and timestamp;
   - CI checks;
   - compatibility matrix;
   - migrations and user impact;
   - remaining medium/low risks;
   - recommended release version and manual release steps.
4. Finalize root `AGENTS.md`. It must be concise, accurate, and useful without rereading all historical handoffs. Include:
   - repository purpose and supported scope;
   - final repository layout;
   - exact setup, format, lint, type-check, offline-test, full-test, validation, and live-test commands;
   - test-layer/network rules;
   - Home Assistant lifecycle and async rules;
   - stable identity/migration rules;
   - forecast semantics document reference;
   - dependency update policy;
   - CI/release expectations;
   - no-refactoring-for-its-own-sake rule;
   - how to use this plan and handoffs for future work;
   - definition of done;
   - prohibition on claiming checks passed without running them.
5. Keep `AGENTS.md` below Codex's project instruction size limit; link to detailed documents instead of copying them.
6. Resolve every remaining `xfail`, TODO, and tracker row associated with this plan. Any unrelated pre-existing TODO must be clearly distinguished.
7. Update all session rows, issue rows, and decision records.
8. Run final verification from a clean environment/checkout:
   - dependency sync;
   - formatting/lint/type checks;
   - complete offline tests and coverage;
   - HACS/hassfest/action validation;
   - install/setup smoke;
   - live FMI suite;
   - stable Home Assistant compatibility;
   - beta informational check where available;
   - vulnerability audit.
9. Review the complete diff from the original base for unrelated refactoring or accidental behavior changes.
10. Recommend a release version, but do not tag, push, publish, or close issues without owner authorization.

### Exit criteria

- Every required tracker and known-issue row is `DONE` or explicitly `BLOCKED` with owner-visible evidence.
- All required checks pass from a clean environment.
- Coverage target is met.
- Live FMI test passes or a contemporaneous external FMI outage is evidenced; a genuine outage does not permit hiding an integration failure.
- No known critical/high defect remains.
- `AGENTS.md` is the accurate durable entry point for future agents.
- Final report and release notes are complete.

---

## 13. Handoff template

Each session must create `docs/agent-handoffs/SXX.md` with this structure:

```markdown
# Session SXX Handoff

## Metadata

- Session: SXX — <title>
- Status: DONE | IN_PROGRESS | BLOCKED
- Started UTC: <timestamp>
- Completed UTC: <timestamp or N/A>
- Base commit: <sha>
- Final commit(s): <sha list or N/A with reason>
- Executor: OpenAI Codex

## Objective

<One paragraph describing the bounded objective.>

## Changes made

- <Behavior/code/test/documentation change>

## Root causes and decisions

- <Problem, evidence, decision, and why it was necessary>

## Tests and checks run

| Command | Result | Notes |
|---|---|---|
| `<exact command>` | PASS / FAIL / NOT_RUN | <important output or reason> |

Never record PASS for a command that was not run.

## Files materially changed

- `<path>` — <reason>

## Issue/requirement mapping

- `<issue or plan requirement>` — <test and implementation reference>

## Remaining risks or blockers

- <risk, severity, evidence, next action>

## Instructions for the next session

- <prerequisites, relevant files, commands, and pitfalls>
```

---

## 14. Decision log

Codex must add rows for material architecture, semantics, migration, support, or dependency decisions.

| ID | Session | Date UTC | Decision | Alternatives considered | Evidence/rationale | Document/commit |
|---|---|---|---|---|---|---|
| D001 | S01 | 2026-07-31 | Migrate the integration from repository root to `custom_components/fmi/` | Retain root with `content_in_root: true` | HACS documents root content as valid, but the current hassfest container rejected it with `Domain does not match dir name`; the standard layout also enables public-loader Home Assistant tests without import shims | `docs/agent-handoffs/S01.md`; OWNER_TO_COMMIT |
| D002 | S01 | 2026-07-31 | Target Home Assistant 2026.7.4 on Python 3.14.2 for the reproducible S01 environment, using `pytest-homeassistant-custom-component==0.13.348` | Use the helper's newest release 0.13.349 with Home Assistant 2026.8.0b0; retain an older Home Assistant/Python pair | Home Assistant 2026.7.4 is the current stable release and requires Python 3.14.2; helper 0.13.348 pins that exact stable version, while 0.13.349 targets the next beta | `docs/maintenance/DEVELOPMENT.md`; `docs/agent-handoffs/S01.md`; OWNER_TO_COMMIT |
| D007 | S01 | 2026-07-31 | Use Ruff as the sole flake8-style linter and formatter with `E`, `F`, `I`, `UP`, `B`, and `ASYNC`; retain Pylint as a complementary check | Keep the former flake8 fatal subset; run Ruff alongside flake8; drop Pylint | The broader Ruff selection exposed import, modernization, and bugbear findings, supports both safe fixes and formatting, and now passes with no active legacy dependency, configuration, or command; Pylint continues to pass at 10.00/10 | `docs/maintenance/DEVELOPMENT.md`; `docs/agent-handoffs/S01.md`; OWNER_TO_COMMIT |
| D008 | S02 | 2026-07-31 | Use compact synthetic fixture specifications that build the installed client's real models, plus a narrow async fake for the three consumed client methods | Store raw live FMI captures; use `SimpleNamespace` throughout tests; add a production wrapper before an upgrade requires it | Synthetic values avoid owner-coordinate/license risk, generated hourly series stay reviewable, real `NamedTuple` models expose dependency-shape changes, and the fake provides deterministic client/server failures without production refactoring | `tests/helpers/fmi.py`; `tests/fixtures/fmi/README.md`; `docs/agent-handoffs/S02.md`; OWNER_TO_COMMIT |
| D009 | S03 | 2026-07-31 | Keep Home Assistant 2026.7.4's exact Pillow/PyJWT pins and track their current High-severity advisories as a temporary owner-approved exception | Override Home Assistant metadata with fixed packages; target a Home Assistant prerelease; stop all maintenance work | The integration neither imports nor declares these packages and its manifest closure audits cleanly; overriding exact Core pins makes the environment inconsistent, while the owner explicitly accepted the temporary risk for private testing until stable Home Assistant updates | `TODO.md`; `docs/maintenance/DEPENDENCIES.md`; `docs/agent-handoffs/S03.md`; OWNER_TO_COMMIT |
| D010 | S04 | 2026-07-31 | Load an entry when either the primary current source (including place fallback) or a configured station succeeds, while keeping forecast and optional-source availability independent | Require the forecast-backed coordinator to succeed; treat any configured station failure as fatal; retain stale forecast data | Independent coordinators preserve usable observations during a WFS incident; explicit stale-data clearing and transition-only logging make outages and automatic recovery visible without presenting old data as current | `docs/maintenance/AVAILABILITY.md`; `tests/test_availability.py`; `docs/agent-handoffs/S04.md`; `ad0c997ea70f2316195808347501de4b4e8f58ea` |
| D011 | S05 | 2026-07-31 | Retain the complete one-hour FMI series and derive separate UTC hourly and local-calendar daily forecasts with documented deterministic aggregation; preserve the legacy optional daily entity until S11 migration evidence exists | Aggregate the configured coarse FMI timestep; make another daily request; remove the legacy entity immediately | `Precipitation1h` cannot be totaled from a coarse series, a second request would amplify load/failure paths, and Home Assistant requires separate hourly/daily methods with UTC timestamps. Keeping the legacy entity avoids silently removing an existing unique ID while its methods become semantically correct. | `docs/maintenance/FORECAST_SEMANTICS.md`; `tests/test_forecast_characterization.py`; `tests/test_setup.py`; OWNER_TO_COMMIT |
| D003 | TBD | — | Daily condition/wind/other-field aggregation semantics | TBD | Must follow FMI field meaning and current Home Assistant schema | TBD |
| D004 | TBD | — | Immutable config-entry/entity identity and v0.6.2 migration | TBD | Coordinates/place names are mutable; user automations must survive | TBD |
| D005 | TBD | — | Lightning max-age default and units | TBD | Backward compatibility, usefulness, and clear UI semantics | TBD |
| D006 | TBD | — | Stale-data and partial-availability policy | TBD | Avoid both unnecessary outage and misleading freshness | TBD |

---

## 15. Final definition of done

The maintenance project is complete only when all statements below are true.

### Dependencies

- The newest stable compatible `fmi-weather-client` available at implementation time is used.
- All direct runtime, development, test, and GitHub Actions dependencies have been checked against their newest stable releases.
- The development/test environment is reproducibly locked.
- The resolved runtime/test graph is documented.
- No unaddressed critical/high known vulnerability remains.
- Every version exception is reproduced and documented.

### Correctness and availability

- #110, #111, #112, #114, #115, and #117 meet their required outcomes.
- PR #116's polar failure is fixed with tests.
- Daily precipitation and other daily fields follow documented semantics.
- Forecast and observation outages degrade independently and recover automatically.
- Missing/NaN/malformed data does not crash updates or produce fabricated values.
- Optional lightning/sea-level/geocoding failures do not disable core weather.
- Date/time logic works across month/year/DST/polar cases.

### Compatibility and migrations

- Current supported Home Assistant stable loads, unloads, reloads, and updates the integration correctly.
- Config flow, options flow, and reconfigure flow work through the UI-facing APIs.
- Existing v0.6.2-style config entries and registries migrate safely and idempotently.
- User-customized entity IDs are preserved.
- Coordinate changes do not require rebuilding automations in tested normal cases.

### Tests

- Offline unit, contract, and Home Assistant integration tests pass without network access.
- Coverage thresholds are enforced.
- Every fixed issue has an explicit regression test.
- Live FMI tests exercise forecast, observation, parsing, and Home Assistant exposure using public test locations.
- Live tests use stable invariants and modest request volume.

### CI and maintenance

- Required pull-request CI checks formatting, lint, typing, tests, coverage, setup/installability, HACS, hassfest, and dependency risk.
- Scheduled jobs check Home Assistant beta/dependency drift and real FMI behavior.
- Workflows use least privilege and immutable action pins.
- Dependency update automation exists.
- README, changelog, migration notes, audits, and final report are current.
- Root `AGENTS.md` is concise, accurate, and sufficient for future Codex sessions.

### Scope discipline

- No unrelated feature work was added.
- No refactor exists without a documented correctness, compatibility, testing, migration, security, or validation reason.
- No test, linter, type checker, or security check was weakened merely to obtain a green result.

---

## 16. Authoritative references to re-check during implementation

These references establish the starting point. The executing agent must use current versions of the documentation and record access dates.

### Upstream repository and known work

- Repository: <https://github.com/anand-p-r/fmi-hass-custom>
- Issue #110: <https://github.com/anand-p-r/fmi-hass-custom/issues/110>
- Issue #111: <https://github.com/anand-p-r/fmi-hass-custom/issues/111>
- Issue #112: <https://github.com/anand-p-r/fmi-hass-custom/issues/112>
- Issue #114: <https://github.com/anand-p-r/fmi-hass-custom/issues/114>
- Issue #115: <https://github.com/anand-p-r/fmi-hass-custom/issues/115>
- Pull request #116: <https://github.com/anand-p-r/fmi-hass-custom/pull/116>
- Issue #117: <https://github.com/anand-p-r/fmi-hass-custom/issues/117>

### FMI

- FMI Open Data overview: <https://en.ilmatieteenlaitos.fi/open-data>
- FMI Open Data manual: <https://en.ilmatieteenlaitos.fi/open-data-manual>
- FMI WFS services/stored queries and limits: <https://en.ilmatieteenlaitos.fi/open-data-manual-fmi-wfs-services>
- FMI WFS examples and guidelines: <https://en.ilmatieteenlaitos.fi/open-data-manual-wfs-examples-and-guidelines>
- FMI time-series data: <https://en.ilmatieteenlaitos.fi/open-data-manual-time-series-data>
- FMI Open Data changelog: <https://en.ilmatieteenlaitos.fi/open-data-changelog>
- `fmi-weather-client` package: <https://pypi.org/project/fmi-weather-client/>

### Home Assistant and HACS

- Home Assistant integration quality scale: <https://developers.home-assistant.io/docs/core/integration-quality-scale/>
- Home Assistant integration manifest: <https://developers.home-assistant.io/docs/creating_integration_manifest/>
- Home Assistant config flow: <https://developers.home-assistant.io/docs/core/integration/config_flow/>
- Home Assistant reconfigure flow guidance: <https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/reconfiguration-flow/>
- Home Assistant testing guidance: <https://developers.home-assistant.io/docs/development_testing/>
- Home Assistant standalone hassfest action: <https://github.com/home-assistant/actions>
- HACS documentation: <https://www.hacs.xyz/>
- HACS repository validator: <https://github.com/hacs/action>

### Codex and CI security

- Codex `AGENTS.md` discovery and precedence: <https://developers.openai.com/codex/agent-configuration/agents-md>
- Codex long-horizon task practices: <https://developers.openai.com/blog/run-long-horizon-tasks-with-codex>
- GitHub Actions secure-use guidance: <https://docs.github.com/en/actions/reference/security/secure-use>
- GitHub dependency review action: <https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/manage-your-dependency-security/configure-dependency-review-action>

---

## 17. Owner review checkpoints

The sessions are executable without repeated clarification, but the following outputs deserve explicit owner review before publishing a release:

1. S03 dependency exceptions, if any.
2. S05 forecast aggregation semantics.
3. S07 identity/migration design and any unavoidable entity-ID effect.
4. S09 lightning max-age default.
5. S14 support matrix and any remaining security/privacy exception.
6. S16 final report, recommended version, changelog, and release steps.

Codex should not stop routine implementation merely to ask about choices already constrained by this plan. It should stop as `BLOCKED` only when a safe decision cannot be made from authoritative API semantics, backward compatibility, tests, and the rules above.
