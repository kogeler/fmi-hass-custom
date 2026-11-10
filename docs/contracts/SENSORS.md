<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Sensor Contract

## Assertions

### `SNS-007` — Warning entities expose bounded independent state

**Contract:** Enabled warnings MUST add a count sensor, an enum level sensor, and a presence binary
sensor on the existing location device. Only active warnings MUST contribute to count/presence and
maximum severity. Level MUST use `none`, `green`, `yellow`, `orange`, `red`, or `unclassified`;
presence MUST NOT claim `safety`. The count sensor MUST expose detached active/future message lists,
future count, publication time, and requested language. Message fields MUST contain only
validated identity, event/classification, official localized text/area names/link, and UTC times.
Serialized warning attributes MUST NOT exceed 128 KiB or be silently truncated. Lists MUST be
excluded from Recorder attributes while remaining available in current entity state. Retrieval time
MUST NOT be an entity attribute, so an unchanged publication MUST NOT write a state change.
Active ordering MUST put unclassified severity first, followed by red/orange/yellow/green, then
onset and identifier; future ordering MUST prioritize onset before severity/identifier.

**Evidence:**

- [`test_warning_public_entities_follow_independent_source_and_recover`](../../tests/test_warning_entities.py) — `tests/test_warning_entities.py::test_warning_public_entities_follow_independent_source_and_recover`
- [`test_warning_onset_expiry_and_replacement_update_ha_without_network`](../../tests/test_warning_entities.py) — `tests/test_warning_entities.py::test_warning_onset_expiry_and_replacement_update_ha_without_network`
- [`test_warning_projection_overflow_is_unavailable`](../../tests/test_warnings_coordinator.py) — `tests/test_warnings_coordinator.py::test_warning_projection_overflow_is_unavailable`
- [`test_warning_recorder_excludes_large_attributes`](../../tests/test_warning_entities.py) — `tests/test_warning_entities.py::test_warning_recorder_excludes_large_attributes`
- [`test_warning_full_documented_dashboard_and_automation`](../../tests/test_warning_entities.py) — `tests/test_warning_entities.py::test_warning_full_documented_dashboard_and_automation`
- [`test_warning_real_utf8_presentation_boundaries`](../../tests/test_warnings_coordinator.py) — `tests/test_warnings_coordinator.py::test_warning_real_utf8_presentation_boundaries`
- [`test_warning_mixed_severity_sorting_and_repeated_publication`](../../tests/test_warnings_coordinator.py) — `tests/test_warnings_coordinator.py::test_warning_mixed_severity_sorting_and_repeated_publication`
- [`test_warning_future_ordering_prioritizes_onset_then_severity_and_id`](../../tests/test_warnings_coordinator.py) — `tests/test_warnings_coordinator.py::test_warning_future_ordering_prioritizes_onset_then_severity_and_id`
- [`test_warning_all_official_severity_colors`](../../tests/test_warnings_client.py) — `tests/test_warnings_client.py::test_warning_all_official_severity_colors`
- [`test_warning_unchanged_publication_writes_no_state_change`](../../tests/test_warning_entities.py) — `tests/test_warning_entities.py::test_warning_unchanged_publication_writes_no_state_change`

### `SNS-001` — Sensor metadata and ownership are stable

**Contract:** Every sensor MUST use a translated entity description, the appropriate native unit and
device/state class where applicable, a stable legacy-compatible unique-ID suffix, and the existing
location device. Warning sensors instead follow `SNS-007` metadata and `MIG-004` identity.
Fresh entries MUST use immutable coordinate-independent device identity; existing registry identity
MUST follow [the migration contract](MIGRATIONS.md).

**Evidence:**

- [`test_all_sensor_descriptions_have_current_units_and_types`](../../tests/test_sensor_entities.py) — `tests/test_sensor_entities.py::test_all_sensor_descriptions_have_current_units_and_types`
- [`test_fresh_sensors_use_location_device_context`](../../tests/test_sensor_entities.py) — `tests/test_sensor_entities.py::test_fresh_sensors_use_location_device_context`
- [`test_forecast_metric_sensors_expose_current_values_and_stable_identity`](../../tests/test_sensor_entities.py) — `tests/test_sensor_entities.py::test_forecast_metric_sensors_expose_current_values_and_stable_identity`
- [`test_shipped_translation_keys_match_runtime_surfaces`](../../tests/test_distribution.py) — `tests/test_distribution.py::test_shipped_translation_keys_match_runtime_surfaces`

### `SNS-002` — Forecast metric sensors preserve valid zero and isolate missing data

**Contract:** Feels like, dew point, pressure, three cloud layers, PoP, and thunder probability MUST
expose finite native values from the selected main-location sample: current data at the one-hour
interval, otherwise the selected forecast sample. Probability values MUST use the current
supplement for current data or the timestamp-aligned supplement for forecast data. Cloud and
probability values MUST be within 0–100; valid zero MUST remain available, while an invalid/missing
field MUST make only that sensor unavailable and MUST recover without recreation.

**Evidence:**

- [`test_forecast_metric_sensors_expose_current_values_and_stable_identity`](../../tests/test_sensor_entities.py) — `tests/test_sensor_entities.py::test_forecast_metric_sensors_expose_current_values_and_stable_identity`
- [`test_metric_sensor_missing_values_do_not_disable_independent_fields`](../../tests/test_sensor_entities.py) — `tests/test_sensor_entities.py::test_metric_sensor_missing_values_do_not_disable_independent_fields`
- [`test_sensor_availability_recovers_with_coordinator`](../../tests/test_sensor_entities.py) — `tests/test_sensor_entities.py::test_sensor_availability_recovers_with_coordinator`

### `SNS-003` — Forecast gust uses deterministic finite precedence

**Contract:** Forecast requests MUST add `HourlyMaximumGust` once in the existing WFS request.
Finite hourly maximum gust MUST take precedence over native `WindGust`; native gust MAY be retained
when the hourly field is missing. Sensor extraction MUST NOT substitute ordinary wind speed.

**Evidence:**

- [`test_client_adapter_maps_hourly_maximum_gust_with_finite_precedence`](../../tests/test_fmi_contract.py) — `tests/test_fmi_contract.py::test_client_adapter_maps_hourly_maximum_gust_with_finite_precedence`
- [`test_client_adapter_keeps_one_hourly_gust_parameter`](../../tests/test_fmi_contract.py) — `tests/test_fmi_contract.py::test_client_adapter_keeps_one_hourly_gust_parameter`
- [`test_wind_gust_finite_precedence_and_missing_values`](../../tests/test_sensor_entities.py) — `tests/test_sensor_entities.py::test_wind_gust_finite_precedence_and_missing_values`

### `SNS-004` — Probability supplements are timestamp-aligned and range-checked

**Contract:** `PoP` and `ProbabilityThunderstorm` MUST be parsed by response field name from the
same bounded forecast response, aligned by aware UTC timestamp, and represented outside the fixed
upstream model. Duplicate timestamps MUST retain the last row; invalid values MUST become missing
without clamping or timestamp reuse.

**Evidence:**

- [`test_client_adapter_parses_reordered_probability_fields_and_last_duplicate`](../../tests/test_fmi_contract.py) — `tests/test_fmi_contract.py::test_client_adapter_parses_reordered_probability_fields_and_last_duplicate`
- [`test_client_adapter_validates_probability_range_without_clamping`](../../tests/test_fmi_contract.py) — `tests/test_fmi_contract.py::test_client_adapter_validates_probability_range_without_clamping`
- [`test_probability_sensor_uses_configured_interval_sample_timestamp`](../../tests/test_sensor_entities.py) — `tests/test_sensor_entities.py::test_probability_sensor_uses_configured_interval_sample_timestamp`

### `SNS-005` — Home Assistant performs presentation-unit conversion

**Contract:** Temperature, pressure, and wind sensors/weather fields MUST declare their FMI-native
units and MUST allow Home Assistant to perform configured-system presentation conversion. The Rain
sensor MUST declare precipitation intensity in `mm/h`; the Weather entity MUST declare accumulated
precipitation in `mm`, with hourly values representing FMI `Precipitation1h` and daily values
following `FCS-004`. The integration MUST NOT numerically pre-convert cached native values.

**Evidence:**

- [`test_metric_sensors_and_weather_follow_ha_unit_conversion`](../../tests/test_lifecycle.py) — `tests/test_lifecycle.py::test_metric_sensors_and_weather_follow_ha_unit_conversion`
- [`test_hourly_forecast_uses_current_home_assistant_keys_and_units`](../../tests/test_forecast_characterization.py) — `tests/test_forecast_characterization.py::test_hourly_forecast_uses_current_home_assistant_keys_and_units`

### `SNS-006` — Lightning sensor state and attributes are deterministic

**Contract:** Successful empty lightning data MUST expose `no_strikes` without dynamic strike
attributes. A qualifying strike MUST expose textual distance/direction state plus top-level `time`,
`distance`, `bearing`, `direction`, `strikes`, `peak_current`, `cloud_cover`, and `ellipse_major`
attributes; `OBSERVATIONS` MUST contain remaining retained groups using the same schema. Coincident
coordinates MUST expose `HERE` with a null bearing. Failure MUST clear state and every dynamic
attribute.

**Evidence:**

- [`test_public_entity_and_forecast_contracts`](../../tests/test_lifecycle.py) — `tests/test_lifecycle.py::test_public_entity_and_forecast_contracts`
- [`test_lightning_empty_failure_and_recovery_transitions`](../../tests/test_lifecycle.py) — `tests/test_lifecycle.py::test_lightning_empty_failure_and_recovery_transitions`
- [`test_coincident_lightning_has_no_invented_bearing`](../../tests/test_lightning_geometry.py) — `tests/test_lightning_geometry.py::test_coincident_lightning_has_no_invented_bearing`
- [`test_coincident_lightning_sensor_exposes_here_without_bearing`](../../tests/test_sensor_entities.py) — `tests/test_sensor_entities.py::test_coincident_lightning_sensor_exposes_here_without_bearing`
