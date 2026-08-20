<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Sensor And Forecast Supplement Contract

This document defines the current FMI sensor, wind-gust, entity-naming, and location-grouping
contracts. It applies to Home Assistant 2026.8.1 and `fmi-weather-client==1.0.0`.

Last verified against current code: 2026-08-20.

## Gust Sources

The selected client still requests `WindGust` from `fmi::forecast::edited::weather::scandinavia::point::multipointcoverage`. FMI returns that field as NaN for this forecast producer, which is the reported cause of the unavailable wind-gust sensor. Current FMI producer metadata lists `HourlyMaximumGust` as the available forecast field. Station observations continue to provide `WindGust` with three-second gust measurements.

The integration uses these contracts:

- Forecast-backed current weather and hourly forecasts request `WindGust` and `HourlyMaximumGust` together in the client's existing WFS request. No second request is added.
- The adapter parses `HourlyMaximumGust` by timestamp and exposes it through the client's existing `WeatherData.wind_gust` model field. `WeatherData.wind_max` retains the extracted hourly value as a compatibility fallback.
- For forecast-backed data, finite `HourlyMaximumGust` takes precedence because it is the field published by the producer. A finite native `WindGust` is retained only when the hourly field is missing.
- Observation-by-place and observation-by-station calls remain upstream client calls and retain observation `WindGust` semantics.
- Sensor extraction accepts finite values, including `0.0`; it rejects `None`, NaN, and infinities. If `wind_gust` is unavailable, it checks `wind_max`. Ordinary wind speed is never substituted.
- A sensor with no valid value is unavailable, not zero or stale. Coordinator failure and recovery update availability without recreating the entity.

The adapter deliberately isolates the stable client's private parameter and response boundary in `custom_components/fmi/fmi_client.py`. Offline tests pin the selected client's mismatch, the added parameter, single-request behavior, XML timestamp mapping, finite precedence, and the original 10-minute current/60-minute hourly forecast timesteps.

## Forecast Probability Source

The same coordinate request also adds `PoP` and `ProbabilityThunderstorm` exactly once. The adapter
parses gust and both probabilities from one bounded safe XML document by response field name, so
column order is not a contract. Rows align to aware UTC timestamps; the last duplicate timestamp
wins consistently with forecast normalization.

`ForecastProbabilities`, `CurrentWeatherResult`, and `ForecastResult` keep these integration-owned
values separate from the fixed upstream `WeatherData` NamedTuple. Future probabilities cross the
adapter boundary in a read-only timestamp mapping. The coordinator owns current and future
supplements in one typed runtime state and replaces or clears them with their current/forecast
owner. Missing, malformed, non-finite, below-zero, or above-100 probabilities remain unavailable;
valid `0.0` and `100.0` are retained. This adds no request or dependency.

## Entity And Device Naming

Every sensor uses `SensorEntity`, `has_entity_name = True`, translated entity descriptions, and a
location device. The device identifier is `(fmi, coordinator.unique_id)`, where the coordinator ID
comes from immutable `entity_identity`, never mutable display text. Fresh entries use a random
coordinate-independent identity; migrated entries retain their original coordinate-derived value.
The device name is the place resolved by FMI, with the configured name as a setup fallback.

For a fresh English installation at Helsinki, the temperature entity is therefore:

- device: `Helsinki`;
- entity name: `Temperature`;
- friendly name: `Helsinki Temperature`;
- entity ID: `sensor.helsinki_temperature`.

Names with non-ASCII characters and punctuation remain intact as device display names; Home
Assistant performs its normal slug conversion for generated entity IDs. Two entries have different
device identifiers and sensor unique IDs even when their sensor types or resolved place labels
match.

Existing unique IDs are unchanged. They retain the v0.6.2 coordinate, configured-name, and English sensor suffix shape so registry customizations remain attached.

## Conservative Legacy ID Migration

Before adding sensors, setup looks up each unchanged unique ID in the entity registry. It renames
an entry only when its entity ID is exactly the known v0.6.2 generated default such as
`sensor.temperature`.

- A user-customized ID is preserved.
- An occupied location-aware target is not overwritten.
- The registry entry and unique ID are updated in place; no entity is deleted or recreated.
- Ambiguous suffixed defaults such as `sensor.temperature_2` are preserved because current registry
  data cannot distinguish an automatically allocated suffix from the same user-selected ID. The
  two-entry acceptance fixture proves that these entities retain their internal/unique IDs and
  acquire the correct location device without guessing. See `MIGRATIONS.md`.

## Sensor Metadata

| Sensor | Native contract |
|---|---|
| temperature | temperature, °C, measurement |
| feels like / dew point | temperature, °C, measurement |
| atmospheric pressure | atmospheric pressure, hPa, measurement |
| wind speed / gust | wind speed, m/s native, measurement; Home Assistant may convert to the configured system unit |
| humidity | humidity, %, measurement |
| rain | precipitation intensity, mm/h, measurement |
| total / low / medium / high cloud cover | independent %, measurement; layers may overlap and are never added |
| precipitation / thunderstorm probability | %, measurement; no precipitation-intensity device class |
| sea level | distance, cm, measurement |
| place, condition, compass direction, forecast time, best time, lightning | string values without an incompatible numeric device or state class |

The main location device exposes the forecast-backed current values as dedicated `Feels like`,
`Dew point`, `Atmospheric pressure`, `Low cloud cover`, `Medium cloud cover`, `High cloud cover`,
`Precipitation probability`, and `Thunderstorm probability` sensors. They follow the same selected
source timestamp and configured legacy interval as the existing weather-value sensors. Client
model fields are accepted only when finite; cloud layers and probabilities additionally require
0–100 inclusive. Missing or invalid data makes only that sensor unavailable, while explicit zero
remains a valid state and later coordinator data recovers the existing entity.

Every description has a stable legacy-style unique-ID suffix and belongs to the existing main
location device. These sensors are not duplicated on the optional station-observation device.
Temperature and pressure declare native FMI units and therefore use Home Assistant's configured
unit conversion for state presentation.

Static attribution remains the entity attribution rather than being duplicated in extra state attributes. Dynamic best-condition, lightning, and sea-level details remain extra attributes.

`Best time of day` retains its legacy-style unique ID, device, customized entity ID, and selected
`HH:MM` state. A selected result preserves `location`, aware `time`, air `temperature`,
`relative_humidity`, `precipitation`, and `wind_speed`, and adds `apparent_temperature`,
`precipitation_probability`, and `thunderstorm_probability`. The valid `no_suitable_time` token is
frontend-translated and has no dynamic selection attributes. Unusable forecast data makes the
sensor unavailable and also clears those attributes. The deterministic time/candidate contract is
defined in `TIME_AND_MISSING_DATA.md`.

## Lightning State And Attributes

A successful empty FMI result stores `no_strikes`; Home Assistant can translate that finite state
for presentation. A qualifying group stores `{distance:.1f} km · {DIRECTION}`, for example
`42.3 km · SE`. A coincident group stores `0.0 km · HERE`. The value remains a textual sensor with
no device/state class or unit conversion.

The primary group and every nested `OBSERVATIONS` row expose `time`, numeric kilometer `distance`,
`direction`, `bearing`, `strikes`, `peak_current`, `cloud_cover`, and `ellipse_major`. Bearing is
`None` only for `direction=here`. No row exposes address, `location`, latitude, longitude, or raw
coordinates. Static attribution is FMI only. A failed source is unavailable and clears all dynamic
attributes; successful empty data is available and has no dynamic strike attributes.

## References

- [FMI current producer parameter metadata](https://opendata.fmi.fi/info?what=qengine), checked 2026-07-31.
- [FMI WFS examples and parameter guidance](https://en.ilmatieteenlaitos.fi/open-data-manual-wfs-examples-and-guidelines), checked 2026-07-31.
- [Home Assistant entity naming](https://developers.home-assistant.io/docs/core/entity/), checked 2026-07-31.
- [Home Assistant sensor entity contract](https://developers.home-assistant.io/docs/core/entity/sensor/), checked 2026-07-31.
- [Home Assistant entity registry](https://developers.home-assistant.io/docs/entity_registry_index/), checked 2026-07-31.
