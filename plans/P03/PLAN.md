<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# P03 Implementation Plan: Reliable Local Lightning State And Direction

> **Archive notice:** This completed plan is a dated execution record. Use the current
> [contract catalog](../../docs/contracts/README.md), [maintenance runbooks](../../docs/maintenance/),
> and [plan archive index](../README.md) instead of treating historical commands or requirements
> below as current policy.

> **Target repository:** [`kogeler/fmi-hass-custom`](https://github.com/kogeler/fmi-hass-custom)
> **Intended executor:** OpenAI Codex
> **Plan baseline date:** 2026-08-18
> **Execution model:** sequential green session checkpoints
> **Plan status:** `DONE`
> **Planning branch/commit:** `master` at `7e2ac6ce28863c9cd675b7ec3bd4bce26cee9a67`
> **Execution branch:** `p03-reliable-local-lightning`
> **Release train:** owner-selected `1.2.0` after published `1.1.0`; release notes must prominently
> document the intentional lightning state/attribute incompatibility
> **Canonical agent entry point:** `AGENTS.md`
> **Verified execution baseline:** `plans/P03/BASELINE.md` (to be created by S00)
> **Execution reports:** `plans/P03/SXX.md` (to be created by the owning session)

---

## 1. How to use this plan

The canonical plan path is:

```text
plans/P03/PLAN.md
```

P03 follows the self-contained P01/P02 structure. After successful execution its canonical files
must be:

```text
plans/P03/
  PLAN.md
  BASELINE.md
  S00.md
  S01.md
  S02.md
  S03.md
  S04.md
```

Only `PLAN.md` exists before execution. Do not create an unverified `BASELINE.md` or empty session
reports merely to make the directory look complete. S00 owns the baseline, and each session owns
its chronological report and handoff.

`PLAN.md` is the living tracker, requirement matrix, decision log, and definition of done.
`BASELINE.md` records the exact pre-change repository, API, external-source, dependency, and test
state verified by S00. `SXX.md` records what that session actually changed and which exact commands
completed. Do not put P03 progress reports in `docs/maintenance/`, `TODO.md`, P01, or P02. Current
technical contracts belong in `docs/maintenance/` only after implementation proves them.

P01 and P02 are completed historical plans. Read them only when a current contract's history is
necessary; do not modify their trackers or reports while executing P03.

To start the whole plan after the owner selects an execution branch and release:

```text
Read AGENTS.md and plans/P03/PLAN.md in full. Inspect git status and execute S00 through
S04 sequentially. At each boundary update PLAN.md, write the owning report, run every
session gate, and continue only from a green checkpoint. Correct the plan immediately
when verified reality differs. Do not commit.
```

To resume an interrupted run:

```text
Read AGENTS.md and plans/P03/PLAN.md in full. Inspect git status, current lightning code,
the owning maintenance contracts, and the previous P03 report. Execute the next
NOT_STARTED or IN_PROGRESS session whose prerequisites are DONE. Do not repeat completed
work or claim commands that were not run.
```

To run one session only:

```text
Read AGENTS.md and plans/P03/PLAN.md in full. Execute P03 Session SXX only if every
prerequisite is DONE. Update the tracker and decision/requirement rows, write
plans/P03/SXX.md, and stop at that session's green checkpoint without committing.
```

### Context-safety rule

Each session owns one coherent concern. If verified work is larger than the session can safely
complete:

1. Stop at a green, documented checkpoint.
2. Add explicit sub-sessions such as `S02-A` and `S02-B` to the tracker.
3. Record the reason and revised dependency order in the current report and decision log.
4. Keep the parent `IN_PROGRESS` until all mandatory sub-sessions are `DONE`.
5. Continue the split work before advancing to the next numbered session.

Do not silently include unrelated forecast, station, sea-level, config-flow, container, CI, or
dependency-upgrade work.

---

## 2. Mission

Replace the lightning sensor's ambiguous, externally reverse-geocoded state with a fully local and
truthful Home Assistant contract:

1. A successful FMI response with no qualifying strikes is an **available empty observation**, not
   a source failure.
2. A transport, timeout, unsafe payload, parser, or unusable FMI response is **unavailable**, with
   stale lightning state and attributes cleared.
3. A successful non-empty response exposes locally calculated distance, initial bearing, and
   compass direction relative to the coordinates stored by the **specific FMI config entry** that
   owns the sensor.
4. Nominatim, OpenStreetMap attribution, strike-coordinate disclosure to that service, geocoder
   caches/rate limiting, and their dead tests/constants disappear completely.
5. The sensor keeps its existing entity registry record, unique ID, customized entity ID, device,
   config entry, options, and update cadence.

The intended visible non-empty state is a concise distance-and-direction value such as
`42.3 km · SE`. The exact state token, precision, and supported translation behavior must be
frozen in S00 against the current Home Assistant API. Machine-readable `direction` and `bearing`
attributes are mandatory, and distance remains numeric. A valid empty response must have an
explicit, translated, automation-testable "no lightning strikes" state.

This is a deliberate compatibility break for users who compare the old Nominatim address or raw
coordinate fallback stored in the sensor state or `location` attribute. The owner accepted that
trade-off on 2026-08-18. Preserve all unrelated lightning attributes where their meaning remains
valid, and document a direct automation migration path.

---

## 3. Scope boundaries and non-goals

### 3.1 Included behavior

P03 includes:

- explicit source tri-state modeling:
  - `None` = lightning request/payload failed or is unusable;
  - empty collection = FMI succeeded and no qualifying strikes exist;
  - non-empty collection = FMI succeeded with validated strike groups;
- availability based on source validity rather than collection truthiness;
- clearing previous state and all dynamic lightning attributes on empty and failed updates, with an
  explicit empty state written only for the successful-empty case;
- deterministic recovery across every failure/empty/non-empty transition without reload;
- initial geographic bearing from the config entry's coordinates to each FMI strike coordinate;
- an eight-sector compass contract (`N`, `NE`, `E`, `SE`, `S`, `SW`, `W`, `NW`) unless S00 proves a
  better Home Assistant-native localized representation without unstable backend-localized state;
- distance and circular-radius filtering calculated at one reviewed local geometry boundary;
- exact boundary behavior for coincident points, sector edges, the antimeridian, poles, invalid
  coordinates, and geometry non-convergence/failure;
- the same direction/bearing/distance schema for the primary strike and every retained
  `OBSERVATIONS` entry;
- complete removal of the Nominatim runtime path and, if S00 reconfirms the planning inventory,
  complete removal of the now-unneeded `geopy` direct runtime dependency;
- Home Assistant-level compatibility, lifecycle, multi-entry, privacy, recorder-history, and
  registry tests;
- release notes, user guidance, maintenance contracts, translations, dependency records, and TODO
  closure after the behavior passes.

### 3.2 Deliberately incompatible surface

P03 intentionally changes only the user-facing lightning value/schema listed below:

| Existing surface | P03 result |
|---|---|
| Native state is a Nominatim address or raw strike coordinates | Direction-and-distance state for a strike; explicit empty state for a successful no-strike response |
| Primary `location` attribute contains address/coordinates | Removed; replaced by stable direction and bearing while retaining numeric distance |
| Each `OBSERVATIONS[*].location` contains address/coordinates | Removed; each row receives the same direction and bearing schema |
| Entity attribution includes FMI and OpenStreetMap | FMI attribution only |
| Nominatim may receive a selected strike coordinate | No non-FMI lightning network request exists |

Do not delete or rewrite Home Assistant Recorder history to hide the old schema. Historical states
remain under the user's Recorder retention policy. The first successful P03 refresh writes the new
state/attribute mapping; a successful empty response or failure removes stale current attributes.

The following remain compatible:

- config entry and options data;
- config-entry version;
- device and entity registry rows;
- entity unique ID and customized entity ID;
- enabled/disabled state;
- lightning radius and maximum-age options;
- current/forecast, configured observation, and sea-level entities;
- existing `time`, `distance`, `strikes`, `peak_current`, `cloud_cover`, `ellipse_major`, and
  `OBSERVATIONS` meanings for non-empty results, except for the documented removal/replacement of
  nested `location`.

### 3.3 Explicitly excluded behavior

Do not implement any of the following in P03:

- projected closest approach, arrival time, path, speed, or "moving toward/away" conclusions;
- storm-cell identity inferred from individual lightning groups;
- motion inferred from surface wind, forecast wind direction, or one lightning update;
- safety alerts, warnings, evacuation advice, probability, or severity claims;
- radar image processing, cell clustering/tracking, nowcasting, or a new FMI radar product;
- a replacement reverse-geocoding provider, proxy, address database, or raw-coordinate state;
- Home Assistant Home coordinates as the reference when an entry has its own configured point;
- configuration migration or new lightning options without a reproduced requirement;
- a new runtime dependency solely for elementary distance/bearing calculations;
- deleting historical Recorder data;
- changing unrelated sensor identities, update intervals, live test concurrency, or source
  isolation.

### 3.4 Why wind-based storm prediction is excluded

The available wind value is a point/surface forecast, not an observed storm-cell motion vector.
Thunderstorm motion depends on winds through the cloud layer, shear, outflow boundaries, and where
new convective cells form. The National Weather Service documents that an area's storm motion can
deviate significantly from mean wind because of discrete propagation, and NOAA's operational
motion tooling derives motion by tracking the same radar feature across multiple frames. Individual
FMI lightning observations neither identify one cell nor establish a track.

Publishing a closest-approach estimate from ordinary wind would therefore be false precision and
could give a user unsafe reassurance. Reconsider motion only as a separate future plan if FMI
publishes an authoritative, documented, fresh radar-nowcast/storm-cell identifier and motion vector
with defensible uncertainty and failure semantics. P03 must not leave placeholder code or TODO
calculation hooks for the rejected shortcut.

---

## 4. Engineering constraints

### 4.1 Evidence before change

For each behavior:

1. Characterize the current coordinator/parser/entity behavior with deterministic tests.
2. Add or tighten a test for the required outcome and confirm it fails for the expected reason when
   practical.
3. Implement the smallest coherent change.
4. Run focused tests and the session-wide gates.
5. Record exact results and any plan correction in the owning report.

Do not infer that empty/failure recovery, attribute clearing, translations, geometry, or registry
compatibility works from code inspection alone when an executable test is possible.

If execution discovers an error, stale assumption, missing requirement, or unsafe instruction in
this plan, or deliberately departs from the recorded design, stop the affected work and correct
`PLAN.md` immediately in the same work phase. Do not defer the correction until a session report,
handoff, or final review. The owning report must then record the already-applied correction and its
evidence.

### 4.2 Source-state and availability model

- Preserve `list[FMILightningStruct] | None` or replace it with an equally explicit typed model; do
  not collapse it to `bool`.
- The optional-source wrapper must mark lightning available for both empty and non-empty successful
  results. It marks lightning unavailable only for `None`/classified failure.
- The lightning entity must incorporate `super().available` and lightning-source validity directly;
  the generic base rule `native_value is not None` must not erase the empty-success distinction.
- A non-empty result exposes the newest group among the nearest qualifying groups, preserving the
  currently documented ordering unless S00 finds and records a correctness defect.
- A successful empty update clears all previous strike attributes and exposes only the stable empty
  state; it must not retain the last address, direction, bearing, distance, or `OBSERVATIONS`.
- A failed update clears all prior strike data/attributes and makes the entity unavailable.
- Later empty or non-empty successes recover automatically and retain transition-based logging.
- Primary FMI, configured station, forecast, and sea-level availability remain independent.

### 4.3 Geometry contract

- Reference point: the latitude/longitude persisted in the owning config entry and already held by
  that entry's coordinator. Never use `hass.config.latitude/longitude` after setup.
- Target point: the validated FMI lightning row coordinates, held only long enough to calculate
  local results. Do not expose raw target coordinates in the new entity state or attributes.
- Distance: kilometers, finite, non-negative, rounded only once at the presentation/model boundary.
  S00 must compare the current `geopy.geodesic` result with Home Assistant's local WGS84 location
  helper and/or a narrowly owned standard-library implementation before freezing the replacement.
- Bearing: normalized to `[0, 360)` degrees and documented as the initial bearing from the config
  point toward the strike, not the direction from which a storm is travelling.
- Direction sectors: center each of eight sectors on the cardinal/intercardinal bearing, define
  half-open boundaries deterministically, and derive every human/machine value from one function.
- Coincident points: distance is `0`; bearing is mathematically undefined. S00 must freeze one
  explicit non-misleading representation (recommended: `bearing=None`, `direction="here"`) rather
  than inventing north.
- Antimeridian and poles: normalize longitude deltas; test finite results and documented behavior.
- Invalid/non-finite input: reject the row before trigonometry and never leak coordinates in logs.
- Radius: the FMI bbox remains a request-volume prefilter, but every parsed candidate must also be
  discarded when calculated distance exceeds the configured radius. The exact boundary is
  inclusive. This closes the planning-discovered mismatch where the current square bbox can admit
  corner points beyond the advertised circular radius.
- Keep geometry pure and network-free. Do not run elementary math in an executor merely because
  the removed geocoder used one.

### 4.4 User-visible state and translations

- Freeze one stable machine contract before S01 implementation. The intended strike state is
  numeric kilometers followed by a concise direction code, for example `42.3 km · SE`; formatting
  must not depend on a frontend user's locale or on Home Assistant's configured display units.
- Store `direction` as a documented stable token/code and `bearing` as a numeric degree value in
  attributes. Preserve `distance` as numeric kilometers for automations.
- Provide an explicit source token for valid empty data and a supported Home Assistant state
  translation in every existing locale. S00 must test how the current supported Home Assistant
  renders state translations when the same text sensor can also contain a dynamic composite value.
- Do not use Python `None`, the literal accidental string `None`, `unknown`, an empty string, or a
  numeric sentinel to mean "no strikes".
- Do not make this sensor a numeric distance device class while it also needs a distinct textual
  empty state. Do not add a state class incompatible with mixed textual semantics.
- Do not store per-user localized state strings; that makes automation state depend on UI language.
  If the intended full-word translated composite cannot be supported by public HA APIs, use stable
  compass codes in the state and translations only for finite symbolic states such as no-strikes.
- Update `strings.json`, `translations/en.json`, and `translations/fi.json` together. Hassfest
  passing alone does not prove semantic parity; assert keys and Home Assistant state behavior.

### 4.5 Compatibility, migration, and Recorder

- No config-entry version bump is expected because no persisted config field changes.
- Never recreate the entity to obtain the new state. Keep its current description key, unique ID,
  entity registry ID, customized entity ID, enabled state, device identifier, and config entry.
- Exercise a realistic pre-P03 entity registry fixture and loaded entity transition.
- Document that templates comparing the old address/native value or reading `location` must migrate
  to `direction`, `bearing`, and `distance`.
- Do not attempt to edit Home Assistant Recorder tables. Verify only that new state writes replace
  current attributes and that restart/reload does not restore an old address as current data.
- Unload/reload, options reload, migration from legacy config entries, and two entries at different
  coordinates must retain independent results.

### 4.6 Security and privacy

- After P03, lightning performs exactly one external-provider class of request: the configured FMI
  WFS query. No selected strike coordinate is sent to Nominatim or another service.
- Do not log configured coordinates, strike coordinates, bbox query strings, raw XML, external
  payloads, coordinate-derived identity, or arbitrary exception messages.
- Locally calculated distance, bearing, and direction may be exposed because they are the feature's
  intended output; raw coordinates are not required and remain private from entity attributes.
- Retain bounded shared aiohttp use, timeouts, 2 MiB payload ceiling, XML entity protections, and
  cancellation propagation.
- Delete Nominatim's process-global lock/timestamp, cache, timeout/user-agent/attribution constants,
  imports, executor work, tests, and documentation. Do not leave an inactive feature flag or dead
  fallback.
- Confirm the source distribution and dependency snapshot contain no Nominatim/geopy artifacts
  after dependency removal.

### 4.7 Dependency and environment policy

- Root `pyproject.toml` and `custom_components/fmi/manifest.json` own runtime direct dependencies;
  `tools/lint/pyproject.toml` owns Ruff. The three generated root hash locks remain the only lock
  files.
- Planning inventory found `geopy` is used only by lightning distance and Nominatim. S00 must
  reconfirm with repository-wide search. If true, remove `geopy==2.5.0` from both runtime manifests,
  regenerate all three locks through `make lock`, and verify the manifest/locks/dependency snapshot.
- Do not hand-edit generated locks or add `.in`, `requirements/`, another pyproject, or another venv.
- Do not add a replacement geometry package. Prefer the current supported Home Assistant local WGS84
  helper when its result/failure contract is acceptable; otherwise use one small reviewed
  standard-library math boundary with independent reference vectors.
- All project-aware commands except exact hash-locked Ruff run through the confined rootless Podman
  toolbox. Keep `PYTEST_WORKERS=auto` and xdist work-stealing for every pytest target.
- A dependency removal requires `make lock`, `make freeze-check`, `make audit`, `make licenses`,
  `make dependency-snapshot`, clean-distribution validation, and documentation updates.

### 4.8 Release and documentation policy

- Published release `1.1.0` points to the current planning commit. P03 requires a new release; never
  amend the published `1.1.0` changelog section or reuse its tag.
- Because P03 deliberately breaks address/native-state and `location` attribute consumers, the
  owner-selected release is `1.2.0` per D010. The changelog and migration guidance must make that
  accepted incompatibility prominent even though the version is not a major bump.
- The new changelog section begins with `### User-facing features`. It must explain the useful
  direction/distance and correct empty state before internal dependency/security notes.
- The changelog and user guide must clearly call out the automation migration from old address and
  `location` comparisons. Do not minimize the accepted incompatibility.
- Update current contracts in `AVAILABILITY.md`, `OPTIONAL_SOURCES.md`, `SENSORS.md`, `RUNTIME.md`,
  `COMPATIBILITY_SECURITY.md`, `DEPENDENCIES.md`, `LIVE_TESTS.md`, and `MIGRATIONS.md` only where
  actual behavior changes.
- Close/remove the three lightning TODO sections only after their acceptance criteria are proven:
  public Nominatim replacement, no-lightning availability, and local direction. Preserve the
  unrelated cryptography TODO.
- Issue #4 may be closed after the empty/failure contract is released. Issue #5 may be closed or
  answered after the owner reviews the delivered direction contract. P03 does not authorize Codex
  to post, close, label, or otherwise mutate GitHub issues.

### 4.9 Living-plan and owner-controlled Git rules

- Correct this plan immediately when current code, Home Assistant, FMI, geometry evidence, or a
  required safe design differs. Record every material correction in the session report and
  decision log.
- Do not implement directly on `master`. S00 starts only after the owner selects/creates a branch.
- Do not commit, push, tag, publish, or mutate issue state. The owner owns those actions.
- Each report contains a concise suggested checkpoint commit beginning `P03-SXX:`. Use
  `OWNER_TO_COMMIT` until the owner provides commit evidence.
- Never reset, stash, overwrite, or reformat unrelated owner work.
- A new release number or external issue action is an owner decision, not implied by permission to
  implement code.

---

## 5. Planning baseline to verify in S00

This is a read-only planning snapshot from 2026-08-18. It is not execution evidence. S00 must
remeasure it on the selected branch and write `plans/P03/BASELINE.md`.

### 5.1 Repository and release state

- Planning worktree was clean on `master` at
  `7e2ac6ce28863c9cd675b7ec3bd4bce26cee9a67`.
- `.version` and `custom_components/fmi/manifest.json` are `1.1.0`.
- GitHub Release `1.1.0` is published and its tag targets that exact commit.
- P01 and P02 are complete. P03 did not previously exist in `plans/`.
- Rootless Podman, no-bind-mount confinement, hash locks, auto-xdist, consolidated CI, bounded live
  tests, dependency submission, and release rules are current repository contracts and are not
  being redesigned by P03.

### 5.2 Current lightning data path

- Enabling the lightning option makes the primary coordinator query FMI stored query
  `fmi::observations::lightning::multipointcoverage` on its existing cadence.
- Query time range uses the configured maximum age. A square bbox is generated around the config
  entry coordinates with the configured radius as half-side.
- Parsed FMI rows contain latitude, longitude, epoch, strike count, peak current, cloud cover, and
  ellipse major size. Rows are validated for aligned arrays, finite numeric fields, coordinate
  ranges, integer/non-negative strike counts, aware time, age, and future time.
- `geopy.geodesic` calculates distance from each strike to `self.latitude/self.longitude`, which
  already comes from the owning config entry rather than Home Assistant Home.
- Up to five nearest candidates are retained, then ordered newest-first for presentation.
- The current code claims to distance-limit candidates, but planning inspection found no explicit
  `distance <= lightning_radius` rejection after bbox parsing. Square-bbox corner results can
  therefore exceed the user's nominal circular radius. S00 must reproduce this before fixing it.
- Parsing/building currently runs in the executor because it may synchronously call Nominatim.
  After removal, S00 must decide whether bounded XML parsing still belongs in the executor under the
  existing runtime contract; do not move parsing onto the event loop casually.

### 5.3 Current geocoder and entity path

- `_LightningState` stores data plus a per-coordinator coordinate/address cache and a Nominatim
  instance. A process-global lock/rate timestamp permits one public Nominatim request every 15
  seconds, with at most one new coordinate lookup per update.
- Failure or rate limiting falls back to raw strike-coordinate text.
- `FMILightningStruct` contains `location` text but does not retain raw coordinates or bearing.
- `FMILightningStrikesSensor` uses the newest retained record's `location` as native state and
  exposes it in the primary and nested `OBSERVATIONS` attributes.
- Attribution combines FMI with OpenStreetMap.
- Both `None` and `[]` make `update()` set `native_value=None` and clear attributes.
- The optional-source wrapper passes `bool`, so `[]` also marks lightning source availability
  false. The generic base entity additionally requires `native_value is not None`. As a result,
  valid empty and failed data both appear `unavailable`.

### 5.4 Current dependencies and documentation

- `geopy==2.5.0` is a direct dependency in root PEP 621 metadata and the integration manifest.
- Planning `rg` found no geopy usage outside lightning distance/Nominatim and related tests/docs.
- `DEPENDENCIES.md` describes geopy only as lightning reverse geocoding.
- `OPTIONAL_SOURCES.md`, `RUNTIME.md`, and `COMPATIBILITY_SECURITY.md` document public Nominatim,
  executor reverse geocoding, address fallback, request limits, coordinate disclosure, and accepted
  private-deployment risk.
- `SENSORS.md` documents lightning only as a generic string sensor and does not define a direction,
  bearing, empty-state, or automation schema.
- `TODO.md` has three P03-owned sections: replace public Nominatim, distinguish no lightning from
  unavailable, and provide local direction without unreliable storm prediction.

### 5.5 Existing coverage relevant to P03

- `tests/test_auxiliary_payloads.py` covers successful/malformed/empty payloads, age boundaries,
  current geodesic failure, Nominatim caching/fallback, and one-geocode-per-update behavior.
- `tests/test_availability.py` proves lightning failures do not disable current weather, but does
  not yet prove the complete empty/non-empty/failure transition matrix at entity level.
- `tests/test_lifecycle.py` asserts the old address native state and existing attributes.
- `tests/test_sensor_entities.py`, `test_compatibility_security.py`,
  `test_dependency_policy.py`, and `test_compatibility_helper.py` pin relevant metadata,
  bounding-box, dependency, and distribution contracts.
- S00 must record current test collection, coverage, exact focused results, and all lightning
  branches before editing. Do not copy counts from P02 reports.

### 5.6 Product inputs already accepted

- Issue #4 requests a valid state when FMI successfully reports no lightning.
- Issue #5 asks for direction relative to Home or a configured location and suggests a projected
  closest distance from wind.
- The owner selected the specific config entry's configured coordinates, not global Home, as the
  reference point.
- The owner selected complete Nominatim removal and local distance/bearing/direction.
- The owner accepted incompatibility for address/native-state and old `location` consumers while
  preserving entity identity and unrelated attributes.
- The owner rejected wind-based closest approach after reviewing the evidence and posted a polite
  issue response describing the proposed replacement. No issue-author acceptance is recorded in
  the planning baseline; implementation is not blocked because the repository owner fixed scope.

### 5.7 Questions S00 must close

1. Does current code demonstrably admit valid bbox corner strikes outside the configured circular
   radius, and what exact inclusive comparison fixes it?
2. Which local distance implementation best preserves current WGS84 outputs while allowing geopy
   removal: Home Assistant's supported runtime helper or a small repository-owned function?
3. What reference vectors and tolerance independently verify distance and initial bearing,
   including antimeridian, high latitude, sector boundaries, coincident points, and any
   non-convergence case?
4. Can current Home Assistant translate a stable empty-state token on a sensor that otherwise has
   dynamic composite text? What exact state does the state machine store versus the frontend show?
5. Is `42.3 km · SE` with stable compass codes the safest strike state, or does a public API permit
   full-word presentation without localized machine state? Do not use backend locale strings.
6. What exact token represents coincident coordinates without inventing a bearing?
7. Can XML parsing remain in its existing executor boundary after Nominatim removal without extra
   architectural change? The expected answer is yes unless measurement proves a reason to change.
8. Are coordinates needed only in an internal candidate/model, or must any raw coordinate survive
   parsing? The expected user contract does not expose them.
9. Is `geopy` absent from every non-lightning runtime/test path so it can be removed atomically?
10. What exact migration note communicates the accepted incompatibility for the owner-selected
    `1.2.0` release, and is it prominent before S04 modifies release metadata?
11. How will S04 perform the owner-requested one-time ad hoc live lightning check against current
    FMI observations without adding a permanent test or exceeding the existing shared twelve-attempt
    budget? Freeze a bounded search and an honest no-current-strike classification in S00.

---

## 6. Requirement closure matrix

Update status, evidence, report, and commit at every session boundary.

| ID | Required outcome | Owner | Primary evidence | Report | Commit | Status |
|---|---|---|---|---|---|---|
| R01 | Successful empty FMI lightning data is available with an explicit translated no-strikes state | S01 | coordinator and HA entity tests | `plans/P03/S01.md` | `OWNER_TO_COMMIT` | DONE |
| R02 | Failed/unusable lightning data is unavailable, clears stale state/attributes, and recovers without reload | S01/S03 | full transition matrix | `plans/P03/S03.md` | `OWNER_TO_COMMIT` | DONE |
| R03 | Every strike's distance, initial bearing, and eight-sector direction are calculated locally relative to its owning config entry | S02 | pure geometry and multi-entry tests | `plans/P03/S02.md` | `OWNER_TO_COMMIT` | DONE |
| R04 | Configured radius is enforced as an inclusive circle after the FMI bbox prefilter | S02 | boundary and bbox-corner regression tests | `plans/P03/S02.md` | `OWNER_TO_COMMIT` | DONE |
| R05 | Primary state and `OBSERVATIONS` expose the frozen direction/bearing/distance schema without raw coordinates or old `location` | S02 | parser/entity/schema tests | `plans/P03/S02.md` | `OWNER_TO_COMMIT` | DONE |
| R06 | Nominatim, OSM attribution, geocoder state/rate limiting, coordinate disclosure, and dead code/tests are completely removed; active TODO/user-document residue closes only after final proof | S02/S04 | repository/distribution searches, privacy tests, and S04 documentation/TODO audit | `plans/P03/S04.md` | `OWNER_TO_COMMIT` | DONE |
| R07 | `geopy` is removed from manifests/locks/snapshots if S00 reconfirms it has no remaining use; no replacement runtime dependency is added | S02 | lock, dependency policy, audit/license/snapshot checks | `plans/P03/S02.md` | `OWNER_TO_COMMIT` | DONE |
| R08 | Existing config/entity/device identity and customized entity IDs survive upgrade, reload, options, and multi-entry operation | S03 | migration/lifecycle/registry tests | `plans/P03/S03.md` | `OWNER_TO_COMMIT` | DONE |
| R09 | User docs, translations, maintenance contracts, changelog, TODO, and automation migration guidance match proven behavior | S04 | docs/translation/version review | `plans/P03/S04.md` | `OWNER_TO_COMMIT` | DONE |
| R10 | Full repository, supported HA, bounded live, dependency, security, distribution, and confinement gates pass with no unrelated scope | S04 | final verification matrix | `plans/P03/S04.md` | `OWNER_TO_COMMIT` | DONE |
| R11 | One bounded, non-persistent ad hoc probe finds current real FMI lightning data when available and verifies local state/attributes through the production parser/entity contract | S04 | recorded current-data probe inputs and sanitized results; no committed test | `plans/P03/S04.md` | `OWNER_TO_COMMIT` | DONE |

Status values: `NOT_STARTED`, `IN_PROGRESS`, `BLOCKED`, `DONE`.

---

## 7. Candidate risks to investigate

| Risk | Why it matters | Required handling |
|---|---|---|
| Empty list is still coerced to false | It recreates issue #4 despite an entity-only patch | Test and change the optional-source availability predicate; preserve explicit tri-state data |
| Generic base availability masks empty success | `native_value is not None` couples unrelated sensor semantics | Add lightning-specific availability while incorporating `super().available`; do not weaken other sensors |
| Stale attributes survive state change | Old address/direction can mislead after empty/failure | Replace the entire dynamic attribute mapping on every transition and assert state-machine output |
| Square bbox exceeds circular radius | Corner strikes violate the user-selected radius | Enforce inclusive calculated distance after parse; retain bbox only as query-volume prefilter |
| Distance implementation drift | Removing geopy may change visible numeric values | Compare reference vectors/current outputs, define tolerance/rounding once, and document intentional differences |
| Antimeridian/pole math | Naive longitude differences or cosine formulas can flip direction | Normalize longitude delta and test both sides of 180 degrees and high latitudes |
| Coincident strike | Bearing is undefined at zero distance | Use an explicit non-direction token/None bearing; never report arbitrary north |
| Sector boundary ambiguity | A tiny rounding change can switch direction | Use normalized unrounded bearing and documented half-open sector thresholds before presentation rounding |
| Localized composite state | Per-user translation cannot safely be baked into stored state | Prefer stable compass codes; translate only finite tokens supported by HA and test actual stored/render contract |
| Mixed textual/numeric sensor metadata | A distance device/state class conflicts with no-strikes text | Keep an honest string sensor with numeric attributes; add no incompatible state class |
| Attribute API break | Existing templates read `location` | Call out breaking migration prominently; preserve entity identity and all still-meaningful numeric fields |
| Recorder misunderstanding | Removing current attrs does not purge history | Document retention; never mutate Recorder DB; test only current state/reload behavior |
| Raw coordinate leak | Removing Nominatim does not automatically remove logs/attrs | Search source/distribution, inject invalid data, and assert logs/diagnostics/entity attrs contain no coordinates |
| Multi-entry reference mix-up | Using HA Home or another coordinator gives wrong direction | Create two entries with the same strike and assert different local direction/distance and stable identities |
| Dependency residue | Removing imports but retaining geopy leaves supply-chain and HACS drift | Change both manifests, all generated locks, tests/docs, dependency snapshot, audit/license evidence |
| Excessive live requests | A new live lightning probe can breach the shared 12-attempt contract | Prefer sanitized fixtures; add live I/O only if S00 identifies contract drift fixtures cannot detect |
| False safety semantics | Users may treat direction as a storm forecast | State and docs must say direction is point-to-strike observation only; exclude trend/arrival/closest approach |
| Upstream FMI shape drift | Parser assumptions may change independently | Keep strict aligned-array validation and use existing bounded live/failure classification without weakening safety |

S00 may add risks. Do not remove a risk without recorded evidence that closes or supersedes it.

---

## 8. Required test architecture

### 8.1 Pure geometry and parser tests

Cover with independent expected values, not expectations calculated by the function under test:

- cardinal and intercardinal reference bearings;
- every sector boundary just below, exactly at, and just above the threshold;
- longitude wrapping across `+180/-180` in both directions;
- high northern/southern latitude pairs and geographic poles;
- coincident coordinates;
- invalid ranges, booleans if accepted by Python numeric coercion, NaN, and infinities;
- distance zero, exactly radius, just within radius, just outside radius, and a bbox-corner point;
- current visible distance rounding compatibility on ordinary Finnish points;
- parser ordering: five nearest retained, then newest presented first;
- empty arrays, malformed aligned rows, unequal arrays, invalid timestamps, and mixed valid/invalid
  rows under the new model;
- no network call, geocoder/cache mutation, or raw-coordinate output during parsing.

Use authoritative published coordinate/reference vectors or independently precomputed values with
documented source/tolerance. Do not compare one implementation to a copy of itself.

### 8.2 Coordinator source-state tests

Prove at least these startup and refresh cases:

| Previous source state | New result | Required source/entity result |
|---|---|---|
| none/startup | empty success | available explicit no-strikes; empty dynamic attrs |
| none/startup | non-empty success | available direction-distance state and full current attrs |
| none/startup | failure | unavailable; empty attrs; primary source still independent |
| empty | non-empty | recover/update without reload |
| non-empty | empty | available no-strikes; every old strike attr cleared |
| empty | failure | unavailable; no stale empty/strike attrs presented as current data |
| non-empty | failure | unavailable; no old strike state/attrs retained |
| failure | empty | available no-strikes without reload; one recovery transition log |
| failure | non-empty | available strike without reload; one recovery transition log |
| non-empty A | non-empty B | all primary/nested fields replaced, not merged with A |

Also prove repeated failure does not spam transition warnings, repeated empty success remains
available, and an optional lightning outcome never changes current/forecast/station/sea-level
availability.

### 8.3 Home Assistant entity, registry, and lifecycle tests

Cover through public setup/entity APIs:

- exact native/state-machine values and attributes for empty, non-empty, and failed sources;
- translations for the empty state in source strings, English, and Finnish under the supported HA
  test environment;
- no OSM attribution after the cutover; FMI attribution remains;
- existing entity registry record, unique ID, customized entity ID, disabled/enabled state, device,
  and config entry survive setup/reload/options updates;
- realistic legacy/current registry fixtures load without config-entry migration;
- two simultaneous entries calculate the same strike relative to their own stored coordinates;
- unload/reload removes listeners and does not resurrect Recorder/current address data;
- disabling lightning removes the entity through the existing options reload contract without
  affecting unrelated entities;
- updated extra attributes contain no `location`, latitude, longitude, address, or raw coordinates;
- `OBSERVATIONS` contains the same stable field schema for every retained secondary group.

### 8.4 Privacy, dependency, and distribution tests

Prove:

- source contains no `Nominatim`, `GeocoderServiceError`, Nominatim URL/user agent/rate state, or OSM
  attribution outside historical P01/P02/P03 execution records where history requires it;
- the distributed integration contains no Nominatim/geopy import or stale metadata;
- coordinator/parser/entity logs and diagnostics contain no exact configured/strike coordinates or
  query URLs after injected failures;
- root PEP 621 dependencies, integration manifest, runtime/dev/lint locks, compatibility helper,
  dependency policy tests, SBOM/dependency snapshot, audit, and license inventory agree;
- no new runtime package replaces geopy;
- clean HACS/manual distribution and hassfest validation still pass.

Historical plans may truthfully mention the old dependency/service and must not be rewritten. Search
acceptance should distinguish those historical records from current code/docs/distribution.

### 8.5 Live and compatibility testing

- Ordinary P03 tests remain deterministic and socket-blocked.
- The existing bounded live suite must keep auto-xdist, shared 12-attempt maximum, and two-request
  semaphore unless S00 records and justifies an exact change.
- Do not add a permanent live lightning test merely to test geometry or empty state; fixtures cover
  those better.
- In S04, perform one owner-requested ad hoc marked-live check that is not retained in the test
  suite. Within the existing shared twelve-attempt ceiling, query current FMI lightning
  observations using only public, non-owner coordinates/bounding areas, select an actual recent
  strike group when one is available, and pass the response through the production parser and
  entity presentation contract. Independently verify the selected result's distance, bearing,
  direction sector, formatted state, radius inclusion, and absence of raw coordinates/legacy
  `location` in attributes.
- The ad hoc check must use the existing bounded aiohttp/time/payload protections and be recorded
  with sanitized inputs/results in `S04.md`; do not commit its temporary test/script or a raw FMI
  payload. Production continues to use Home Assistant's shared session. If the HA test harness's
  cached shared session is bound to a different event loop, the temporary probe may use a
  dedicated SSL-verifying aiohttp session with a current-loop threaded resolver; Home Assistant's
  session factory cannot replace its cached connector. This exception changes neither runtime code
  nor its shared-session contract.
  If the bounded current search finds no qualifying strike because weather is quiet or FMI is
  unavailable, record the exact attempt/classification honestly and do not weaken deterministic
  acceptance tests or fabricate a live success.
- Run current stable compatibility as required. Prerelease remains informational and must not become
  a support claim.

### 8.6 Coverage and assertion quality

- Keep the repository coverage gate at 95% or higher and compare against the S00-measured baseline.
- Every new failure branch, geometry edge, source transition, and compatibility boundary needs
  proportionate coverage.
- Do not add exclusions, broad ignores, `noqa`, xfail, sleeps, serial defaults, retry plugins, or
  weaker assertions merely to turn a result green.
- Every pytest target retains `PYTEST_WORKERS=auto` and `--dist=worksteal`; fixed workers are
  diagnostic overrides only.

---

## 9. CI and repository quality target

P03 should need no new workflow or permission. Use the existing consolidated CI and trusted
dependency-submission topology.

Required local target set across sessions:

- `make doctor`
- `make dev-build`
- `make format-check`
- `make lint`
- `make type-check`
- `make test-fast`
- `make test-full`
- `make test-network-block`
- `make validate`
- `make version-check`
- `make bandit`
- `make syntax`
- `make shellcheck`
- `make confinement-test`
- `make live`
- `make compatibility-stable`
- `make compatibility-prerelease` (informational; classify accurately)
- `make audit`
- `make licenses`
- `make freeze-check`
- `make dependency-snapshot`
- `make check` and `make ci` at final verification
- `git diff --check`, final status, and complete diff review

Only run dependency regeneration in the session that owns manifest removal. `make audit-raw` may
remain nonzero only for the exact owner-approved Home Assistant cryptography exception documented
outside P03; no new P03 exception is permitted.

CI acceptance:

- offline coverage, bounded live FMI, validation, dependency risk, CodeQL, stable compatibility,
  release version, and all existing required check identities remain intact;
- prerelease compatibility remains informational;
- dependency submission on trusted direct `master` push must receive the regenerated graph after
  merge; local `make dependency-snapshot` proves content before then;
- no workflow permission, mutable action reference, inline dependency pin, or network contour is
  broadened for P03 without a reproduced blocker and plan correction.

---

## 10. Session tracker

Update this table at the start and end of each execution session.

| Session | Objective | Prerequisites | Report | Commit | Status |
|---|---|---|---|---|---|
| S00 | Verify baseline, freeze state/geometry/release contracts, and add characterization evidence | Owner-selected non-master branch | `plans/P03/BASELINE.md`; `plans/P03/S00.md` | `OWNER_TO_COMMIT` | DONE |
| S01 | Implement truthful empty/failure/non-empty availability and stale clearing without changing address presentation yet | S00 DONE | `plans/P03/S01.md` | `OWNER_TO_COMMIT` | DONE |
| S02 | Cut over atomically to local distance/bearing/direction, exact radius, and remove Nominatim/geopy | S01 DONE | `plans/P03/S02.md` | `OWNER_TO_COMMIT` | DONE |
| S03 | Prove registry/lifecycle/multi-entry/privacy/recovery compatibility and close confirmed gaps | S02 DONE | `plans/P03/S03.md` | `OWNER_TO_COMMIT` | DONE |
| S04 | Finalize translations/docs/release/TODO and run complete release verification | S03 DONE | `plans/P03/S04.md` | `OWNER_TO_COMMIT` | DONE |

The plan is complete only when every session and R01-R11 are `DONE`.

---

## 11. Standard session protocol

### 11.1 Start of session

1. Read `AGENTS.md`, this plan, the previous P03 report, and the smallest relevant maintenance docs.
2. Inspect branch, commit, status, untracked files, and unrelated owner changes.
3. Confirm all prerequisites are `DONE` and set the current session `IN_PROGRESS`.
4. Reproduce or characterize the session's behavior before editing.
5. Update plan text immediately, before continuing affected work, if reality differs or execution
   deliberately departs from a recorded instruction.

### 11.2 During session

1. Add failing/characterization tests before behavior where practical.
2. Keep changes inside the owning scope.
3. Run focused tests after each coherent change through supported Make/container paths.
4. Preserve unrelated work and never use destructive Git recovery.
5. Record decisions and deviations while evidence is fresh.
6. Do not say a command passed unless that exact invocation completed successfully.

### 11.3 End of session

1. Run every listed session gate.
2. Review the complete session diff and `git diff --check`.
3. Update requirement rows, decision log, tracker, and plan status honestly.
4. Write `plans/P03/SXX.md` using the template below.
5. Include one `P03-SXX: ...` suggested owner commit without committing.
6. Mark `DONE` only if exit criteria pass; otherwise leave `IN_PROGRESS` or `BLOCKED` with exact
   evidence and safe next action.

---

## 12. Detailed session specifications

## Session S00 — Verified baseline and frozen contracts

### Objective

Turn the planning snapshot into reproducible execution evidence and close every design question
that could otherwise cause a second user-facing rewrite.

### Required work

1. Confirm a non-master execution branch, starting commit, clean/dirty ownership, and selected
   release version. Record the owner's version decision; do not alter metadata in S00 unless
   characterization requires no other behavior change.
2. Read current lightning coordinator, parser, entity, options, registry, diagnostics, dependency,
   Make, CI, docs, and all relevant tests.
3. Create `plans/P03/BASELINE.md` with exact code paths, data flow, state/attribute samples,
   dependency inventory, test count/coverage, supported HA version, and current docs.
4. Add/confirm characterization tests for current `None`, `[]`, non-empty, failure, ordering,
   Nominatim fallback, stale clearing, and entity identity behavior without blessing defects.
5. Reproduce the square-bbox/circular-radius discrepancy with a deterministic corner candidate.
6. Compare `geopy.geodesic`, Home Assistant's supported local WGS84 helper, and an independent
   trusted reference set for ordinary, antimeridian, polar, and coincident points. Freeze distance
   function, units, rounding, failure, and tolerances in D004.
7. Freeze bearing normalization, sector boundary table, direction tokens, coincident representation,
   and internal coordinate lifetime in D005.
8. Build a minimal Home Assistant test/experiment for state translations and dynamic composite
   values. Freeze exact stored strike state, empty token, frontend translation expectation, and
   English/Finnish requirements in D006.
9. Confirm exact primary and `OBSERVATIONS` schemas, removed fields, preserved fields, Recorder
   boundary, and automation migration examples.
10. Reconfirm `geopy` has no remaining non-P03 use and document all files/locks/snapshots affected
    by removal.
11. Decide whether any live request is necessary. Default to no budget change; record evidence.
12. Recheck issue #5 only for new maintainer feedback. Do not expand scope or mutate the issue.
13. Update this plan/decision/risk/requirement text for every verified discrepancy.
14. Write `plans/P03/S00.md` with evidence and `P03-S00: freeze lightning state and geometry contracts`.

### Verification

- focused current lightning parser/entity/availability/lifecycle tests;
- new characterization/geometry reference tests;
- translation experiment under the locked Home Assistant environment;
- `make format-check`;
- `make lint`;
- `make type-check`;
- `make test-fast`;
- `make version-check`;
- `git diff --check`.

### Exit criteria

- `BASELINE.md` and S00 report contain reproducible evidence, not planning assumptions.
- Release version and execution branch are owner-confirmed.
- Exact state, empty token, attribute schema, distance implementation, bearing/sector/collision rules,
  radius semantics, dependency removal, and live budget are frozen.
- Characterization tests are green and known defects are explicitly marked for S01/S02.
- No production behavior changed unintentionally.

### Do not do

- Do not remove Nominatim/geopy before geometry/state contracts are frozen.
- Do not use a live lightning occurrence as a deterministic geometry fixture.
- Do not make issue-author response a hidden blocker after the owner fixed scope.

## Session S01 — Truthful source state and availability

### Objective

Fix issue #4 and the coordinator/entity stale-data contract while leaving the address-to-direction
presentation cutover for S02.

### Required work

1. Replace the lightning optional-source truthiness predicate with explicit successful-empty versus
   failed-source semantics.
2. Add lightning-specific entity availability that incorporates coordinator success/source validity
   without weakening the generic rule for other sensors.
3. Implement the S00-frozen explicit empty native state and translated empty token.
4. Ensure a successful empty update clears the complete prior strike attribute mapping but remains
   available.
5. Ensure a failure clears prior state/attributes and remains unavailable while primary and other
   optional sources continue.
6. Prove all transitions in section 8.2 at coordinator and HA state-machine level, including
   transition-based logs and recovery without reload.
7. Test startup, periodic refresh, options reload, unload/reload, and two independent entries for
   state isolation.
8. Keep the existing Nominatim address presentation temporarily for non-empty results so S01 has one
   coherent concern. Do not document this intermediate state as final.
9. Update `AVAILABILITY.md` only if it can truthfully describe a stable contract that will remain
   after S02; otherwise record the pending doc change for S04.
10. Update requirement rows/decision log and write `plans/P03/S01.md` with
    `P03-S01: distinguish empty lightning data from source failures`.

### Verification

- focused auxiliary payload, availability, sensor entity, lifecycle, and transition tests;
- `make format-check`;
- `make lint`;
- `make type-check`;
- `make test-full`;
- `make test-network-block`;
- `make validate` when translation files change;
- `git diff --check`.

### Exit criteria

- R01 is `DONE`; the S01-owned part of R02 is proven.
- Empty success, failure, and recovery are unambiguous and stale-free.
- No unrelated source/entity availability changed.
- S01 report is complete and the tree is green for S02.

### Do not do

- Do not use `bool(data)` for lightning availability.
- Do not represent empty success as `None`, `unknown`, `unavailable`, empty string, or numeric zero.
- Do not start the user-visible address/direction cutover partially.

## Session S02 — Local geometry, schema cutover, and dependency removal

### Objective

Atomically replace address enrichment with the frozen local direction contract, enforce the true
radius, and remove every now-dead service/dependency surface.

### Required work

1. Implement one pure typed geometry boundary using the S00-selected distance method plus initial
   bearing/direction calculation.
2. Add the complete independent geometry edge suite and reject invalid/non-finite rows without
   coordinate-bearing logs.
3. Enforce inclusive circular radius after local distance calculation while retaining the FMI bbox
   as a request prefilter.
4. Extend/refactor the internal candidate/final lightning model with only fields needed for state:
   direction token, bearing, distance, time, and existing FMI observations. Keep raw coordinates
   internal and ephemeral.
5. Format the exact S00-frozen non-empty native state and primary/nested attribute schema.
6. Remove `location` from primary and `OBSERVATIONS`; retain time, distance, strikes, peak current,
   cloud cover, ellipse major, and list ordering.
7. Delete Nominatim calls, cache, rate limiter, lock/time globals, imports, constants, fallbacks,
   exceptions, tests, and OpenStreetMap attribution. Retain FMI attribution.
8. Remove geopy from root `pyproject.toml` and integration manifest after final repository-wide
   confirmation. Regenerate locks with `make lock`; do not hand-edit them.
9. Update dependency/compatibility tests and compatibility helper to assert the smaller runtime
   graph. Generate and inspect dependency snapshots.
10. Search current code/distribution and maintenance contracts for residue, distinguishing
    immutable historical plan evidence from active contracts. User-facing docs and the accepted
    Nominatim TODO were explicitly reserved for S04, so S02 left R06 `IN_PROGRESS` until that final
    proof; S04 has now closed it without reopening S02 runtime work.
11. Run audit/license/freeze/distribution validation and classify the existing approved upstream
    cryptography finding without creating a P03 exception.
12. Update requirement rows/decisions and write `plans/P03/S02.md` with
    `P03-S02: replace lightning geocoding with local direction geometry`.

### Verification

- all geometry, parser, sensor, lifecycle, compatibility-security, dependency-policy, and clean
  distribution tests;
- `make lock`;
- `make freeze-check`;
- `make format-check`;
- `make lint`;
- `make type-check`;
- `make bandit`;
- `make test-full`;
- `make test-network-block`;
- `make validate`;
- `make audit`;
- `make licenses`;
- `make dependency-snapshot` and review all three manifests;
- `git diff --check` and active-surface residue search.

### Exit criteria

- At the S02 boundary, R03-R05 and R07 were `DONE` with exact evidence, the runtime/code portion of
  R06 was proven, and only the S04-owned user-document/TODO closure remained. S04 has now completed
  that closure and R06 is `DONE`.
- No runtime request can reach Nominatim and no raw strike coordinate is exposed.
- The configured radius is a real inclusive circle.
- State/schema match S00, all retained records have consistent direction/bearing/distance, and no
  stale `location` survives a write.
- Runtime dependency graph no longer contains geopy and no replacement was added.
- S02 report is complete and the dependency diff is fully reviewed.

### Do not do

- Do not leave a disabled geocoder path, compatibility flag, or old field populated with a new
  meaning.
- Do not derive movement, trend, or safety predictions from bearing.
- Do not expose raw strike or config-entry coordinates to make debugging easier.

## Session S03 — Compatibility, lifecycle, recovery, and privacy audit

### Objective

Exercise the complete new behavior through Home Assistant public APIs, fix only reproduced gaps,
and prove that the accepted value/schema incompatibility does not become an identity or isolation
regression.

### Required work

1. Run the full transition matrix through loaded Home Assistant entities, not parser objects alone.
2. Verify current entries and realistic legacy registry fixtures retain config-entry version/data,
   entity/device unique IDs, customized entity IDs, enabled state, device attachment, and options.
3. Exercise setup, reload, options updates, disable/re-enable lightning, unload, and restart-like
   re-setup. Prove old current attributes do not resurrect.
4. Exercise at least two entries at different configured coordinates against the same strike and
   prove each uses its own coordinator point.
5. Verify optional source isolation across current weather, forecasts, configured observation,
   lightning, and sea-level for empty, malformed, timeout, and recovery cases.
6. Inject all documented parser/geometry/transport failures and verify cancellation propagation,
   bounded errors, transition logs, and no stale data.
7. Audit logs, diagnostics, entity states/attributes, generated reports, and clean distribution for
   exact coordinates, query URLs, raw payloads, Nominatim/OSM/geopy residue, and arbitrary external
   exception messages.
8. Confirm Recorder boundary by state-machine/reload behavior and documentation; do not access or
   mutate user database tables.
9. Run the existing bounded live suite. If it fails, classify upstream outage versus regression
   before modifying any assertion. Run stable compatibility and record prerelease signal
   accurately.
10. Fix every confirmed P03-owned critical/high correctness, identity, lifecycle, privacy, or
    compatibility defect; split larger discoveries instead of absorbing unrelated work.
11. Update stable maintenance contracts only when the final behavior is now proven.
12. Update requirements/decisions and write `plans/P03/S03.md` with
    `P03-S03: prove lightning lifecycle identity and privacy contracts`.

### Verification

- complete auxiliary payload, availability, lifecycle, migration, diagnostics, sensor, dependency,
  compatibility-security, and network-block tests;
- `make format-check`;
- `make lint`;
- `make type-check`;
- `make test-full`;
- `make test-network-block`;
- `make validate`;
- `make version-check`;
- `make live`;
- `make compatibility-stable`;
- `make compatibility-prerelease` with informational classification;
- `git diff --check`.

### Exit criteria

- R02 and R08 are `DONE`; R01-R08 have report-backed evidence.
- Identity and entry isolation are unchanged despite the accepted state/schema break.
- No known P03-owned critical/high defect or privacy leak remains.
- Existing live budget and source isolation remain valid, or a plan-approved exact change is proven.
- S03 report is complete.

### Do not do

- Do not weaken live assertions during an FMI outage.
- Do not hide broad exceptions, cancellation, or stale data to keep the coordinator green.
- Do not rewrite unrelated migrations or registries for cleanliness.

## Session S04 — Documentation, release, TODO closure, and final verification

### Objective

Make the new contract explicit to users and future maintainers, synchronize the owner-confirmed
release, remove completed TODOs, and prove release readiness with every required gate.

### Required work

1. Review the complete P03 diff, baseline, reports, decisions, and requirement evidence.
2. Update `docs/USER_GUIDE.md` with direction/distance meaning, reference point, empty versus
   unavailable, attributes, absence of storm prediction, and automation migration.
3. Update current contracts in `AVAILABILITY.md`, `OPTIONAL_SOURCES.md`, `SENSORS.md`, `RUNTIME.md`,
   `COMPATIBILITY_SECURITY.md`, `DEPENDENCIES.md`, `LIVE_TESTS.md`, and `MIGRATIONS.md` where their
   existing statements changed. Remove current Nominatim/OSM/geopy risk text rather than retaining
   obsolete advice.
4. Audit `strings.json`, English, and Finnish translation parity and run HA validation.
5. Set `.version` to the owner-confirmed release, synchronize manifest, and create one matching dated
   changelog section. Never alter published `1.1.0` history.
6. Begin the release section with `### User-facing features`: correct empty state and local
   direction/distance first. Follow with compatibility migration, privacy/security, dependency,
   and internal fixes in appropriate sections.
7. Explain prominently that address/native-state and `location` template consumers must migrate to
   direction/bearing/distance; entity IDs and registry customization remain.
8. Remove the three completed lightning sections from `TODO.md` only after their acceptance criteria
   are proven. Preserve the unrelated cryptography item and any non-P03 work.
9. Update `AGENTS.md` only if a durable development/documentation rule changed; do not add P03
    progress narration to it.
10. Run the bounded, non-persistent ad hoc current-FMI lightning check defined in section 8.5 and
    record its sanitized evidence without committing a temporary probe or raw response.
11. Run every final gate below, inspect generated artifacts, and review the entire diff for unrelated
    change, dead code, stale docs, and release consistency.
12. Update R09-R11, all session rows, decisions, and plan status to `DONE` only after the final
    matrix passes.
13. Write `plans/P03/S04.md` with remaining limitations and
    `P03-S04: release reliable local lightning direction and availability`.

### Verification

- `make doctor`
- `make dev-build`
- `make lock` only if S02 locks require final regeneration
- `make freeze-check`
- `make format-check`
- `make lint`
- `make type-check`
- `make bandit`
- `make syntax`
- `make shellcheck`
- `make test-fast`
- `make test-full`
- `make test-network-block`
- `make confinement-test`
- `make validate`
- `make version-check`
- `make live`
- `make compatibility-stable`
- `make compatibility-prerelease` (informational result recorded accurately)
- `make audit`
- `make licenses`
- `make dependency-snapshot`
- `make check`
- `make ci`
- `git diff --check`
- final `git status --short`, dependency/distribution searches, and complete diff review

### Exit criteria

- R01-R11 and S00-S04 are `DONE`.
- User-visible state, translations, attributes, docs, TODO, dependencies, and release records match
  tested code.
- Every required supported-environment gate passes; informational/upstream signals are classified
  rather than hidden.
- No Nominatim/geopy/current-location residue, storm prediction, raw coordinate output, unrelated
  refactor, or dead code remains.
- `plans/P03/` contains the canonical plan, verified baseline, and all reports.

### Do not do

- Do not close GitHub issues, push, tag, or publish; provide the owner with suggested text/status.
- Do not remove TODOs on the strength of code alone before docs and final gates pass.
- Do not claim P03 predicts storm movement or improves lightning safety.

---

## 13. Execution report template

Every session report at `plans/P03/SXX.md` must use:

```markdown
<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# P03 Session SXX Report

## Metadata

- Date/time:
- Starting branch/commit:
- Ending commit: OWNER_TO_COMMIT
- Working tree at start:
- Suggested owner commit: `P03-SXX: ...`
- Status: DONE | IN_PROGRESS | BLOCKED

## Objective

One paragraph matching the owning session.

## Baseline and evidence

- Relevant code/API behavior verified before change.
- External references and access dates.
- Reproduction or characterization result.

## Changes made

- Behavioral and structural changes.
- Plan or contract corrections.

## Decisions

- Decision IDs added/updated.
- Alternatives rejected and evidence.

## Tests and checks run

| Command/check | Result | Evidence/notes |
|---|---|---|

Never mark PASS unless that exact command completed successfully.

## Files materially changed

- Paths and reasons, not a raw inventory.

## Requirement mapping

- RXX: status and evidence.

## Remaining risks or blockers

- Precise unresolved items, or `None within this session`.

## Instructions for the next session

- Preconditions, exact objective, and facts that must not be rediscovered.
```

Keep `PLAN.md`, S00-owned `BASELINE.md`, and all session reports together under `plans/P03/`.

---

## 14. Decision log

Update this table when execution evidence changes a decision.

| ID | Owner/session | Date | Decision | Rejected alternatives | Rationale/evidence | Status |
|---|---|---|---|---|---|---|
| D001 | Owner/P03 | 2026-08-18 | Use each specific FMI config entry's stored coordinates as the lightning reference point | Global Home coordinates; selectable second reference | The sensor belongs to that configured location; reconfiguration already updates its source point and entries must remain independent | ACCEPTED |
| D002 | Owner/P03 | 2026-08-18 | Remove Nominatim completely and replace address/raw-coordinate presentation with local direction, bearing, and distance | Keep best-effort address; another geocoder/proxy; raw coordinates | Removes external policy/availability/privacy surface and better answers the user's actual question | ACCEPTED |
| D003 | Owner/P03 | 2026-08-18 | Accept incompatibility for old address/native-state and `location` consumers while preserving registry/entity identity and valid numeric observation fields | Retain misleading alias forever; create a duplicate entity | The new contract is more useful and private; a documented automation migration is acceptable, but entity recreation is not | ACCEPTED |
| D004 | S00/P03 | 2026-08-19 | Use `homeassistant.util.location.distance` (local WGS84 Vincenty metres); reject its `None` non-convergence result; store kilometers rounded to two decimals; format state distance with one decimal; include candidates whose unrounded metre result is `<= radius_km * 1000` | Keep geopy; add geometry dependency; copy an ellipsoid solver | HA 2026.8.1 matched GeographicLib/geopy within one millimetre for ordinary, antimeridian, high-latitude, and coincident vectors; antipodal non-convergence is explicit and far outside supported radius | ACCEPTED |
| D005 | S00/P03 | 2026-08-19 | Calculate spherical initial bearing with normalized longitude delta, normalize to `[0, 360)`, round the published bearing to one decimal after selecting a half-open eight-sector bucket, and use `bearing=None`, `direction="here"` for coincident points | Undefined thresholds; arbitrary north at zero distance; duplicate a full ellipsoidal inverse solver | One pure standard-library bearing boundary is network-free and deterministic; sectors are `[337.5, 22.5)` N then 45-degree half-open buckets clockwise, while coincidence has no honest bearing | ACCEPTED |
| D006 | S00/P03 | 2026-08-19 | Store `no_strikes` for successful empty data and provide English `No lightning strikes` / Finnish `Ei salamaniskuja` state translations; originally store strike state as `{DIRECTION} · {distance:.1f} km` (for coincidence, `HERE · 0.0 km`) without backend localization | Backend-localized composite state; `None`; numeric sentinel; distance device class | HA state translations support finite exact tokens on unique-ID entities, while arbitrary dynamic composites remain raw; the sensor therefore stays textual with no state class/device class | SUPERSEDED IN PART BY D014 |
| D007 | Owner/P03 | 2026-08-18 | Do not calculate storm movement/closest approach from wind; reconsider only with authoritative FMI motion data in a separate plan | Surface-wind projection; single-strike extrapolation | NWS/NOAA evidence shows storm propagation differs from mean wind and operational motion requires tracking features across radar frames | ACCEPTED |
| D008 | S00/P03 | 2026-08-19 | Enforce the configured lightning radius as an inclusive circle after the square FMI bbox prefilter | Treat square bbox half-side as radius; silently keep corner points | A deterministic 200 km bbox-corner characterization exceeds 200 km from the configured point, and current parser code contains no post-distance radius comparison | ACCEPTED |
| D009 | S00/P03 | 2026-08-19 | Remove geopy entirely with Nominatim and regenerate every owned lock/snapshot | Leave unused direct dependency; replace it | Repository-wide active-surface search found geopy only in lightning distance/geocoding, dependency metadata, their tests, and current documentation | ACCEPTED |
| D010 | Owner/P03 | 2026-08-19 | Release P03 as `1.2.0` after published `1.1.0` | Recommended `2.0.0`; amend/reuse `1.1.0` | The owner explicitly selected `1.2.0`; changelog and migration guidance must still state the accepted native-state and attribute incompatibility clearly | ACCEPTED |
| D011 | Plan/P03 | 2026-08-18 | Do not delete Recorder history; replace only current state/attrs on refresh and document retention | Database migration/purge | Recorder ownership/retention belongs to Home Assistant/user, and P03 needs no persisted integration migration | ACCEPTED |
| D012 | Owner/P03 | 2026-08-19 | Keep deterministic lightning coverage offline, but perform one bounded non-persistent ad hoc current-data check in S04 | Add a permanent weather-dependent test; skip all real non-empty lightning evidence | The owner explicitly requested one end-to-end calculation/presentation check using actual current FMI strike data while keeping the normal suite deterministic | ACCEPTED |
| D013 | S04/P03 | 2026-08-19 | Permit only the temporary ad hoc probe to use a dedicated SSL-verifying aiohttp session with a current-loop threaded DNS resolver when the test fixture's cached shared session is cross-loop | Change production session ownership; bypass bounded production fetch; abandon live evidence | Two probe attempts failed before FMI I/O completed with `Future attached to a different loop`, and HA's factory rejected a replacement connector; offline/runtime tests already prove unchanged production shared-session ownership, while the harness-only session still passes through the exact production timeout, size, parser, and request-budget boundaries | ACCEPTED |
| D014 | Maintenance/P03 follow-up | 2026-08-19 | Present non-empty state as `{distance:.1f} km · {DIRECTION}` and coincidence as `0.0 km · HERE`; attributes and all other semantics remain unchanged | Retain direction-first state; localize the composite; change attribute schema | Distance is the primary measured value and reads more naturally first; this improves scan order without changing machine-readable attributes or entity identity | ACCEPTED |

---

## 15. Final definition of done

P03 is complete only when every statement below is true.

### User-visible truthfulness

- Valid empty FMI lightning data is available and displays an explicit translated no-strikes state.
- Real source/payload failure is unavailable and never retains an old strike.
- A strike displays the frozen local distance-and-direction state.
- `direction`, `bearing`, and `distance` are stable automation-facing attributes for primary and
  nested observations.
- Direction means configured-point-to-strike initial bearing only, never storm motion.

### Geometry and source correctness

- Every result uses the owning config entry's coordinates, including multiple entries.
- Distance/bearing/sector logic is finite, normalized, independently tested, and deterministic at
  boundaries, antimeridian, poles, and coincidence.
- Configured radius is enforced as an inclusive circle after bbox prefiltering.
- Empty, non-empty, malformed, failure, and recovery transitions are fully covered.
- Ordering, age, limit, and retained FMI observation meanings remain documented and tested.

### Compatibility and privacy

- Existing config, options, entity/device registry records, unique IDs, customized entity IDs, and
  lifecycle remain intact without a config-entry migration.
- The accepted address/`location` API break has a prominent automation migration example.
- Current entity state/attrs never expose raw strike/config coordinates or retain an old address.
- No Nominatim/other geocoder request, state, policy risk, attribution, cache, or dead fallback
  remains.
- Recorder history is neither rewritten nor misrepresented as current state.
- No storm path, arrival, closest approach, or safety claim is exposed.

### Dependencies, tests, and quality

- Geopy is absent from runtime manifests, generated locks, dependency snapshot, compatibility
  helpers/tests, current docs, and distributed integration if S00 confirms D009.
- No new runtime geometry/geocoder dependency was added.
- Offline, full coverage, network block, lint, types, security, validation, confinement, live,
  stable compatibility, audit, licenses, locks, snapshots, and distribution gates pass.
- One bounded non-persistent S04 probe has attempted to select actual current FMI lightning data and
  verify production distance/bearing/direction/state output; its sanitized result or honest
  no-current-strike/upstream classification is recorded without retaining a test or raw payload.
- Prerelease compatibility is recorded accurately as informational.
- Coverage remains at/above gate without suppressions or assertion weakening.
- Every pytest target remains auto-xdist/work-steal and live limits remain bounded.

### Documentation and release

- User guide and every owning maintenance contract match actual code.
- Source strings, English, and Finnish translations are structurally and semantically aligned.
- The new release has synchronized `.version`, manifest, and dated changelog section after
  published `1.1.0`.
- User-facing lightning benefits are the first changelog block; incompatibility is explicit.
- The three P03 lightning TODO sections are removed only after completion; unrelated TODO remains.
- `plans/P03/` contains its plan, verified baseline, and S00-S04 reports.

### Scope discipline

- No wind-based storm forecast, radar tracking, alternate geocoder, raw-coordinate display, new
  configuration mode, unrelated refactor, or CI redesign entered P03.
- Historical P01/P02 records were not rewritten to pretend the old service never existed.
- No commit, tag, release, push, or GitHub issue mutation was performed by Codex.

---

## 16. Authoritative references to recheck

Record exact access dates in the executing report.

### Repository contracts and requests

- Agent guide: `AGENTS.md`
- TODO acceptance inputs: `TODO.md`
- Availability: `docs/maintenance/AVAILABILITY.md`
- Optional sources: `docs/maintenance/OPTIONAL_SOURCES.md`
- Sensors: `docs/maintenance/SENSORS.md`
- Runtime: `docs/maintenance/RUNTIME.md`
- Compatibility/security/privacy: `docs/maintenance/COMPATIBILITY_SECURITY.md`
- Dependencies: `docs/maintenance/DEPENDENCIES.md`
- Migration/registry: `docs/maintenance/MIGRATIONS.md`
- Live budget: `docs/maintenance/LIVE_TESTS.md`
- Development and release: `docs/maintenance/DEVELOPMENT.md`,
  `docs/maintenance/HACS_RELEASES.md`
- Issue #4: <https://github.com/kogeler/fmi-hass-custom/issues/4>
- Issue #5 and owner proposal: <https://github.com/kogeler/fmi-hass-custom/issues/5>

### Home Assistant

- Sensor entity/native value/attributes:
  <https://developers.home-assistant.io/docs/core/entity/sensor/>
- Entity availability rule:
  <https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/entity-unavailable/>
- Entity state translations:
  <https://developers.home-assistant.io/blog/2022/12/01/entity_translations/>
- Entity naming and lifecycle: <https://developers.home-assistant.io/docs/core/entity/>
- Entity registry: <https://developers.home-assistant.io/docs/entity_registry_index/>
- Async blocking operations:
  <https://developers.home-assistant.io/docs/asyncio_blocking_operations/>
- Exact `homeassistant.util.location` implementation from the S00-supported HA tag; it is candidate
  implementation evidence, not a version-independent promise.

### FMI

- FMI WFS stored queries, limits, and discovery:
  <https://en.ilmatieteenlaitos.fi/open-data-manual-fmi-wfs-services>
- FMI WFS examples and parameter guidance:
  <https://en.ilmatieteenlaitos.fi/open-data-manual-wfs-examples-and-guidelines>
- FMI open-data changelog: <https://en.ilmatieteenlaitos.fi/open-data-changelog>
- FMI lightning detection background:
  <https://en.ilmatieteenlaitos.fi/thunderstorms-in-finland>
- Exact `DescribeStoredQueries` result for
  `fmi::observations::lightning::multipointcoverage` captured/summarized without private data in
  S00 if query-shape verification is needed.

### Storm-motion safety boundary

- National Weather Service multicell definition: storm-area motion may deviate significantly from
  mean wind because of new-cell propagation:
  <https://forecast.weather.gov/glossary.php?word=multicell>
- National Weather Service spotter guidance, including non-intuitive storm motion and
  back-building:
  <https://www.weather.gov/spotterguide/types>
- NOAA AWIPS Distance/Time/Motion training: operational motion is obtained by following a feature
  over multiple radar frames, with warnings about noisy two-position tracks:
  <https://vlab.noaa.gov/web/oclo/awipsfundamentals?page=distancetimemotion>

---

## 17. Owner review checkpoints

The plan fixes the product direction, but these outputs require owner review before merge:

1. **Before S00:** select a non-master execution branch.
2. **S00:** record the owner-selected `1.2.0` release, exact strike/empty state examples,
   coincident representation, attribute migration table, and no-new-permanent-live-test decision.
3. **S01:** inspect the visible valid-empty versus unavailable behavior and translations.
4. **S02:** inspect direction/distance output, radius boundary, removed address/location fields,
   geopy lock diff, and proof of no Nominatim/raw-coordinate traffic.
5. **S03:** inspect registry/multi-entry/privacy/recovery evidence and compatibility classification.
6. **S04:** approve user guide, breaking-change migration text, changelog, TODO closure, final matrix,
   and suggested issue replies/closure status.

Routine implementation should not stop to re-ask decisions already accepted in D001-D003 and D007.
Stop only if S00 proves the requested state cannot be represented safely through supported Home
Assistant APIs, the dependency cannot be removed without a new runtime risk, or a new owner choice
would materially change compatibility or release scope.
