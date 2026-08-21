<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Availability Contract

## Assertions

### `AVL-001` — Initial setup requires one usable current source

**Contract:** Initial setup MUST succeed when either the primary current path (including place
fallback) or a configured station returns usable data; it MUST enter `setup_retry` when neither
does. A failure in one path MUST NOT disable a working independent path.

**Evidence:**

- [`test_observation_by_place_loads_when_forecast_wfs_fails`](../../tests/test_availability.py) — `tests/test_availability.py::test_observation_by_place_loads_when_forecast_wfs_fails`
- [`test_station_observation_loads_when_all_forecast_sources_fail`](../../tests/test_availability.py) — `tests/test_availability.py::test_station_observation_loads_when_all_forecast_sources_fail`
- [`test_both_current_sources_fail_initial_setup`](../../tests/test_availability.py) — `tests/test_availability.py::test_both_current_sources_fail_initial_setup`

### `AVL-002` — Current fallback and stale clearing are atomic

**Contract:** A failed forecast-current request MUST fall back to the configured place observation;
if both fail after prior success, current and dependent forecast state MUST clear instead of
remaining available as stale data. Primary timeouts MUST follow the same rule.

**Evidence:**

- [`test_transport_error_uses_place_fallback_and_clears_stale_current`](../../tests/test_availability.py) — `tests/test_availability.py::test_transport_error_uses_place_fallback_and_clears_stale_current`
- [`test_current_outage_clears_stale_data_and_recovers`](../../tests/test_availability.py) — `tests/test_availability.py::test_current_outage_clears_stale_data_and_recovers`
- [`test_primary_deadline_timeout_clears_stale_data_and_recovers`](../../tests/test_availability.py) — `tests/test_availability.py::test_primary_deadline_timeout_clears_stale_data_and_recovers`

### `AVL-003` — Forecast state is independent and never silently stale

**Contract:** Forecast transport, parser, shape, `None`, or empty-result failure MUST clear the
previous forecast collection while preserving usable current or station state. The coordinator
MUST retain a complete one-hour source series even when a legacy display interval is coarser.

**Evidence:**

- [`test_forecast_clears_stale_data_and_recovers_without_log_spam`](../../tests/test_availability.py) — `tests/test_availability.py::test_forecast_clears_stale_data_and_recovers_without_log_spam`
- [`test_malformed_forecast_keeps_current_weather_available`](../../tests/test_availability.py) — `tests/test_availability.py::test_malformed_forecast_keeps_current_weather_available`
- [`test_coarse_legacy_interval_preserves_hourly_forecast_source`](../../tests/test_availability.py) — `tests/test_availability.py::test_coarse_legacy_interval_preserves_hourly_forecast_source`

### `AVL-004` — Probability supplements follow their owning sample set

**Contract:** Current probabilities MUST be replaced or cleared with forecast-backed current data;
future probabilities MUST be replaced or cleared with their timestamped forecast collection.
Missing or invalid probability data MUST NOT invalidate unrelated weather fields, and recovery
MUST NOT require entity recreation or reload.

**Evidence:**

- [`test_probability_supplements_replace_clear_and_recover_atomically`](../../tests/test_availability.py) — `tests/test_availability.py::test_probability_supplements_replace_clear_and_recover_atomically`
- [`test_probability_sensors_clear_and_recover_without_reload`](../../tests/test_sensor_entities.py) — `tests/test_sensor_entities.py::test_probability_sensors_clear_and_recover_without_reload`
- [`test_partial_metric_failure_preserves_independent_sources_and_recovers`](../../tests/test_lifecycle.py) — `tests/test_lifecycle.py::test_partial_metric_failure_preserves_independent_sources_and_recovers`

### `AVL-005` — Optional sources fail and recover independently

**Contract:** Lightning and sea-level failures MUST clear only their owning state and MUST NOT fail
current weather, observations, or forecasts. A successful empty lightning response MUST remain
available as `no_strikes`; later valid data MUST restore either optional sensor automatically.

**Evidence:**

- [`test_optional_source_failure_does_not_disable_current_weather`](../../tests/test_availability.py) — `tests/test_availability.py::test_optional_source_failure_does_not_disable_current_weather`
- [`test_lightning_empty_failure_and_recovery_transitions`](../../tests/test_lifecycle.py) — `tests/test_lifecycle.py::test_lightning_empty_failure_and_recovery_transitions`
- [`test_optional_failure_clears_stale_data_and_success_recovers`](../../tests/test_auxiliary_payloads.py) — `tests/test_auxiliary_payloads.py::test_optional_failure_clears_stale_data_and_success_recovers`

### `AVL-006` — Lifecycle recovery does not leak listeners or entry state

**Contract:** Coordinator entities MUST use Home Assistant listener ownership, unload/reload MUST
remove and restore only the affected entry state, and simultaneous entries MUST recover
independently. Repeated failures in one outage SHOULD emit one transition warning rather than one
warning per poll.

**Evidence:**

- [`test_partial_outage_unload_reload_cleans_coordinator_listeners`](../../tests/test_availability.py) — `tests/test_availability.py::test_partial_outage_unload_reload_cleans_coordinator_listeners`
- [`test_reload_unload_and_remove_do_not_duplicate_lifecycle_state`](../../tests/test_lifecycle.py) — `tests/test_lifecycle.py::test_reload_unload_and_remove_do_not_duplicate_lifecycle_state`
- [`test_two_locations_fail_and_recover_independently`](../../tests/test_lifecycle.py) — `tests/test_lifecycle.py::test_two_locations_fail_and_recover_independently`
