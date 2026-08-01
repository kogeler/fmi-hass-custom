<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Compatibility, Security, and Privacy Audit

Audited 2026-08-01 from base commit `c919057c6ddc39283bd88ba75bdf061b55ea9159`. The supported environment is Home Assistant 2026.7.4 on Python 3.14.2 with `fmi-weather-client` 1.0.0. Home Assistant's Integration Quality Scale is used only as guidance for this custom integration; no Core tier is claimed.

## Result

No critical finding remains. Precise configured coordinates and raw external response content could reach debug/error logs; those privacy paths are fixed and regression-tested. The only known High dependency findings are the already owner-accepted Pillow/PyJWT versions required exactly by current stable Home Assistant. They remain formally blocked upstream in `TODO.md`; the integration runtime closure itself audits cleanly.

| Severity | Finding | Resolution / status |
|---|---|---|
| High | The dependency parser logged the complete FMI response at error level after a structurally valid response failed deeper parsing. Config-flow tracebacks and coordinator error details could also include arbitrary external text, including configured coordinates. | Fixed. A dependency-logger privacy filter retains the generic parser failure while dropping raw dictionaries/XML and coordinate-bearing request/place debug records. Integration logs now keep only exception class or HTTP status, and config-flow validation logs no traceback. Regression tests use precise sentinel coordinates and fail if they appear. |
| High, blocked upstream | The complete stable HA test graph contains 28 advisory rows for Pillow 12.2.0 and PyJWT 2.12.1; fixed versions are 12.3.0 and 2.13.0. HA 2026.7.4 requires the affected versions exactly. | Formal owner exception remains in `TODO.md`. Neither package is imported or declared by this integration, and its separately resolved runtime closure reports no known vulnerability. HA 2026.8.0b3 already pins both fixed versions, but a prerelease is not substituted for stable. |
| Medium | Per-entry coordinators/listener were stored as an untyped nested `hass.data` dictionary rather than the current `ConfigEntry.runtime_data` contract. | Fixed with typed `FMIConfigEntry`/`FMIEntryRuntimeData`; setup, reload, failed unload, multi-entry isolation, migrations, and removal remain covered through public HA lifecycle tests. |
| Medium | No user-downloadable diagnostics existed, and returning config data naively would reveal latitude, longitude, or the coordinate-derived legacy entity identity. | Fixed with diagnostics that redact all three fields and expose only options, config version, poll cadence, success state, and source booleans. No place, weather model, response payload, entry ID, or unique ID is returned. |
| Medium, accepted for private testing | Optional lightning address enrichment sends public FMI strike coordinates to the public OSMF Nominatim service on a cache miss. This is periodic application use, which the policy discourages at scale. | It does not send the configured home coordinates, is disabled unless lightning is enabled, caches results, uses one worker, identifies the repository, displays attribution, resolves at most one address per update, and is globally limited to 4 requests/minute. This fits the owner's current single-user testing, not an assumed public user base. `TODO.md` requires removal, a switchable provider, or an owner-controlled service before broader distribution. |
| Medium, S15-owned | Workflow actions are SHA-pinned and permissions are read-only, but the selected hassfest and HACS actions internally run mutable `ghcr.io/home-assistant/hassfest` and `ghcr.io/hacs/action:main` images. Required CI also lacks dependency automation/review. | Documented for S15, which already owns production CI/CD. The mutable validation containers receive no repository secrets; the HACS job's token is read-only and the repository is public. This is not a stable runtime blocker. |
| Low | A lightning radius centered exactly at either pole generated latitude/longitude values outside WGS84 request limits. | Fixed by clamping latitude and using the full valid longitude range when a radius reaches a pole or crosses the antimeridian. Core weather remains independent. |

## Home Assistant Guidance Review

| Area | S14 result |
|---|---|
| Runtime data and typing | Per-entry runtime state now uses typed `ConfigEntry.runtime_data`. Mypy has a zero-error 29-file baseline; strict Platinum typing is not claimed. |
| Config flows | User, options, and reconfigure flows use current UI APIs, validate FMI connectivity, reject duplicates, retain stable identity, and are fully covered. FMI has no credentials, so reauthentication is not applicable. |
| Coordinators and availability | Current/forecast and optional sources use a 30-minute coordinator; a configured station uses an independent 10-minute coordinator. Outage/recovery is logged once per transition and entities follow coordinator/source availability. |
| Weather | Hourly/daily forecasts use the separate async APIs, cached data, current feature flags, native units, and UTC RFC 3339 timestamps. Subscriber updates are lifecycle-tested. |
| Sensors | Entities publish native values/units, current device/state classes where applicable, translated names, stable unique IDs, service devices, and no entity-driven polling. |
| Naming and registries | `has_entity_name` and device context produce current names while conservative migrations preserve established unique/custom entity IDs. |
| Unload/reload | Listener cleanup, failed unload retention, option reload, removal, migration, and multi-entry isolation pass through Home Assistant APIs. |
| Diagnostics | Implemented with explicit coordinate and legacy-identity redaction; no external payload or weather/location value is included. |
| Polling and parallel updates | The established 30/10-minute coordinator intervals remain appropriate for FMI data. Both read-only coordinator platforms explicitly set `PARALLEL_UPDATES = 0`, matching current HA guidance. |
| Fully async dependency | Not claimed. The selected FMI client uses `requests` behind `asyncio.to_thread`; Nominatim uses HA's executor. Integration-owned optional HTTP uses HA's shared aiohttp session. |

Documentation-oriented quality rules remain assigned to S16. Branding/tier metadata is not added because this repository is a HACS custom integration and does not claim an official Core quality tier.

## Support Matrix

| Environment | Policy | Evidence |
|---|---|---|
| Home Assistant 2026.7.4 / Python 3.14.2 | Supported current stable | Exact frozen environment; complete offline lifecycle/config/entity/migration suite, typing, lint, coverage, layout, and hassfest validation pass. Remote HACS/workflow execution remains an S15 release gate. |
| Home Assistant 2026.6.x | Not supported/retained | This pre-1.0 maintenance line supports current stable only. No previous-stable claim is made, avoiding an untested compatibility promise. |
| Home Assistant 2026.8.0b2 / helper 0.13.350 | Informational beta | Matching beta harness installs cleanly and the full offline suite passes. |
| Home Assistant 2026.8.0b3 / helper 0.13.350 | Informational latest beta | The full offline suite passes after replacing only HA with b3. The helper still requires b2 exactly, so `pip check` correctly reports that harness metadata mismatch; it is not a stable blocker. |

The v0.6.2 config/registry migration cases run inside the stable and beta suites, covering upgrade behavior as part of the same matrix.

## Dependency and License Review

- `make audit` remains nonzero with exactly the 28 Pillow/PyJWT advisory rows described above. No advisory was ignored or suppressed.
- A separate fresh resolution of `fmi-weather-client==1.0.0` and `geopy==2.5.0` reports no known vulnerability.
- `make licenses` succeeds with no unknown license. The runtime FMI client is GPL-3.0 and geopy is MIT; the complete development graph also includes copyleft packages selected by HA/test tooling. No dependency source was copied into this MIT repository. Bundling or redistributing third-party packages requires following their own licenses; this inventory is not a legal compatibility opinion.
- All selected direct runtime/development packages remain their newest stable versions. The 24 outdated entries are transitive selections constrained by HA, its test helper, or their resolver-compatible parents; none is independently overridden.
- The complete root freeze remains generated and unchanged because no direct dependency selection changed in S14.

## Data and Privacy Boundaries

- FMI necessarily receives configured coordinates for setup validation, current/forecast, sea-level, and optional centered lightning-bbox requests. Responses are processed in memory and are not included in diagnostics.
- Nominatim receives only coordinates of public lightning strikes selected from FMI results, never the configured coordinate. It may return an address exposed intentionally as the lightning sensor value; raw strike coordinates remain its documented fallback.
- Normal integration logs contain source names, transitions, HTTP status classes, and exception class names only. The selected dependency's coordinate/request and response-body log records are filtered at its logger boundary.
- Entity states still expose the configured FMI place name and weather/lightning data because those are the integration's intended user-facing outputs. They are not copied into diagnostics.

## Workflow Review

- The workflow grants only `contents: read`, defines cancellation concurrency, uses bounded timeouts, pins `actions/checkout` to the current v7.0.1 commit, and pins the Python image by digest.
- The hassfest/HACS action source references are immutable SHAs and their repository licenses are known. Their internal mutable image references are the S15 finding above.
- The interim live probe deliberately runs after offline tests in the same blocking workflow, per owner direction. It has no secrets and uses public fixed locations with a documented request budget. S15 owns its final topology.
- No workflow interpolates pull-request-controlled text into shell commands. Dependency-review, scheduled drift checks, and update automation remain explicit S15 deliverables.

## Sources

Checked 2026-08-01:

- Home Assistant quality rules: <https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/>
- Runtime data: <https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/runtime-data/>
- Diagnostics and coordinate redaction: <https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/diagnostics/>
- Coordinator/polling guidance: <https://developers.home-assistant.io/docs/integration_fetching_data/>
- Parallel updates: <https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/parallel-updates/>
- Weather API: <https://developers.home-assistant.io/docs/core/entity/weather/>
- Sensor API: <https://developers.home-assistant.io/docs/core/entity/sensor/>
- Home Assistant releases: <https://pypi.org/project/homeassistant/>
- Home Assistant custom-component test helper: <https://pypi.org/project/pytest-homeassistant-custom-component/>
- OSMF Nominatim usage/privacy policy: <https://operations.osmfoundation.org/policies/nominatim/>
- Checkout release/source: <https://github.com/actions/checkout/releases/tag/v7.0.1>
- Hassfest action source: <https://github.com/home-assistant/actions/blob/ab22029681aa532bfe7de5774a9972d67bfbd2c0/hassfest/action.yml>
- HACS action source: <https://github.com/hacs/action/blob/1ebf01c408f29afcb6406bd431bc98fd8cbb15aa/action.yml>
- Vulnerability records: <https://osv.dev/vulnerability/PYSEC-2026-2253> and <https://osv.dev/vulnerability/PYSEC-2026-179>
