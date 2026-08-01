<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Runtime Architecture And Invariants

This document is the maintenance contract for coordinator ownership, I/O boundaries, availability,
and runtime side effects. Read it before changing `custom_components/fmi/__init__.py`,
`fmi_client.py`, or any entity platform. The supported reference environment is declared in
`hacs.json` and the committed dependency freeze. Keep historical investigation outside this
current contract.

## Entry Ownership And Lifecycle

- Each config entry owns one typed `FMIConfigEntryRuntimeData` value in
  `ConfigEntry.runtime_data`.
- The main coordinator refreshes current weather, hourly source forecasts, lightning when enabled,
  and sea level every 30 minutes. A configured observation station uses its own 10-minute
  coordinator.
- `CoordinatorEntity` owns entity listeners. Setup registers one config-entry update listener;
  unload and failed-unload paths must retain or remove runtime state consistently.
- Reload, options updates, reconfiguration, and simultaneous entries must not share coordinators,
  callbacks, identity, or availability state.
- Entity properties read cached coordinator data only. They must not perform I/O or request a
  refresh from an update callback.

## Event-Loop And Network Boundaries

- Coordinate current/forecast work in the synchronous FMI client runs outside the event loop
  through `asyncio.to_thread`. Observation helpers use the client's executor-backed async API.
- Integration-owned lightning and sea-level HTTP uses Home Assistant's shared aiohttp session.
  XML parsing and Nominatim reverse geocoding run through `async_add_executor_job`.
- Cancellation must propagate. Source boundaries catch only the documented finite transport,
  client/server, parser, and external-shape exceptions; do not replace them with a broad
  `Exception` catch.
- Ordinary tests block sockets. Only the marker-isolated probes described in `LIVE_TESTS.md` may
  use real network access.

## Source Failure Boundaries

| Source | Success and fallback | Failure behavior |
|---|---|---|
| Current weather | Use the forecast-current query; fall back to place observation when current fails | Clear stale current data; setup may still succeed from a configured station |
| Hourly source forecast | Normalize the complete one-hour series independently of current data | Clear only forecast data; retain usable current or observation state |
| Configured station | Refresh on its independent coordinator | Clear only station state; never disable working place/current data |
| Lightning | Optional and enabled through entry options | Clear only lightning state; core weather remains available |
| Sea level | Best-effort for every configured location | Clear only sea-level state; core weather remains available |

Initial setup succeeds when either the primary current path, including place fallback, or a
configured station produces usable data. Forecast and optional-source failures alone do not force
setup retry. Every source recovers on a later successful refresh without recreating entities.
Transition logging should report an outage and recovery once, not on every poll.

## Data, Timeouts, And Request Volume

- Empty results and `None` are no-data failures. Numeric boundaries accept finite values and reject
  booleans, malformed strings, NaN, and infinities without fabricating zeroes.
- FMI dependency requests use the client's ten-second HTTP timeout inside the 40-second primary
  coordinator bound. Optional HTTP uses 2-second connect, 3-second read, and 5-second total
  timeouts plus a 2 MiB response limit.
- Runtime refreshes add no retry loop. A normal primary refresh makes one current request, one
  hourly forecast request, and one sea-level request. Place observation is requested only after a
  current failure. Station and enabled lightning each add one request on their own cadence.
- Forecast, optional-source timestamp, and missing-value semantics are defined in
  `FORECAST_SEMANTICS.md`, `TIME_AND_MISSING_DATA.md`, and `OPTIONAL_SOURCES.md`.

## Logging And Diagnostics

The integration must not configure the process-wide root logger. Logs may contain source names,
availability transitions, HTTP status classes, and exception class names, but not configured
coordinates, coordinate-derived identity, raw FMI/XML responses, or arbitrary external exception
text. The FMI dependency logger filter must continue to remove coordinate-bearing request records
and raw parser payloads.

Diagnostics expose only sanitized configuration/options, config version, poll cadence, coordinator
success, and source availability flags. They must not expose coordinates, place/weather values,
entry or entity identity, or external payloads. See `COMPATIBILITY_SECURITY.md` for the complete
privacy boundary.

## Verification Map

- `tests/test_availability.py`: setup, independent source failure, stale clearing, and recovery.
- `tests/test_lifecycle.py`: setup/unload/reload, listener ownership, multi-entry isolation, and
  public entity/forecast behavior.
- `tests/test_runtime_audit.py`: no process-wide logging configuration.
- `tests/test_compatibility_security.py`: executor boundaries, logging privacy, diagnostics,
  optional HTTP bounds, and polar bounding boxes.
- `tests/test_auxiliary_payloads.py`: optional-source parsing, timestamps, freshness, and failures.

Run `make test-full`, `make type-check`, and `make test-network-block` after changing these
contracts. Use `make live` only when the change can affect the external FMI boundary.

## References

- [Home Assistant blocking-operation guidance](https://developers.home-assistant.io/docs/asyncio_blocking_operations/)
- [Home Assistant coordinator and polling guidance](https://developers.home-assistant.io/docs/integration_fetching_data/)
- [Home Assistant diagnostics rules](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/diagnostics/)
