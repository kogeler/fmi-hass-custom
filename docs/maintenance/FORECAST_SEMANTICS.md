<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Forecast-Semantics Maintenance

Normative hourly/daily normalization, aggregation, condition, timestamp, and API requirements are
owned exclusively by [the forecast-semantics contract](../contracts/FORECAST_SEMANTICS.md).
Missing-value and Best-time rules are in
[the time and missing-data contract](../contracts/TIME_AND_MISSING_DATA.md).

## Source Rationale

FMI `Precipitation1h` is a preceding-hour amount. The selected client labels its model value
`mm/h`, while Home Assistant's forecast schema represents accumulated precipitation; the contract
and tests therefore own the exact public unit/aggregation behavior. Likewise, hourly event
probabilities have no valid daily combination without a dependence model, so any future daily PoP
feature requires new upstream information and a contract change rather than an arbitrary formula.

## Change Checklist

1. Identify the affected `FCS-*` assertion and update its tests with the same change.
2. Cover full local dates, partial boundary days, duplicate timestamps, month/year/leap boundaries,
   and both DST transitions when touching grouping or time conversion.
3. Use independent fixtures for missing versus explicit zero and for mixed conditions/wind ties.
4. Do not infer an aggregation for a field whose source semantics do not support it.
5. Run `make test-full`, `make type-check`, and `make live` when FMI/HA public forecast exposure
   changes.

## References

- [Home Assistant weather entity contract](https://developers.home-assistant.io/docs/core/entity/weather/)
- [Home Assistant forecast-type migration notice](https://developers.home-assistant.io/blog/2023/08/07/weather_entity_forecast_types/)
- [FMI WFS examples and timestep guidance](https://en.ilmatieteenlaitos.fi/open-data-manual-wfs-examples-and-guidelines)
- [`fmi-weather-client` source](https://codeberg.org/saaste/fmi-weather-client/)
