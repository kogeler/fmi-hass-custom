<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Runtime Contract

## Assertions

### `RUN-001` — Runtime ownership is per config entry

**Contract:** Each loaded config entry MUST own one typed runtime-data value containing its main
coordinator and, only when a station ID is configured, a separate observation coordinator.
Lightning and sea-level state MUST remain owned by that entry's main coordinator. Reload, options
updates, reconfiguration, failure, and simultaneous entries MUST NOT share callbacks, identity,
cached data, or availability state.

**Evidence:**

- [`test_reload_unload_and_remove_do_not_duplicate_lifecycle_state`](../../tests/test_lifecycle.py) — `tests/test_lifecycle.py::test_reload_unload_and_remove_do_not_duplicate_lifecycle_state`
- [`test_failed_platform_unload_retains_loaded_entry_data`](../../tests/test_lifecycle.py) — `tests/test_lifecycle.py::test_failed_platform_unload_retains_loaded_entry_data`
- [`test_two_entries_select_best_time_from_their_own_forecasts_and_options`](../../tests/test_lifecycle.py) — `tests/test_lifecycle.py::test_two_entries_select_best_time_from_their_own_forecasts_and_options`

### `RUN-002` — Polling cadence and platform concurrency are fixed

**Contract:** The main coordinator MUST use a 30-minute update interval, a configured station MUST
use a separate 10-minute interval, and both read-only entity platforms MUST declare
`PARALLEL_UPDATES = 0` so coordinator polling owns refresh concurrency.

**Evidence:**

- [`test_runtime_cadence_and_platform_parallelism_match_contract`](../../tests/test_contracts.py) — `tests/test_contracts.py::test_runtime_cadence_and_platform_parallelism_match_contract`
- [`test_diagnostics_redact_location_and_stable_identity`](../../tests/test_compatibility_security.py) — `tests/test_compatibility_security.py::test_diagnostics_redact_location_and_stable_identity`

### `RUN-003` — Blocking and integration-owned I/O stays off the event loop

**Contract:** Synchronous FMI client requests/parsing MUST run through an executor boundary.
Integration-owned lightning and sea-level HTTP MUST use Home Assistant's shared async session, and
their parsing MUST run in the executor. Entity state/property access MUST NOT initiate network I/O.

**Evidence:**

- [`test_selected_client_place_lookup_uses_executor_and_weather_model`](../../tests/test_fmi_contract.py) — `tests/test_fmi_contract.py::test_selected_client_place_lookup_uses_executor_and_weather_model`
- [`test_optional_http_uses_ha_session_bounded_timeout_and_executor`](../../tests/test_auxiliary_payloads.py) — `tests/test_auxiliary_payloads.py::test_optional_http_uses_ha_session_bounded_timeout_and_executor`
- [`test_public_entity_and_forecast_contracts`](../../tests/test_lifecycle.py) — `tests/test_lifecycle.py::test_public_entity_and_forecast_contracts`

### `RUN-004` — Cancellation and failure boundaries remain explicit

**Contract:** Cancellation MUST propagate through primary and optional update boundaries. Primary
boundaries MUST catch only classified FMI/transport/parser/shape failures; optional boundaries MAY
isolate an ordinary exception but MUST NOT consume cancellation or disable primary weather.

**Evidence:**

- [`test_optional_source_cancellation_propagates`](../../tests/test_auxiliary_payloads.py) — `tests/test_auxiliary_payloads.py::test_optional_source_cancellation_propagates`
- [`test_primary_source_timeout_clears_stale_data_and_recovers`](../../tests/test_availability.py) — `tests/test_availability.py::test_primary_source_timeout_clears_stale_data_and_recovers`
- [`test_optional_source_failure_does_not_disable_current_weather`](../../tests/test_availability.py) — `tests/test_availability.py::test_optional_source_failure_does_not_disable_current_weather`

### `RUN-005` — Normal refresh request topology is bounded

**Contract:** A normal primary refresh MUST make one forecast-current request, one hourly forecast
request, and one sea-level request with no internal retry loop. Place observation MAY add one
request only after current failure; a station and enabled lightning each own one independent
request. Probability and gust supplements MUST NOT add a second forecast request.

**Evidence:**

- [`test_client_adapter_adds_hourly_gust_without_second_request`](../../tests/test_fmi_contract.py) — `tests/test_fmi_contract.py::test_client_adapter_adds_hourly_gust_without_second_request`
- [`test_client_adapter_preserves_weather_and_forecast_timesteps`](../../tests/test_fmi_contract.py) — `tests/test_fmi_contract.py::test_client_adapter_preserves_weather_and_forecast_timesteps`
- [`test_normal_refresh_request_topology_and_deadlines_are_bounded`](../../tests/test_availability.py) — `tests/test_availability.py::test_normal_refresh_request_topology_and_deadlines_are_bounded`
- [`test_live_budget_is_shared_and_hard_bounded`](../../tests/test_live_contract.py) — `tests/test_live_contract.py::test_live_budget_is_shared_and_hard_bounded`

### `RUN-006` — Coordinator deadlines are explicit

**Contract:** Primary forecast/current work and configured-station observation work MUST each run
inside a 40-second coordinator-wide deadline. A timeout MUST clear the owning stale state and allow
a later refresh to recover.

**Evidence:**

- [`test_normal_refresh_request_topology_and_deadlines_are_bounded`](../../tests/test_availability.py) — `tests/test_availability.py::test_normal_refresh_request_topology_and_deadlines_are_bounded`
- [`test_primary_source_timeout_clears_stale_data_and_recovers`](../../tests/test_availability.py) — `tests/test_availability.py::test_primary_source_timeout_clears_stale_data_and_recovers`
- [`test_observation_deadline_timeout_clears_stale_data_and_recovers`](../../tests/test_availability.py) — `tests/test_availability.py::test_observation_deadline_timeout_clears_stale_data_and_recovers`
