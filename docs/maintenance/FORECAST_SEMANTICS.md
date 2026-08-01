<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Forecast Semantics

This document defines how FMI's one-hour point forecast samples are exposed through Home
Assistant's hourly and daily weather forecast APIs.

## Source contracts

The installed `fmi-weather-client==1.0.0` model exposes timezone-aware `WeatherData` samples. Its `precipitation_amount` field maps FMI `Precipitation1h` and is documented by the client as the amount during the preceding hour. The client labels the value `mm/h`, while Home Assistant's weather entity contract requires accumulated forecast precipitation in `mm` or `in`. The integration therefore exposes each one-hour amount and its daily sum as millimetres.

FMI states that forecast data is returned only at requested time positions. A query with a three-hour or longer timestep omits intervening `Precipitation1h` samples and cannot produce a complete daily total. The coordinator must retain a one-hour source series even when a legacy option requests a coarser interval for other consumers.

Home Assistant requires separate `async_forecast_hourly` and `async_forecast_daily` methods. Forecast `datetime` values are UTC RFC 3339 strings, and all values use the entity's native units. The deprecated `forecast` property is not part of the supported contract.

## Input normalization

- Reject samples without timezone-aware timestamps.
- For a repeated timestamp, retain the last occurrence in the FMI payload so that a corrected later value is not double-counted.
- Sort the resulting unique samples chronologically before hourly exposure or daily grouping.
- Treat `None`, NaN, and infinite numeric values as missing.
- Do not invent precipitation probability or other values absent from the installed client model.

## Hourly forecast

Each normalized FMI sample produces one hourly forecast item:

- `datetime`: sample time converted to UTC RFC 3339;
- condition: the existing FMI `WeatherSymbol3` to Home Assistant mapping, or `None` for an unmapped symbol;
- temperature, precipitation, wind speed, wind gust, wind bearing, pressure, humidity, cloud coverage, and dew point: the finite value from that sample;
- precipitation: the source hour's `Precipitation1h` amount in millimetres.

Hourly output never reports a daily low temperature and does not convert missing values to zero.

## Daily grouping and timestamp

Samples are grouped by their full calendar date in Home Assistant's configured timezone, including DST transitions. A daily item's timestamp is local midnight for that date converted to UTC RFC 3339. This satisfies Home Assistant's UTC output contract without losing the local-day boundary.

Partial first and last days are included using only the available samples. The integration does not extrapolate missing hours or label a partial total as a complete 24-hour measurement.

## Daily aggregation

For each local day:

| Field | Rule |
|---|---|
| high temperature | Maximum finite hourly temperature |
| low temperature | Minimum finite hourly temperature |
| precipitation | Sum of finite one-hour amounts with `math.fsum`; `None` when no valid amount exists; explicit zeros remain valid |
| wind speed | Maximum finite sustained wind speed |
| wind gust | Maximum finite gust |
| wind bearing | Bearing from the sample selected for maximum sustained wind; earliest timestamp wins a speed tie; `None` without valid sustained wind |
| humidity | Arithmetic mean of finite hourly humidity values |
| pressure | Arithmetic mean of finite hourly pressure values |
| dew point | Arithmetic mean of finite hourly dew-point values |
| cloud coverage | Rounded arithmetic mean of finite hourly percentages |

A field with no valid samples is `None` rather than a fabricated zero.

## Daily condition

The daily condition is not the first sample. It is the highest-severity recognized condition present during that local day, using this deterministic order from highest to lowest:

1. `lightning-rainy`
2. `lightning`
3. `pouring`
4. `snowy-rainy`
5. `snowy`
6. `rainy`
7. `fog`
8. `cloudy`
9. `partlycloudy`
10. `sunny`
11. `clear-night`

Multiple FMI symbols that map to the same Home Assistant condition are equivalent. Unknown symbols do not override a recognized condition; if every symbol is unknown, the daily condition is `None`. This policy favors safety-relevant precipitation and thunder conditions over a clear first hour without inventing probability data.

## Entity compatibility

Every retained weather entity advertises and implements both hourly and daily forecast methods with
their literal granularities. The old `daily_mode` option still creates its legacy extra entity,
and its methods are no longer mode-dependent. The migration contract preserves that entity:
disabling the option leaves its registry/custom ID intact and unavailable, and re-enabling it
restores the same record. See `MIGRATIONS.md`.

## References

- [Home Assistant weather entity contract](https://developers.home-assistant.io/docs/core/entity/weather/), checked 2026-07-31.
- [Home Assistant forecast-type migration notice](https://developers.home-assistant.io/blog/2023/08/07/weather_entity_forecast_types/), checked 2026-07-31.
- [FMI WFS examples and timestep guidance](https://en.ilmatieteenlaitos.fi/open-data-manual-wfs-examples-and-guidelines), checked 2026-07-31.
- [`fmi-weather-client` 1.0.0 source](https://codeberg.org/saaste/fmi-weather-client/src/tag/1.0.0/fmi_weather_client/models.py), checked against the installed package 2026-07-31.
