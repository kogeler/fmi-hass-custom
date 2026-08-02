<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# P02 Implementation Plan: User-Friendly FMI Location Selection

> **Target repository:** [`kogeler/fmi-hass-custom`](https://github.com/kogeler/fmi-hass-custom)
> **Intended executor:** OpenAI Codex
> **Plan baseline date:** 2026-08-02
> **Execution model:** one bounded session per Codex invocation
> **Plan status:** `PLANNED`
> **Canonical agent entry point:** `AGENTS.md`
> **Verified baseline:** `plans/P02/BASELINE.md` (created by S00)
> **Execution reports:** `plans/P02/SXX.md`

---

## 1. How to use this plan

The canonical plan path is:

```text
plans/P02/PLAN.md
```

P02 must be self-contained in the same form as the completed P01 directory. After execution its
top-level structure must include this canonical set (plus any explicitly approved split-session
reports):

```text
plans/P02/
  PLAN.md
  BASELINE.md
  S00.md
  S01.md
  S02.md
  S03.md
  S04.md
```

`PLAN.md` owns the living tracker, requirements, decisions, and definition of done.
`BASELINE.md` owns the verified pre-implementation repository/API snapshot produced by S00. Each
`SXX.md` owns that session's chronological evidence and handoff. Do not distribute P02 records
between `docs/`, `docs/maintenance/`, or another plan directory.

P02 is independent from the completed P01 plan. Read `plans/P01/PLAN.md` and `plans/P01/` only when a
historical decision is needed; do not update them while executing P02.

For the first execution session, use:

```text
Read AGENTS.md and plans/P02/PLAN.md in full. Inspect the current repository and
execute Session S00 only. Update the tracker and write plans/P02/BASELINE.md and
plans/P02/S00.md. Do not start S01.
```

For subsequent sessions, use:

```text
Read AGENTS.md and plans/P02/PLAN.md in full. Inspect git status, relevant current
maintenance contracts, and the previous plans/P02/SXX.md report. Execute exactly
the next NOT_STARTED session whose prerequisites are DONE. Update the tracker and
write its report. Do not start a later session.
```

To request one specific session:

```text
Read AGENTS.md and plans/P02/PLAN.md in full. Execute P02 Session SXX only if all
prerequisites are DONE. Update the tracker and write plans/P02/SXX.md. Do not
perform work assigned to another session.
```

### Context-safety rule

Each session owns one coherent concern. Never combine sessions unless the repository owner
explicitly asks for it. If work expands beyond the stated concern:

1. Stop at a green, documented checkpoint that is ready for owner review and commit.
2. Add sub-sessions such as `S02-A` and `S02-B` to the tracker.
3. Record why the split was necessary in the current report.
4. Leave the parent session `IN_PROGRESS` until all required sub-sessions are `DONE`.
5. Continue in a later Codex invocation.

Do not silently absorb station-selection work, unrelated config-flow cleanup, dependency upgrades,
or entity/runtime refactoring into P02.

---

## 2. Mission

Replace the current latitude/longitude-first setup experience with two user-facing location paths:

1. **Choose on a map.** Use Home Assistant's standard location selector, initially positioned at
   the Home Assistant home location. Accepting the default is the "use Home location" path;
   moving the marker selects any other point.
2. **Search by place name.** Submit a city or place name directly to FMI, resolve it to FMI's
   canonical place and coordinates, then show the resolved point on the same map selector for
   explicit confirmation or adjustment.

The work must:

- offer both paths during initial setup and reconfiguration;
- keep raw coordinates out of the normal user experience;
- retain latitude and longitude as the persisted runtime coordinates;
- retain `name`, immutable `entity_identity`, config-entry unique ID, entity/device unique IDs,
  registry records, and customized entity IDs;
- continue rejecting duplicate configured coordinates;
- validate every final point through the established FMI coordinate boundary before persisting it;
- handle ambiguous, missing, malformed, and unavailable FMI place lookups without partial writes;
- keep setup and reconfiguration fully translated through Home Assistant config-flow strings;
- add deterministic offline coverage and a bounded live FMI place-resolution contract;
- update current maintenance and user documentation only after behavior is implemented and proven.

---

## 3. Scope boundaries and non-goals

### 3.1 Included behavior

P02 includes:

- a standard Home Assistant `LocationSelector` initialized from `hass.config.latitude` and
  `hass.config.longitude` for a new entry;
- the same selector initialized from the entry's stored coordinates during reconfiguration;
- an explicit selection between map and place-name paths;
- place-name input sent only to FMI;
- a confirmation map populated from the FMI-resolved result;
- common final validation, duplicate detection, persistence, and error handling for both paths;
- backward-compatible handling of all existing config entries without requiring users to revisit
  their configuration;
- concise documentation of what the two paths do and what information FMI receives.

### 3.2 Explicitly excluded behavior

Do not implement any of the following in P02:

- country, municipality, city, or station catalog browsing;
- a `country -> city -> station` hierarchy;
- observation-station discovery, nearest-station selection, or changes to the existing optional
  `fmisid` setting;
- a separate manual latitude/longitude form;
- address autocomplete or a custom address database;
- forward geocoding through Nominatim, Google, Mapbox, or any provider other than FMI;
- automatic tracking of later Home Assistant Home zone changes;
- custom Lovelace/frontend code, a custom map, or browser screenshot automation;
- changing forecast, sensor, station, lightning, sea-level, entity naming, or aggregation behavior;
- changing config-entry, entity, or device identity merely to simplify the new flow;
- changing the supported dependency set unless a demonstrated compatibility requirement blocks
  the feature and the owner approves the scope expansion.

### 3.3 Why catalogs are excluded

FMI's forecast `place` parameter resolves names but does not expose a stable enumerable catalog of
every supported country and city. Its environmental-monitoring station catalog is a separate data
model and does not define every forecastable location. A forecast point also does not need to
coincide with an observation station. Building a hierarchy from station metadata would therefore
misrepresent forecast coverage and exclude valid locations.

### 3.4 Frontend boundary

Use Home Assistant's standard config-flow menu, text selector, and location selector. Do not build
or test Home Assistant frontend internals. Correct UI behavior means the backend flow exposes the
correct step IDs, selectors, defaults, descriptions, errors, placeholders, and persisted result
through Home Assistant's public config-flow APIs.

---

## 4. Engineering constraints

### 4.1 Evidence before change

For each behavior:

1. Characterize the current config flow and selected FMI dependency boundary.
2. Add a deterministic test that describes the required new result.
3. Confirm it fails for the intended reason before implementation when practical.
4. Implement the smallest change satisfying that result.
5. Run focused tests and the repository-wide offline suite.
6. Record root cause, design, and exact verification in the session report.

Do not claim that a selector, FMI parameter, error classification, or migration behavior works
based only on inspection when a Home Assistant-level test is possible.

### 4.2 Offline tests are the default

- Ordinary tests must remain deterministic and run with sockets blocked.
- Save only sanitized public FMI fixtures needed to characterize place resolution.
- Do not record owner coordinates, addresses, cookies, headers, or raw private responses.
- Only `pytest.mark.live` tests may access FMI.
- Do not add network access to ordinary config-flow or lifecycle tests.
- Keep the required live run sequential and inside the documented request budget.

### 4.3 Home Assistant config-flow correctness

- Use current public Home Assistant selectors and data-flow APIs.
- Keep the standard entry points `async_step_user` and `async_step_reconfigure`.
- Every exposed menu option must lead to a complete, functional path in the same session that
  exposes it; do not commit a visible placeholder path.
- Back, cancel, validation failure, and retry must not mutate an entry.
- A reconfigure flow must update only the selected entry after final successful validation.
- Selector data is transient UI input. Persist the existing latitude/longitude keys, not the
  selector wrapper object.
- Do not store the raw place search string unless S00 proves a durable runtime requirement. The
  expected design stores only the existing name, final coordinates, canonical entry title, and
  immutable identity.

### 4.4 Async and external-service boundaries

- Never perform synchronous FMI I/O on the event loop.
- Reuse or narrowly extend `custom_components/fmi/fmi_client.py`; do not call private dependency
  APIs directly from `config_flow.py`.
- Preserve cancellation.
- Catch only the documented finite transport, FMI client/server, XML/parser, and external-shape
  failures at the correct boundary.
- Do not add retries. A user may submit again after a clear translated error.
- Final coordinate validation and place search must use bounded dependency timeouts already
  covered by the enclosing flow/runtime contract.

### 4.5 Stable identity and persistence

- Existing entries require no migration merely because their future UI changes.
- The final stored latitude and longitude remain mutable source coordinates.
- `entity_identity`, config-entry unique ID, device identifiers, entity unique IDs, and entity
  registry IDs remain unchanged during reconfiguration.
- Preserve the existing `name` value on reconfiguration.
- Initial setup may create identity only after final validation succeeds.
- Duplicate detection compares final coordinates and excludes the entry being reconfigured.
- Run duplicate detection before external validation when possible and again immediately before
  creation/update to protect against concurrent flows.
- Do not introduce fuzzy coordinate equality without evidence. If exact-float comparison proves
  inadequate, document and test the selected normalization before changing it.

### 4.6 Security and privacy

- Treat exact coordinates and raw place-search text as potentially sensitive.
- Do not log either value, include it in arbitrary exception text, or add it to diagnostics.
- Place search may send the submitted string only to FMI. Do not forward it to Nominatim or another
  geocoder.
- Continue filtering coordinate-bearing dependency request logs and parser payloads.
- User-visible errors must identify the failure class without echoing submitted text or external
  payloads.
- Do not add telemetry, analytics, or secrets.

### 4.7 Dependency and environment policy

- Prefer the Home Assistant selector API and the selected FMI client already present in the lock.
- Do not add a new dependency for mapping or place search.
- If the selected FMI client cannot safely expose place resolution, implement a narrow adapter over
  its documented public API before considering a direct WFS implementation.
- Any unavoidable dependency change follows `docs/maintenance/DEPENDENCIES.md` and
  `docs/maintenance/DEVELOPMENT.md`, including clean `pip freeze` regeneration.
- Run supported Python/Home Assistant commands through rootless Podman; the host Python is not a
  fallback.

### 4.8 Release and documentation policy

- `.version` remains the only human-maintained project version.
- P02 must not hardcode a future release number. S00 records the target increment strategy; the
  first implementation session synchronizes `.version`, manifest, and a dated changelog section
  before the P02 branch is opened as a PR.
- Subsequent P02 sessions update the same release section with only notable user-facing changes.
- Current-facing documentation links to the latest GitHub Release and must not copy the numeric
  project version.
- Update the owning files under `docs/maintenance/` when their current contracts change. Store
  P02 progress and verification only under `plans/P02/`.

### 4.9 Living-plan and owner-controlled Git rules

- Correct this plan immediately when verified repository state, Home Assistant APIs, FMI behavior,
  or necessary scope differs from the text. Do not defer a known correction until session end.
- Record every material correction or scope expansion in the current `plans/P02/SXX.md` report and
  decision log.
- A scope expansion does not authorize unrelated work; split the session when required.
- Do not run Git operations that may require a hardware token, interactive credentials, or
  authenticated SSH.
- Do not commit. The repository owner owns all commits.
- Leave a reviewed working tree and provide exactly one concise suggested commit message beginning
  with `P02-SXX:` at session end.
- Use `OWNER_TO_COMMIT` for a completed session until the owner provides its commit SHA. Replace it
  in the tracker/report when a later session can verify the owner's commit.
- Never reset, stash, overwrite, or reformat unrelated owner changes.

---

## 5. Baseline snapshot to verify in S00

This snapshot records planning evidence from 2026-08-02. S00 must refresh it against the actual
working tree and current authoritative documentation before implementation, then preserve the
verified result in `plans/P02/BASELINE.md`. The baseline file is evidence for P02 execution, not a
current maintenance contract.

### Current repository behavior

- Initial setup exposes `name`, `latitude`, and `longitude` in one Voluptuous form.
- Latitude and longitude default to Home Assistant's configured home coordinates, but the user sees
  and edits raw numbers.
- Reconfiguration exposes raw latitude and longitude for the existing entry.
- Both paths call `validate_user_config`, which requests current FMI weather by coordinates and
  uses the returned FMI place as the config-entry title.
- Successful initial setup stores `name`, latitude, longitude, and a random immutable
  `entity_identity`.
- Successful reconfiguration changes only coordinates and the resolved entry title; the existing
  update listener reloads that entry.
- Duplicate detection uses exact final coordinate equality.
- Config-entry version 2 already separates identity from mutable coordinates, so the UI change
  should not require a persistent-data migration.
- `strings.json` and `translations/en.json` still describe direct coordinate entry.

### Available Home Assistant capability

- The supported Home Assistant environment includes `homeassistant.helpers.selector.LocationSelector`.
- It renders a map selection and validates a mapping containing `latitude` and `longitude`, with an
  optional radius that P02 does not need.
- The selector can be initialized with the Home Assistant or entry coordinates, allowing "use
  Home" and "choose on map" to be one path.
- Current config-flow menus and selector-backed schemas must be rechecked in S00 because public API
  details may change with the supported Home Assistant lock.

### Available FMI capability

- FMI WFS forecast stored queries accept a `place` parameter.
- The selected `fmi-weather-client` exposes public place-name weather and forecast functions, but
  the integration's narrow adapter currently exposes only coordinate weather/forecast plus
  observation calls.
- A live planning probe resolved the public names Helsinki, Stockholm, Oslo, and Tallinn to
  canonical place names and coordinates through the selected client.
- This proves locations beyond Finland can resolve, but it is not an exhaustive or stable list of
  supported countries or cities.
- FMI exposes monitoring networks and station metadata separately. A planning query for the active
  automatic weather network returned 188 stations, all marked as Finland. This station catalog is
  not a forecast-place catalog and is outside P02.

### Baseline questions S00 must close

1. What exact step/menu IDs produce the clearest setup and reconfigure paths under the supported
   Home Assistant frontend contract?
2. Can the selected client's public place-name method be wrapped without bypassing the existing
   privacy filter, timeout, and exception policy?
3. What sanitized fixture and dependency contract are sufficient to detect a place-resolution API
   change?
4. Does the search result always provide a finite, valid coordinate pair and non-empty canonical
   place, and how must malformed results be classified?
5. Should the confirmation map permit adjustment? The intended answer is yes, with the adjusted
   point passed through the common final coordinate validation path.
6. How will a search result with the same coordinates as an existing entry surface the existing
   `already_configured` abort?
7. What release increment is appropriate at implementation time, without hardcoding it in P02?

---

## 6. Requirement closure matrix

This table is a living record. Update status, tests, report, and commit evidence during execution.

| ID | Required outcome | Owner | Primary evidence | Report | Commit | Status |
|---|---|---|---|---|---|---|
| R01 | New setup uses a standard map selector initialized at the Home Assistant location instead of raw coordinate fields | S01 | `tests/test_config_flow.py` | `plans/P02/S01.md` | `OWNER_TO_COMMIT` | NOT_STARTED |
| R02 | Reconfigure uses the map selector initialized at the entry's current location | S01 | `tests/test_config_flow.py` | `plans/P02/S01.md` | `OWNER_TO_COMMIT` | NOT_STARTED |
| R03 | Setup and reconfigure both expose a complete alternative FMI place-name search path | S02 | config-flow and FMI contract tests | `plans/P02/S02.md` | `OWNER_TO_COMMIT` | NOT_STARTED |
| R04 | A resolved place is shown on a confirmation map and any adjusted point receives normal coordinate validation | S02 | config-flow step/default/result assertions | `plans/P02/S02.md` | `OWNER_TO_COMMIT` | NOT_STARTED |
| R05 | Both paths persist the existing data shape and preserve identity, registry, lifecycle, and multi-entry isolation | S01/S03 | config-flow, migration, lifecycle tests | `plans/P02/S03.md` | `OWNER_TO_COMMIT` | NOT_STARTED |
| R06 | Duplicate, not-found, transport, server, malformed-result, cancel, back, and concurrent-flow cases never partially mutate an entry | S02/S03 | negative-path Home Assistant tests | `plans/P02/S03.md` | `OWNER_TO_COMMIT` | NOT_STARTED |
| R07 | Raw search text and exact coordinates remain absent from logs and diagnostics | S03 | privacy/log/diagnostic tests | `plans/P02/S03.md` | `OWNER_TO_COMMIT` | NOT_STARTED |
| R08 | A bounded public live probe detects FMI place-resolution drift without weakening offline isolation | S03 | `tests/test_live_fmi.py`; request-budget evidence | `plans/P02/S03.md` | `OWNER_TO_COMMIT` | NOT_STARTED |
| R09 | Strings, user guide, reconfiguration/runtime contracts, changelog, and agent map reflect the proven behavior without duplicating release numbers | S04 | docs review and validation | `plans/P02/S04.md` | `OWNER_TO_COMMIT` | NOT_STARTED |
| R10 | Full repository gates pass and no station/catalog/manual-coordinate scope entered the implementation | S04 | final verification matrix | `plans/P02/S04.md` | `OWNER_TO_COMMIT` | NOT_STARTED |

Status values: `NOT_STARTED`, `IN_PROGRESS`, `BLOCKED`, `DONE`.

---

## 7. Candidate risks to investigate

| Risk | Why it matters | Required handling |
|---|---|---|
| FMI place ambiguity | A name may resolve to an unexpected place | Display FMI's canonical result on a map and require explicit submit; do not silently create the entry from text alone |
| No enumerable place catalog | A country/city list would be incomplete and misleading | Keep free-text FMI resolution plus map; do not synthesize a catalog from station metadata |
| Selector/persistence mismatch | `LocationSelector` returns a mapping while runtime expects top-level coordinates | Normalize transient selector data through one tested boundary and persist only existing keys |
| Search result mutation | A user may move the confirmation marker | Treat the map value as final and revalidate it through the coordinate path before writing |
| Duplicate location race | Two flows may resolve different text to the same coordinates | Check duplicates on final coordinates before external validation where possible and immediately before write |
| Malformed dependency model | FMI/client may return missing place, non-finite coordinates, or an unexpected object | Validate the adapter result and surface a translated generic error without storing partial state |
| FMI outage during setup | Search and final validation depend on live FMI | Preserve form input in memory, display a retryable translated connection error, and write nothing |
| Privacy leakage | Place input may be an address and coordinates identify a home | Filter dependency logs; never echo input, coordinates, raw XML, URL parameters, or external payloads |
| Reconfigure identity regression | A new step structure could accidentally recreate or rename entries | Use `async_update_and_abort` only after final validation and assert all persistent identity/registry fields |
| Search/client boundary drift | The upstream place method is outside the current integration adapter | Add a narrow contract-tested adapter and a bounded live public-place probe |
| Unsupported point | The map permits points outside FMI forecast coverage | Let FMI coordinate validation reject the point with a clear non-destructive error |
| Back/cancel stale state | Multi-step flow candidates may leak into a later attempt | Keep candidate state per flow instance, replace it on each search, and test cancellation/retry sequences |
| Translations drift | New menu/step/error keys may pass Python tests but fail hassfest | Update `strings.json` and `translations/en.json` together and run repository validation |
| Live request growth | Required CI already has a strict FMI budget | Reuse an existing public point or increase the documented budget by the exact minimal request count |

S00 may add risks. Do not delete a risk without recording the evidence that closed or superseded it.

---

## 8. Required test architecture

### 8.1 Unit and adapter tests

Cover:

- valid `LocationSelector` mappings;
- missing keys, booleans, out-of-range values, NaN, and infinities at the candidate boundary;
- valid place resolution to canonical place and finite coordinates;
- `None`, empty place, missing fields, malformed coordinates, parser errors, FMI client/server
  errors, and request transport failures;
- no raw query or coordinates in logs;
- place-resolution adapter signature and selected public dependency behavior;
- sanitized fixture structure sufficient to catch upstream parsing drift.

Do not duplicate Home Assistant's selector implementation tests. Test the integration's schema,
normalization, and flow contract.

### 8.2 Home Assistant config-flow tests

Initial setup must prove:

- the default map marker matches Home Assistant's configured location;
- no raw latitude/longitude fields are presented;
- accepting the default creates a valid entry;
- moving the marker creates the entry at the selected point;
- menu/choice navigation reaches map and place search;
- a valid place search reaches confirmation with resolved coordinates;
- confirming unchanged and adjusting before confirm both persist the correct final point;
- the canonical FMI place becomes the entry title;
- the existing `name` data remains present and valid;
- duplicate map and duplicate resolved-place results abort consistently;
- search not found, connection failure, malformed response, and invalid final point stay on a
  translated retryable form without an entry;
- repeated submissions and concurrent duplicate creation cannot create two entries.

Reconfiguration must prove:

- map default equals stored entry coordinates, not the current Home location;
- both map and search paths update one entry in place;
- identity, name, options, unique ID, entity registry, device registry, and customized entity IDs
  remain unchanged;
- only coordinates and canonical title change;
- duplicate, failed, canceled, or backed-out flows make no change and trigger no reload;
- successful reconfigure reloads only the affected loaded entry;
- unloaded entries update safely without creating runtime state;
- multi-entry coordinators remain isolated.

### 8.3 Migration and lifecycle tests

No config-entry version change is expected. Prove:

- current and migrated legacy entries can open and complete the new reconfigure UI;
- no migration rewrites data merely to support selector input;
- existing registry guarantees from `tests/test_migrations.py` remain intact;
- setup, unload, reload, and options update behavior does not change;
- failed config flows do not create coordinators, listeners, devices, or entities.

### 8.4 Live FMI contract

Use one stable public place already covered by the repository's public test-location policy. Assert
only durable invariants:

- the name resolves successfully;
- canonical place is non-empty;
- latitude/longitude are finite and geographically valid;
- coordinate validation for the resolved point succeeds;
- the result can drive the same config-flow boundary used offline.

Do not assert exact weather values, exact coordinates beyond a broad public-region sanity bound, or
the complete spelling of a mutable external label unless the FMI contract documents it. Count the
request explicitly and update `docs/maintenance/LIVE_TESTS.md` if the budget changes.

### 8.5 Coverage and quality

- Keep the repository coverage gate at or above its current threshold.
- Do not add exclusions, `noqa`, broad type ignores, xfails, sleeps, retries, or assertion weakening
  merely to make P02 pass.
- Ruff, Pylint, mypy, network blocking, config-flow tests, migration tests, lifecycle tests,
  hassfest, HACS/layout validation, and actionlint must not regress.
- Use pytest-xdist only through the existing opt-in Make variable. Live tests remain sequential.

---

## 9. CI and repository quality target

P02 does not need a new workflow. The existing event matrix remains authoritative.

Required P02 verification uses:

- `make format-check`
- `make lint`
- `make type-check`
- `make test-full`
- `make test-network-block`
- `make validate`
- `make version-check`
- `make live` when the external place boundary changes
- current stable/prerelease compatibility commands if selector/config-flow behavior differs across
  the moving environments
- `make audit` and `make licenses` only if dependencies change

CI requirements:

- ordinary config-flow tests remain offline;
- the live place test runs in the existing bounded live step after offline coverage;
- workflow permissions and triggers remain unchanged unless a demonstrated P02 need requires a
  narrowly reviewed update;
- no inline pip pins, custom CI HTTP calls, mutable action references, or scheduled workflows are
  added;
- release/version checks remain mandatory for the P02 pull request and `master` push.

---

## 10. Session tracker

Update this table at the start and end of every execution session.

| Session | Objective | Prerequisites | Report | Commit | Status |
|---|---|---|---|---|---|
| S00 | Refresh baseline, freeze UX/data/error contracts, and add place-boundary characterization evidence | None | `plans/P02/BASELINE.md`; `plans/P02/S00.md` | `OWNER_TO_COMMIT` | NOT_STARTED |
| S01 | Replace raw-coordinate setup/reconfigure forms with the Home-defaulted standard map path | S00 DONE | `plans/P02/S01.md` | `OWNER_TO_COMMIT` | NOT_STARTED |
| S02 | Add FMI place-name search and map confirmation to setup and reconfigure | S01 DONE | `plans/P02/S02.md` | `OWNER_TO_COMMIT` | NOT_STARTED |
| S03 | Prove error, privacy, identity, migration, lifecycle, multi-entry, and live FMI behavior; fix confirmed gaps | S02 DONE | `plans/P02/S03.md` | `OWNER_TO_COMMIT` | NOT_STARTED |
| S04 | Finalize translations/docs/release notes and run the complete verification matrix | S03 DONE | `plans/P02/S04.md` | `OWNER_TO_COMMIT` | NOT_STARTED |

The plan is complete only when every session and every requirement row is `DONE`.

---

## 11. Standard session protocol

### 11.1 Start of session

1. Read `AGENTS.md`, this plan, the previous P02 report, and the smallest relevant
   `docs/maintenance/` contracts.
2. Inspect `git status`, current branch, recent commits, and all unexplained working-tree changes.
3. Reconcile `OWNER_TO_COMMIT` with any owner commit created since the previous session.
4. Confirm all prerequisites are `DONE`.
5. Mark only the current session `IN_PROGRESS`.
6. Recheck external/API assumptions that materially affect this session.
7. Correct the plan immediately if evidence differs.
8. State the bounded work and intended verification before editing.

### 11.2 During session

- Keep edits inside the owning concern.
- Add failing/characterization evidence before the behavioral fix when practical.
- Keep tests offline unless explicitly working on the live marker.
- Update current maintenance contracts when behavior changes.
- Update `CHANGELOG.md` only for notable completed behavior, not every internal helper.
- Preserve unrelated owner changes.
- Record important decisions in the decision log as they are made.
- If blocked, document exact evidence and the smallest owner decision or upstream change needed.

### 11.3 End of session

1. Run the session's focused checks and the required wider checks.
2. Review `git diff --check`, relevant diffs, and `git status`.
3. Update requirement rows and the session tracker accurately.
4. Write or update `plans/P02/SXX.md` using the template below.
5. Mark the session `DONE` only when all exit criteria pass and no assigned work remains.
6. Do not mark checks as passed unless the exact command completed successfully.
7. Leave the working tree for owner review; do not commit.
8. Provide exactly one concise suggested commit message beginning with `P02-SXX:`.
9. Do not begin the next session.

---

## 12. Detailed session specifications

## Session S00 — Baseline, UX contract, and characterization

### Objective

Refresh every planning assumption, define the exact step/state/data/error contract, and establish
offline evidence for the Home Assistant selector and FMI place-resolution boundary without changing
the user-visible flow.

### Required work

1. Inspect current `config_flow.py`, `fmi_client.py`, strings/translations, setup/reconfigure tests,
   migration/lifecycle tests, `.version`, changelog, and relevant maintenance contracts.
2. Verify the current supported Home Assistant selector/config-flow APIs locally in Podman and
   against official documentation.
3. Verify the selected FMI client's public place-name API, signature, timeout/executor behavior,
   exception surface, parser model, and logging behavior.
4. Recheck FMI's official `place` parameter documentation and service limits. Use only public test
   names and a minimal number of requests.
5. Record the exact state diagram for initial setup and reconfiguration, including step IDs, menu
   choices, back/cancel behavior, transient candidate fields, and final stored fields.
6. Decide how the common `name` input is collected without confusing it with the FMI place query.
7. Decide and test the malformed-result validation rules for canonical place and coordinates.
8. Add sanitized fixtures and characterization/contract tests needed by S02. Do not expose the new
   UI yet.
9. Record the live test location and exact incremental request budget.
10. Record the SemVer increment strategy for the first implementation session based on the current
    base version and repository policy; do not hardcode the chosen number into this plan.
11. Create `plans/P02/BASELINE.md` containing the verified pre-implementation repository state,
    current selector/config-flow and FMI place-boundary evidence, privacy/request limits, test/CI
    baseline, open questions closed by S00, authoritative references with access dates, and any
    deviations from Section 5.
12. Update risks, decisions, requirements, tracker, and current contracts if verified facts differ.
13. Write `plans/P02/S00.md`, linking to the baseline instead of duplicating its full inventory.

### Verification

- focused FMI contract/fixture tests;
- current config-flow characterization tests;
- `make format-check`;
- `make type-check` if typed production/test helpers changed;
- `make test-network-block`;
- `git diff --check`.

### Exit criteria

- Exact UI/data/error contracts are recorded and implementable without further product decisions.
- Place resolution is characterized offline at the integration boundary.
- No visible map/search path has been partially exposed.
- No private location or raw sensitive response was stored.
- The plan matches verified reality.
- `plans/P02/BASELINE.md` is complete and contains no session-progress narrative.
- `plans/P02/S00.md` is complete.

### Do not do

- Do not replace coordinate fields yet.
- Do not add the place-search menu yet.
- Do not implement station/catalog/manual-coordinate behavior.
- Do not change persistent entry data or identity.

## Session S01 — Home-defaulted map selection

### Objective

Replace raw latitude and longitude fields with the standard Home Assistant map selector for both
new setup and reconfiguration while preserving the existing stored-data and identity contracts.

### Required work

1. Add the narrow transient location-selector field/config needed by the verified S00 design.
2. Render the initial map at Home Assistant's configured coordinates.
3. Render the reconfigure map at the entry's stored coordinates.
4. Normalize the selector mapping into the existing top-level latitude and longitude fields.
5. Route both flows through one common final coordinate validation and duplicate-check boundary
   where doing so reduces real duplication without obscuring flow semantics.
6. Keep initial `name` behavior compatible and preserve it during reconfiguration.
7. Create a new entry only after successful FMI validation; update an existing entry only through
   the current in-place reconfigure API.
8. Update strings and English translations for the map path; remove raw coordinate instructions
   from the exposed forms.
9. Add setup/reconfigure tests for defaults, moved marker, invalid selector data, unsupported point,
   duplicate coordinates, failure, cancel, identity preservation, and reload behavior.
10. At the first implementation change, apply the S00-approved project version increment, sync the
    manifest, and open the matching dated changelog section. Do this once for P02, not per session.
11. Update `docs/maintenance/RECONFIGURATION.md` if the current contract changes materially.
12. Write `plans/P02/S01.md`.

### Verification

- focused config-flow and reconfigure tests;
- focused migration/lifecycle tests affected by the schema change;
- `make format-check`;
- `make lint`;
- `make type-check`;
- `make test-fast`;
- `make test-network-block`;
- `make version-check`;
- `git diff --check`.

### Exit criteria

- New and existing entries use a map instead of visible numeric coordinate fields.
- Accepting the initial marker uses the Home Assistant location.
- Reconfigure defaults to the entry location.
- Stored data and identity remain backward compatible.
- All exposed paths are complete and green.
- `plans/P02/S01.md` is complete.

### Do not do

- Do not expose a place-search choice until S02 can complete it.
- Do not add manual coordinates or station selection.
- Do not change runtime forecast behavior.

## Session S02 — FMI place search and confirmation

### Objective

Add the alternative place-name route to both setup and reconfiguration, resolving through FMI and
requiring confirmation on the standard map before common final validation and persistence.

### Required work

1. Expose the S00-defined translated choice/menu with exactly map and place-search paths.
2. Add a translated text-selector form for a city or place name. Keep `name` semantically distinct
   from the search query.
3. Extend the integration's narrow FMI adapter with the S00-characterized public place-resolution
   call and validated result model.
4. Keep dependency I/O outside the event loop and preserve cancellation/privacy filters.
5. On success, retain only the transient canonical place and coordinate candidate needed for the
   confirmation step.
6. Show the candidate on `LocationSelector`. Allow adjustment, but treat the submitted map point as
   final and run it through coordinate validation.
7. Create/update only after the final point succeeds and duplicate checks pass.
8. Map not-found/no-data and connection/server failures to specific translated retryable errors
   where the existing contract can distinguish them. Map malformed/unexpected results to the
   sanitized generic error.
9. Do not echo raw input or coordinates in logs or error text.
10. Add deterministic setup and reconfigure tests for success, adjustment, ambiguity confirmation,
    duplicate resolution, all error classes, retry, back, cancel, and repeated search.
11. Add notable changelog content to the existing P02 release section.
12. Update current maintenance contracts affected by the new FMI setup-time boundary.
13. Write `plans/P02/S02.md`.

### Verification

- focused FMI adapter/fixture tests;
- complete config-flow tests;
- focused privacy/log tests;
- `make format-check`;
- `make lint`;
- `make type-check`;
- `make test-full`;
- `make test-network-block`;
- `make version-check`;
- `git diff --check`.

### Exit criteria

- Both map and search routes are available and complete in setup and reconfigure.
- Search never creates/updates before map confirmation.
- Adjusted confirmation points follow coordinate validation.
- Error and retry paths are non-destructive and translated.
- No new external provider or persistent search field was introduced without a recorded necessity.
- `plans/P02/S02.md` is complete.

### Do not do

- Do not add autocomplete or catalogs.
- Do not make a station part of location resolution.
- Do not parse/scrape FMI's public website when the documented client/WFS boundary suffices.

## Session S03 — Robustness, identity, lifecycle, privacy, and live contract

### Objective

Audit the complete implemented flow at Home Assistant level, close only reproduced gaps, and prove
the external FMI place boundary with a bounded public live test.

### Required work

1. Exercise initial setup and reconfiguration through Home Assistant's public flow APIs, not direct
   handler shortcuts alone.
2. Cover simultaneous entries and concurrent flows resolving to distinct and identical points.
3. Verify migrated legacy entries, customized IDs, device/entity registry identity, options,
   listener ownership, loaded/unloaded reconfigure, reload isolation, and idempotence.
4. Verify back/cancel/retry sequences discard or replace transient candidates safely.
5. Inject every documented dependency/transport/parser/malformed-result failure at search and final
   validation boundaries.
6. Prove logs and diagnostics omit raw search strings, exact coordinates, URLs with query values,
   raw XML, coordinate-derived identity, and arbitrary exception payloads.
7. Add or update the minimal live place-resolution probe using the S00 public location and request
   budget. Keep assertions stable and broad.
8. Run the existing required live suite and classify any failure as integration regression,
   dependency drift, upstream outage, or unstable assertion before changing code/tests.
9. Fix every confirmed P02-owned high/critical correctness, identity, lifecycle, or privacy defect;
   split the session for larger unrelated discoveries.
10. Update `docs/maintenance/LIVE_TESTS.md`, `RUNTIME.md`, `RECONFIGURATION.md`,
    `COMPATIBILITY_SECURITY.md`, or `MIGRATIONS.md` only where the current contract changed.
11. Update requirement rows and the P02 release changelog section with significant fixes.
12. Write `plans/P02/S03.md`.

### Verification

- full config-flow, migration, lifecycle, compatibility/security, and FMI contract tests;
- `make format-check`;
- `make lint`;
- `make type-check`;
- `make test-full`;
- `make test-network-block`;
- `make live`;
- `make validate` when strings/contracts changed;
- `make version-check`;
- `git diff --check`.

### Exit criteria

- R01 through R08 are `DONE` with explicit tests and report evidence.
- No known P02-owned critical/high defect remains.
- Live request volume is documented and bounded.
- Privacy and identity guarantees pass for both paths.
- `plans/P02/S03.md` is complete.

### Do not do

- Do not weaken live assertions merely because FMI is temporarily unavailable.
- Do not broaden exception handling to `Exception` around cancellation-sensitive FMI calls.
- Do not fix unrelated runtime/product behavior without splitting scope.

## Session S04 — Documentation and final verification

### Objective

Make the proven location experience understandable to users and future agents, synchronize release
records, and demonstrate that the complete repository remains release-ready.

### Required work

1. Review the complete P02 diff and every prior P02 report.
2. Update `docs/USER_GUIDE.md` to describe map selection, Home-location default, place search,
   confirmation, reconfiguration, unsupported-point errors, and privacy without numeric release
   duplication.
3. Keep `README.md` concise; update it only if its capability/limitation summary or documentation
   index materially changed.
4. Update the owning current maintenance contracts and the `AGENTS.md` documentation map or rules
   only where needed for future maintenance.
5. Remove the P02 TODO item only after all sessions and requirements are actually complete; do not
   remove unrelated TODO items.
6. Finalize the existing P02 changelog section with significant user-visible changes only.
7. Verify `.version`, manifest mirror, changelog section, and latest-release documentation policy.
8. Run focused tests followed by every required local repository gate.
9. Run stable/prerelease compatibility when feasible and record exact results without converting
   the informational prerelease signal into a support claim.
10. Review GitHub workflow diffs only if P02 changed CI; otherwise explicitly record that no new
    workflow was required.
11. Update all requirement rows, tracker, decision log, and plan status to `DONE` only after the
    final matrix passes.
12. Write `plans/P02/S04.md` with complete verification and remaining non-P02 limitations.

### Verification

- `make format-check`
- `make lint`
- `make type-check`
- `make test-full`
- `make test-network-block`
- `make validate`
- `make version-check`
- `make live`
- `make compatibility-stable`
- `make compatibility-prerelease` (informational result recorded accurately)
- `make audit` and `make licenses` if the dependency graph changed
- `git diff --check`
- final `git status --short` and diff review

### Exit criteria

- R01 through R10 and S00 through S04 are `DONE`.
- User and maintenance documentation match actual behavior.
- Version metadata and release notes are consistent.
- All required supported-environment gates pass.
- Any upstream/informational failure is classified precisely rather than hidden.
- No catalog, station-selection, manual-coordinate, or unrelated scope entered P02.
- The TODO item is closed only because the plan is complete.
- `plans/P02/S04.md` is complete.

---

## 13. Execution report template

Every session must save a report at `plans/P02/SXX.md` using this structure:

```markdown
<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# P02 Session SXX Report

## Metadata

- Date/time:
- Starting commit:
- Ending commit: OWNER_TO_COMMIT
- Working tree at start:
- Suggested owner commit: `P02-SXX: ...`
- Status: DONE | IN_PROGRESS | BLOCKED

## Objective

One paragraph matching the owning session.

## Baseline and evidence

- Relevant code/API state verified before change.
- External references and access dates.
- Reproduction or characterization result.

## Changes made

- Behavioral and structural changes.
- Plan or contract corrections.

## Decisions

- Decision IDs added/updated.
- Alternatives rejected and why.

## Tests and checks run

| Command/check | Result | Evidence/notes |
|---|---|---|

Do not mark a command PASS unless that exact command completed successfully.

## Files materially changed

- Paths and reasons, not a raw diff inventory.

## Requirement mapping

- RXX: status and evidence.

## Remaining risks or blockers

- Precise unresolved items, or `None within this session`.

## Instructions for the next session

- Preconditions, exact next objective, and facts that must not be rediscovered.
```

The baseline and reports are P02 execution history. Keep `BASELINE.md`, `S00.md` through `S04.md`,
and `PLAN.md` together in `plans/P02/`. Do not place them in `docs/maintenance/`, `plans/P01/`, or
the root documentation.

---

## 14. Decision log

Update this table when evidence changes a decision.

| ID | Owner/session | Date | Decision | Rejected alternatives | Rationale/evidence | Status |
|---|---|---|---|---|---|---|
| D001 | Owner/P02 | 2026-08-02 | Provide exactly two normal location paths: Home-defaulted map and FMI place search followed by map confirmation | Four independent modes; raw coordinates as a normal path | Home and map are one selector state; search covers users who know a place name; confirmation protects against ambiguity | ACCEPTED |
| D002 | Owner/P02 | 2026-08-02 | Do not expose a separate manual coordinate form | Retain raw fields under an advanced mode | The map already selects an arbitrary precise point; a second numeric path adds UI and test complexity without demonstrated need | ACCEPTED |
| D003 | Owner/P02 | 2026-08-02 | Keep station selection outside P02 and separate from forecast-point selection | Country/city/station hierarchy; force forecast to a station | Forecast coverage and observation-station metadata are different FMI concepts; valid forecasts do not require stations | ACCEPTED |
| D004 | Owner/P02 | 2026-08-02 | Use FMI directly for place resolution and no additional geocoder | Nominatim/Google/Mapbox forward geocoding; scraped city catalog | The selected client and official WFS support `place`; another provider adds privacy, policy, availability, and dependency risk | ACCEPTED |
| D005 | Plan/P02 | 2026-08-02 | Preserve existing persisted latitude/longitude and identity fields; selector/search state remains transient | Persist a new nested location object or search mode | Runtime and migrations already use stable coordinates plus independent identity; UI input shape does not justify data migration | PROVISIONAL_UNTIL_S00 |
| D006 | Plan/P02 | 2026-08-02 | Reproduce P01's self-contained directory pattern with `PLAN.md`, S00-owned `BASELINE.md`, and `SXX.md` session reports under `plans/P02/` | Reuse `plans/P01/`; put baseline/reports in `docs/maintenance/`; omit a distinct verified baseline | P02 needs an independent plan, pre-implementation snapshot, and chronological history while maintenance docs remain current technical contracts | ACCEPTED |

---

## 15. Final definition of done

P02 is complete only when every statement is true.

### User experience

- Initial setup no longer requires visible latitude/longitude entry.
- The map starts at the Home Assistant home location and may be accepted or moved.
- Place-name search resolves through FMI and always reaches an explicit map confirmation before
  persistence.
- Reconfiguration offers the same two paths and initializes the map from the entry location.
- Errors are translated, actionable, retryable where appropriate, and do not expose sensitive
  input.
- Station selection and manual coordinates were not introduced.

### Persistence and compatibility

- Runtime continues to receive top-level stored latitude and longitude.
- Existing entries require no UI-driven migration.
- `name`, options, immutable identity, config-entry unique ID, device/entity unique IDs, registry
  records, and customized IDs remain stable.
- Successful reconfiguration changes only intended mutable location/title state and reloads only
  the affected entry.
- Failed, duplicate, canceled, or abandoned flows make no persistent or runtime change.

### External behavior and privacy

- Place lookup uses the documented FMI boundary and no additional provider.
- FMI result fields are validated before use.
- Search and coordinate I/O does not block the event loop or swallow cancellation.
- Raw place input, exact coordinates, raw responses, URLs with query data, and external payloads are
  absent from logs and diagnostics.
- The live contract uses a public location, bounded requests, stable assertions, and no secrets.

### Tests and quality

- Unit/contract/config-flow/migration/lifecycle/privacy tests are deterministic and offline.
- Both paths and all listed failure cases have Home Assistant-level regressions.
- Coverage remains at or above the repository gate.
- Format, lint, type, offline coverage, network blocking, validation, version, and live checks pass.
- Current stable compatibility passes; prerelease compatibility is reported accurately.
- No checker, assertion, coverage rule, or security policy was weakened to make P02 green.

### Documentation and release

- Strings and translations describe actual menu, map, search, confirmation, and errors.
- User and current maintenance documentation match implemented behavior.
- `plans/P02/` contains `PLAN.md`, the S00-verified `BASELINE.md`, and one `SXX.md` report for every
  completed session, matching the self-contained P01 plan-record structure.
- P02 records contain execution history; `docs/maintenance/` contains only current contracts.
- `.version`, manifest, changelog, and release automation remain synchronized.
- Current-facing docs refer users to the latest GitHub Release instead of copying a version number.
- The P02 TODO item is removed only after the plan is complete.

### Scope discipline

- No station/country/city catalog was implemented.
- No manual coordinate form or third-party forward geocoder was added.
- No runtime weather/entity behavior changed without a reproduced P02 necessity.
- No unrelated refactor or dependency change remains in the P02 diff.

---

## 16. Authoritative references to recheck

Record access dates in the executing session report.

### Repository contracts

- Agent guide: `AGENTS.md`
- Current reconfiguration contract: `docs/maintenance/RECONFIGURATION.md`
- Runtime/privacy contract: `docs/maintenance/RUNTIME.md`
- Availability contract: `docs/maintenance/AVAILABILITY.md`
- Compatibility/security contract: `docs/maintenance/COMPATIBILITY_SECURITY.md`
- Live request policy: `docs/maintenance/LIVE_TESTS.md`
- Migration rules: `docs/maintenance/MIGRATIONS.md`
- Development commands: `docs/maintenance/DEVELOPMENT.md`
- Release/version rules: `docs/maintenance/HACS_RELEASES.md`
- Historical plan and decisions: `plans/P01/PLAN.md`, `plans/P01/`

### Home Assistant

- Config flow: <https://developers.home-assistant.io/docs/core/integration/config_flow/>
- Reconfiguration flow rule:
  <https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/reconfiguration-flow/>
- Config-flow quality rule:
  <https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/config-flow/>
- Selector documentation: <https://www.home-assistant.io/docs/blueprint/selectors/>
- Backend localization: <https://developers.home-assistant.io/docs/internationalization/core/>
- Testing: <https://developers.home-assistant.io/docs/development_testing/>
- Async blocking operations: <https://developers.home-assistant.io/docs/asyncio_blocking_operations/>

### FMI

- Open Data manual: <https://en.ilmatieteenlaitos.fi/open-data-manual>
- WFS stored queries and limits:
  <https://en.ilmatieteenlaitos.fi/open-data-manual-fmi-wfs-services>
- WFS examples and `place` parameter:
  <https://en.ilmatieteenlaitos.fi/open-data-manual-wfs-examples-and-guidelines>
- Time-series point/nearest-station behavior:
  <https://en.ilmatieteenlaitos.fi/open-data-manual-time-series-data>
- Open Data changelog: <https://en.ilmatieteenlaitos.fi/open-data-changelog>
- Observation station metadata: <https://en.ilmatieteenlaitos.fi/observation-stations>
- Selected FMI client package/source as pinned by current repository metadata.

---

## 17. Owner review checkpoints

The plan is executable without repeated product clarification, but these outputs deserve owner
review before P02 is merged:

1. **S00:** exact flow state diagram, wording, confirmation behavior, and release increment strategy.
2. **S01:** map-first setup/reconfigure UI and proof that accepting Home location is obvious.
3. **S02:** place-search result/confirmation UX and error wording.
4. **S03:** privacy evidence, identity/migration matrix, and live request-budget change.
5. **S04:** user documentation, changelog, final verification, and remaining limitations.

Codex should not stop routine implementation to re-ask decisions already fixed in D001-D004. Mark
a session `BLOCKED` only when authoritative API behavior, backward compatibility, or privacy makes
a safe implementation impossible without a new owner decision.
