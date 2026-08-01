<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Runtime Correctness Audit

Audited 2026-08-01 at base commit `a944ecd34ad3ba25a60439099447fa6a6cf00c6c` against Home Assistant 2026.7.4, Python 3.14.2, and `fmi-weather-client` 1.0.0. The audit covered only the existing integration feature set assigned to S13.

## Result

No critical finding was reproduced. One high availability defect and one medium process-wide side effect were reproduced and fixed with regression tests. No known reproducible critical/high runtime correctness defect remains.

| Severity | Finding | Evidence and resolution | Status |
|---|---|---|---|
| High | Request-library transport failures and malformed FMI responses escaped the source-specific coordinator boundaries. A current failure skipped place fallback and retained stale internal data behind a failed refresh; a forecast-only parse failure made the primary coordinator fail and could put initial setup into retry despite valid current weather. | Failing Home Assistant tests reproduced both paths. The coordinator now classifies the finite set of transport, XML/parser, and external-shape exceptions at current, place, forecast, and station source boundaries. Current fallback/stale clearing and forecast-only degradation now follow `AVAILABILITY.md`. | Fixed |
| Medium | Importing `const.py` called `logging.basicConfig`, which can change the process-wide root logger when no handler has been configured yet. | An import/reload regression captured the call. The integration now obtains its namespaced logger without configuring Home Assistant's global logging policy. | Fixed |
| Medium | The selected upstream parser can include full FMI response content in its own error logs after structurally valid XML fails deeper parsing; coordinator debug messages also contain configured coordinates. This is a privacy/diagnostic-output question, not required for the availability fix. | S14 removed configured-coordinate debug output, sanitized external error detail, and installed a dependency-logger filter that retains the generic parser error without raw dictionary/XML or coordinate-bearing dependency debug records. | Fixed in S14 |
| Low | A lightning bounding box at exactly a geographic pole produces an impractically large longitude span because the parallel radius approaches zero. | S14 clamps the latitude and uses the full valid longitude span when the radius reaches a pole or crosses the antimeridian. | Fixed in S14 |

## Candidate-Risk Disposition

| Plan hypothesis | Classification | Evidence |
|---|---|---|
| Forecast initialization disables observations | Not reproducible after S04 | Independent first refreshes and Home Assistant tests preserve a working station or place fallback. |
| Failed refresh leaves stale primary data available | Fixed | Known FMI errors, timeouts, request transport failures, and malformed current responses now clear stale current/forecast data; entity availability follows coordinator success. |
| `None` observation is accepted as success | Not reproducible after S04 | Both place and station `None` results are explicit no-data failures. |
| Partial-date grouping or best-time arithmetic | Not reproducible after S05/S08 | Full local dates, month/year/leap/DST cases, and aware timestamps are covered. |
| Missing, NaN, infinite, string, or unexpected FMI values crash output | Not reproducible after S06/S08/S09, except the fixed source-boundary defect | Numeric normalization and malformed fixtures cover entity, forecast, lightning, and sea-level paths; adapter contract failures now degrade at their owning source. |
| Polar sun events are absent | Not reproducible after S08 | Missing, naive, or inconsistent sun events use the documented deterministic fallback. |
| Wind-gust field mismatch | Not reproducible after S06 | The one-request adapter maps hourly maximum gust with finite native fallback. |
| Duplicate/manual coordinator listeners | Not reproducible | Entities use `CoordinatorEntity`; reload/unload tests prove listeners are removed and not duplicated. |
| Optional source failure disables core weather | Not reproducible after S09 | Optional failures clear only lightning/sea-level state and are outside primary availability. |
| Optional HTTP lacks status, timeout, size, or shape bounds | Not reproducible after S09 | HA-managed aiohttp, 2/3/5-second connect/read/total bounds, a 2 MiB limit, status classification, and XML/array validation are tested. |
| Lightning age units, array alignment, or per-strike geocoding amplify work | Not reproducible after S09 | Aware minute boundaries, equal-array validation, address caching, one lookup per update, and process-wide rate limiting are tested. |
| Global logging configuration | Medium, fixed in S13 | `logging.basicConfig` was reproduced and removed. |
| Legacy/deprecated weather or sensor APIs | Not reproducible | Current entity classes, native units, forecast methods, and feature flags pass Home Assistant 2026.7.4; the full suite also passes with warnings treated as errors. |
| Mutable coordinates control identity | Not reproducible after S07/S11 | Stable config/device identity and conservative idempotent registry migration are covered. |
| Exact coordinates in logs/diagnostics | Fixed in S14 | Sentinel-coordinate regressions cover integration debug/error, upstream parser payload logs, config-flow validation, and redacted diagnostics. |
| Dependency/runtime graph defect | Audited in S14 | The integration runtime closure is clean; the formal owner exception remains limited to two exact stable-HA pins and is fixed in current beta. |

## Focused Runtime Review

- **Event loop:** Coordinate current/forecast calls execute the synchronous client through `asyncio.to_thread`; observation calls use the client's executor-backed async methods. Lightning/sea-level HTTP uses Home Assistant's shared async session, while XML parsing and Nominatim reverse geocoding use `async_add_executor_job`. The adapter regression wraps the synchronous boundary with Home Assistant's `protect_loop` and records worker thread IDs distinct from the event-loop thread.
- **Lifecycle and isolation:** First refreshes are independent, one config-entry update listener is registered, `CoordinatorEntity` owns entity listeners, unload/reload removes them, and simultaneous entries retain separate coordinators and failures.
- **Freshness and availability:** Current, forecast, station, lightning, and sea-level states clear at their own failure boundaries and recover on later refreshes. Empty/`None` data is not treated as success.
- **Timeouts and retries:** Synchronous FMI requests use the selected client's ten-second timeout inside a 40-second primary coordinator bound. Optional HTTP uses the documented 2/3/5-second bounds. Runtime updates do not add retries; only the marker-isolated live probe retries once.
- **Request volume:** A normal primary refresh makes one current request and one hourly forecast request, plus the always-exposed sea-level request; configured station and lightning features add one request at their own 10/30-minute cadence. Place observation adds one request only after current failure. No entity calls `async_request_refresh` from an update callback.
- **Network boundaries:** Production network access is limited to the FMI adapter/client worker boundary, the HA-managed optional-source session, and executor-isolated Nominatim enrichment. Ordinary tests remain socket-blocked.
- **Options and values:** UI options use bounded schemas. Cross-field minimum/maximum ordering can intentionally produce no best-time match rather than a crash. Corrupt out-of-band config storage is not treated as a supported input API.
- **Warnings:** The complete offline suite passes with Python warnings and deprecations treated as errors.

## Coverage Closure

The S10 baseline gaps were behavioral, not excluded or hidden:

- `fmi_client.py`: raised from 93.93% lines / 64.28% branches to 100% line and branch coverage. Tests cover absent/misaligned gust fields, both parameter insertion positions, duplicate avoidance, non-string dependency parameters, empty current results, finite gust precedence, request count, timesteps, and worker-thread execution.
- `utils.py`: raised from 90.41% lines / 92.85% branches to 100% line and branch coverage. Boolean numeric sentinels are explicitly rejected. The unused Finland-wide bounding-box helper and its unused constants were removed after repository-wide reference search found no runtime caller; the active coordinate-radius helper remains behaviorally covered.

The complete offline run reports 96% aggregate branch-aware coverage. Every integration module remains at or above 95% line coverage; S13 did not add exclusions or coverage pragmas.

## Report Review

The canonical fork had no open or closed reports or pull requests in the anonymous GitHub API inventory on 2026-08-01. The previously inventoried open maintenance descriptions remain fully represented in the plan matrix; no new report appeared after the S00 cutoff.

Recent closed descriptions were checked for regression signals. Forecast service output remains a native list through Home Assistant tests, forecast and observation use separate 30/10-minute coordinators, entity callbacks do not request refreshes, missing forecast values remain `None`, and the formerly uninformative fetch-error path now records classified source details. The missing integration-card icon report is repository metadata rather than runtime correctness and remains outside S13.

## Sources

- Canonical repository and report inventory: <https://github.com/kogeler/fmi-hass-custom>, checked 2026-08-01.
- Home Assistant blocking-operation guidance: <https://developers.home-assistant.io/docs/asyncio_blocking_operations/>, checked 2026-08-01.
- Home Assistant coordinator/polling guidance: <https://developers.home-assistant.io/docs/integration_fetching_data/>, checked 2026-08-01.
- Installed Home Assistant 2026.7.4 `DataUpdateCoordinator`, weather entity, and loop-protection source, inspected in the pinned Podman environment on 2026-08-01.
- Installed `fmi-weather-client` 1.0.0 async wrappers, HTTP timeout/error handling, parser, and model source, inspected in the pinned Podman environment on 2026-08-01.
