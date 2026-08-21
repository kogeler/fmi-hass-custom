<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Forecast Semantics Contract

## Assertions

### `FCS-001` — Forecast samples normalize by aware timestamp

**Contract:** Forecast exposure MUST reject missing or timezone-naive timestamps, retain the last
sample for a duplicate timestamp, sort unique samples chronologically, and represent public
timestamps as aware UTC RFC 3339 values.

**Evidence:**

- [`test_forecast_sorts_and_deduplicates_timestamps`](../../tests/test_forecast_characterization.py) — `tests/test_forecast_characterization.py::test_forecast_sorts_and_deduplicates_timestamps`
- [`test_forecast_ignores_missing_and_timezone_naive_timestamps`](../../tests/test_time_and_missing_data.py) — `tests/test_time_and_missing_data.py::test_forecast_ignores_missing_and_timezone_naive_timestamps`
- [`test_hourly_forecast_preserves_both_dst_end_hours`](../../tests/test_forecast_characterization.py) — `tests/test_forecast_characterization.py::test_hourly_forecast_preserves_both_dst_end_hours`

### `FCS-002` — Hourly forecast uses the standard Home Assistant schema

**Contract:** Each normalized sample MUST expose the standard Home Assistant hourly condition,
temperature, apparent temperature, precipitation, wind, gust, bearing, pressure, humidity, cloud,
dew-point, and PoP fields in native units when finite. PoP MUST be range-checked and converted to
Home Assistant's integer field with Python half-to-even rounding; missing values MUST remain
`None`, not zero.

**Evidence:**

- [`test_hourly_forecast_uses_current_home_assistant_keys_and_units`](../../tests/test_forecast_characterization.py) — `tests/test_forecast_characterization.py::test_hourly_forecast_uses_current_home_assistant_keys_and_units`
- [`test_hourly_precipitation_probability_validates_and_rounds_half_even`](../../tests/test_forecast_characterization.py) — `tests/test_forecast_characterization.py::test_hourly_precipitation_probability_validates_and_rounds_half_even`
- [`test_hourly_forecast_treats_missing_fields_as_unavailable`](../../tests/test_time_and_missing_data.py) — `tests/test_time_and_missing_data.py::test_hourly_forecast_treats_missing_fields_as_unavailable`

### `FCS-003` — Daily grouping follows the complete Home Assistant local date

**Contract:** Samples MUST group by full calendar date in Home Assistant's configured timezone,
including DST transitions. Each daily timestamp MUST be that local midnight converted to UTC.
Partial boundary days MUST use only available samples and MUST NOT extrapolate missing hours.

**Evidence:**

- [`test_daily_grouping_crosses_calendar_boundaries`](../../tests/test_forecast_characterization.py) — `tests/test_forecast_characterization.py::test_daily_grouping_crosses_calendar_boundaries`
- [`test_hourly_forecast_uses_helsinki_dst_transition`](../../tests/test_forecast_characterization.py) — `tests/test_forecast_characterization.py::test_hourly_forecast_uses_helsinki_dst_transition`
- [`test_daily_forecast_uses_partial_local_day_without_extrapolation`](../../tests/test_forecast_characterization.py) — `tests/test_forecast_characterization.py::test_daily_forecast_uses_partial_local_day_without_extrapolation`

### `FCS-004` — Daily fields aggregate deterministically

**Contract:** Daily high/low temperature and maximum apparent temperature MUST use finite extrema;
precipitation MUST use `math.fsum` over finite one-hour amounts; wind/gust MUST use maxima with the
maximum sustained-wind sample owning bearing; humidity, pressure, dew point, and cloud MUST use
their documented arithmetic means. A field without a finite sample MUST be `None`, while explicit
zero MUST remain valid. Daily PoP MUST NOT be fabricated from hourly event probabilities.

**Evidence:**

- [`test_daily_forecast_sums_hourly_precipitation`](../../tests/test_forecast_characterization.py) — `tests/test_forecast_characterization.py::test_daily_forecast_sums_hourly_precipitation`
- [`test_daily_forecast_aggregates_mixed_conditions_wind_and_means`](../../tests/test_forecast_characterization.py) — `tests/test_forecast_characterization.py::test_daily_forecast_aggregates_mixed_conditions_wind_and_means`
- [`test_daily_forecast_distinguishes_missing_precipitation_from_zero`](../../tests/test_forecast_characterization.py) — `tests/test_forecast_characterization.py::test_daily_forecast_distinguishes_missing_precipitation_from_zero`

### `FCS-005` — Daily condition uses fixed severity precedence

**Contract:** A daily condition MUST be the highest recognized condition in this descending order:
`lightning-rainy`, `lightning`, `pouring`, `snowy-rainy`, `snowy`, `rainy`, `fog`, `cloudy`,
`partlycloudy`, `sunny`, `clear-night`. Unknown symbols MUST NOT override a recognized condition;
an entirely unknown day MUST expose no condition.

**Evidence:**

- [`test_daily_forecast_aggregates_mixed_conditions_wind_and_means`](../../tests/test_forecast_characterization.py) — `tests/test_forecast_characterization.py::test_daily_forecast_aggregates_mixed_conditions_wind_and_means`
- [`test_unknown_forecast_symbol_becomes_none`](../../tests/test_time_and_missing_data.py) — `tests/test_time_and_missing_data.py::test_unknown_forecast_symbol_becomes_none`

### `FCS-006` — Weather forecast APIs and legacy daily entity remain compatible

**Contract:** Every forecast-backed weather entity, including the retained legacy `daily_mode`
entity, MUST advertise separate hourly and daily async forecast APIs with literal granularities;
the deprecated forecast property MUST NOT be the supported path. A configured-station observation
entity MUST advertise no forecast feature. Disabling the legacy entity MUST preserve its
registry/custom identity, and re-enabling MUST restore the same record.

**Evidence:**

- [`test_forecast_methods_return_literal_granularity`](../../tests/test_forecast_characterization.py) — `tests/test_forecast_characterization.py::test_forecast_methods_return_literal_granularity`
- [`test_public_entity_and_forecast_contracts`](../../tests/test_lifecycle.py) — `tests/test_lifecycle.py::test_public_entity_and_forecast_contracts`
- [`test_legacy_daily_entity_survives_disable_and_reenable`](../../tests/test_migrations.py) — `tests/test_migrations.py::test_legacy_daily_entity_survives_disable_and_reenable`
