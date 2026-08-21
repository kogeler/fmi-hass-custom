<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Time And Missing-Data Contract

## Assertions

### `TIM-001` — Clear-condition day/night conversion is deterministic

**Contract:** FMI clear symbol `1` MUST map to `clear-night` at or outside valid aware sunrise and
sunset boundaries and to `sunny` between them. Missing, naive, or inconsistent sun events MUST
fall back to `sunny`; unknown, non-integral, malformed, NaN, or infinite symbols MUST expose no
condition rather than inventing one.

**Evidence:**

- [`test_clear_symbol_uses_aware_sun_boundaries`](../../tests/test_time_and_missing_data.py) — `tests/test_time_and_missing_data.py::test_clear_symbol_uses_aware_sun_boundaries`
- [`test_clear_symbol_falls_back_to_day_when_sun_events_are_incomplete`](../../tests/test_time_and_missing_data.py) — `tests/test_time_and_missing_data.py::test_clear_symbol_falls_back_to_day_when_sun_events_are_incomplete`
- [`test_unknown_or_invalid_weather_symbol_has_no_condition`](../../tests/test_time_and_missing_data.py) — `tests/test_time_and_missing_data.py::test_unknown_or_invalid_weather_symbol_has_no_condition`

### `TIM-002` — External numeric values normalize without fabrication

**Contract:** Finite numbers and numeric strings MAY normalize to `float`; booleans, malformed
strings, `None`, NaN, and infinities MUST be treated as missing. One invalid field MUST NOT abort
the remaining sample, and an empty forecast MUST expose empty hourly/daily results.

**Evidence:**

- [`test_hourly_forecast_accepts_numeric_strings_and_rejects_invalid_values`](../../tests/test_time_and_missing_data.py) — `tests/test_time_and_missing_data.py::test_hourly_forecast_accepts_numeric_strings_and_rejects_invalid_values`
- [`test_hourly_forecast_treats_missing_fields_as_unavailable`](../../tests/test_time_and_missing_data.py) — `tests/test_time_and_missing_data.py::test_hourly_forecast_treats_missing_fields_as_unavailable`
- [`test_empty_forecast_returns_empty_hourly_and_daily_lists`](../../tests/test_time_and_missing_data.py) — `tests/test_time_and_missing_data.py::test_empty_forecast_returns_empty_hourly_and_daily_lists`

### `TIM-003` — Best-time candidates are complete remaining local-day hours

**Contract:** Best time MUST consider only configured-interval forecast samples with aware
timestamps that are not in the past and fall on the current Home Assistant local date. A candidate
MUST contain finite symbol, air/apparent temperature, humidity, sustained wind, precipitation,
PoP, and thunder probability; current observations/time and later days MUST NOT be fallbacks.

**Evidence:**

- [`test_best_time_uses_only_remaining_configured_interval_samples`](../../tests/test_time_and_missing_data.py) — `tests/test_time_and_missing_data.py::test_best_time_uses_only_remaining_configured_interval_samples`
- [`test_best_time_stays_on_current_local_date_across_calendar_boundaries`](../../tests/test_time_and_missing_data.py) — `tests/test_time_and_missing_data.py::test_best_time_stays_on_current_local_date_across_calendar_boundaries`
- [`test_best_time_requires_every_complete_finite_metric`](../../tests/test_time_and_missing_data.py) — `tests/test_time_and_missing_data.py::test_best_time_requires_every_complete_finite_metric`

### `TIM-004` — Best-time hard gates and ordering are fixed

**Contract:** Candidate symbols MUST be limited to FMI codes `1`, `2`, `21`, `3`, `31`, `32`, `41`,
`42`, `51`, `52`, `91`, and `92`; symbol membership and configured apparent-temperature, humidity,
wind, and precipitation limits MUST be inclusive hard gates. Eligible candidates MUST minimize, in
order: thunder probability, distance from the configured feels-like midpoint, PoP, precipitation
amount, then aware timestamp. The integration MUST NOT expose or use a weighted comfort score.

**Evidence:**

- [`test_best_time_uses_frozen_lexicographic_order`](../../tests/test_time_and_missing_data.py) — `tests/test_time_and_missing_data.py::test_best_time_uses_frozen_lexicographic_order`
- [`test_best_time_includes_every_configured_boundary`](../../tests/test_time_and_missing_data.py) — `tests/test_time_and_missing_data.py::test_best_time_includes_every_configured_boundary`
- [`test_best_time_prefers_apparent_comfort_over_hottest_hour`](../../tests/test_time_and_missing_data.py) — `tests/test_time_and_missing_data.py::test_best_time_prefers_apparent_comfort_over_hottest_hour`
- [`test_best_time_allowed_fmi_symbols_match_contract`](../../tests/test_time_and_missing_data.py) — `tests/test_time_and_missing_data.py::test_best_time_allowed_fmi_symbols_match_contract`

### `TIM-005` — Best-time empty and unavailable outcomes are distinct

**Contract:** A healthy forecast with no remaining current-day hour or with complete hours rejected
by limits MUST expose available `no_suitable_time`. Disabled, failed, empty, timestamp-unusable, or
entirely incomplete remaining data MUST make the entity unavailable. Both outcomes MUST clear a
prior selected state and its dynamic attributes and MUST recover on later complete data.

**Evidence:**

- [`test_best_time_reports_no_suitable_hour_without_current_weather_fallback`](../../tests/test_time_and_missing_data.py) — `tests/test_time_and_missing_data.py::test_best_time_reports_no_suitable_hour_without_current_weather_fallback`
- [`test_best_time_clears_selection_for_empty_and_unusable_results`](../../tests/test_time_and_missing_data.py) — `tests/test_time_and_missing_data.py::test_best_time_clears_selection_for_empty_and_unusable_results`
- [`test_best_time_reports_no_suitable_when_today_has_no_remaining_hour`](../../tests/test_time_and_missing_data.py) — `tests/test_time_and_missing_data.py::test_best_time_reports_no_suitable_when_today_has_no_remaining_hour`

### `TIM-006` — Best-time options preserve stored compatibility

**Contract:** Submitted inverted min/max pairs MUST be rejected without partial persistence.
Historical inverted values MUST remain loadable and unchanged until explicitly corrected, and
while inverted they MUST produce `no_suitable_time` rather than silent swapping or migration.

**Evidence:**

- [`test_options_flow_rejects_inverted_best_time_ranges_without_persisting`](../../tests/test_config_flow.py) — `tests/test_config_flow.py::test_options_flow_rejects_inverted_best_time_ranges_without_persisting`
- [`test_options_flow_loads_stored_inverted_range_without_mutating_it`](../../tests/test_config_flow.py) — `tests/test_config_flow.py::test_options_flow_loads_stored_inverted_range_without_mutating_it`
- [`test_best_time_treats_stored_inverted_limits_as_no_suitable_result`](../../tests/test_time_and_missing_data.py) — `tests/test_time_and_missing_data.py::test_best_time_treats_stored_inverted_limits_as_no_suitable_result`

### `TIM-007` — Selected Best-time state remains registry-compatible and transparent

**Contract:** A selected result MUST retain the existing `HH:MM` state and legacy attributes and
MAY add aware apparent-temperature, PoP, and thunder-probability attributes. Options reload MUST
reselect without replacing the entity; state MUST NOT expose internal rank, score, raw forecast,
coordinates, or immutable identity.

**Evidence:**

- [`test_best_time_selected_state_preserves_and_extends_attributes`](../../tests/test_lifecycle.py) — `tests/test_lifecycle.py::test_best_time_selected_state_preserves_and_extends_attributes`
- [`test_best_time_options_reload_reselects_without_replacing_entity`](../../tests/test_lifecycle.py) — `tests/test_lifecycle.py::test_best_time_options_reload_reselects_without_replacing_entity`
