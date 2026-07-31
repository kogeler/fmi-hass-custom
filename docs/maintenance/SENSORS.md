# Sensor And Gust Contract

This document defines the S06 behavior for FMI sensor entities, issue #111 wind gusts, and issue #112 location grouping. It applies to Home Assistant 2026.7.4 and `fmi-weather-client==1.0.0`.

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

## Entity And Device Naming

Every sensor now uses `SensorEntity`, `has_entity_name = True`, translated entity descriptions, and a location device. The device identifier remains `(fmi, coordinator.unique_id)`, derived from coordinates rather than display text. The device name is the place resolved by FMI, with the configured name as a setup fallback.

For a fresh English installation at Helsinki, the temperature entity is therefore:

- device: `Helsinki`;
- entity name: `Temperature`;
- friendly name: `Helsinki Temperature`;
- entity ID: `sensor.helsinki_temperature`.

Names with non-ASCII characters and punctuation remain intact as device display names; Home Assistant performs its normal slug conversion for generated entity IDs. Two coordinate entries have different device identifiers and sensor unique IDs even when their sensor types or place labels match.

Existing unique IDs are unchanged. They retain the v0.6.2 coordinate, configured-name, and English sensor suffix shape so registry customizations remain attached.

## Conservative Legacy ID Migration

Before adding sensors, S06 looks up each unchanged unique ID in the entity registry. It renames an entry only when its entity ID is exactly the known v0.6.2 generated default such as `sensor.temperature`.

- A user-customized ID is preserved.
- An occupied location-aware target is not overwritten.
- The registry entry and unique ID are updated in place; no entity is deleted or recreated.
- Ambiguous suffixed defaults such as `sensor.temperature_2` are not guessed to be integration-generated. S11 owns complete multi-entry migration evidence and any safe extension.

## Sensor Metadata

| Sensor | Native contract |
|---|---|
| temperature | temperature, °C, measurement |
| wind speed / gust | wind speed, m/s native, measurement; Home Assistant may convert to the configured system unit |
| humidity | humidity, %, measurement |
| rain | precipitation intensity, mm/h, measurement |
| cloud coverage | %, measurement |
| sea level | distance, cm, measurement |
| place, condition, compass direction, forecast time, best time, lightning | string values without an incompatible numeric device or state class |

Static attribution remains the entity attribution rather than being duplicated in extra state attributes. Dynamic best-condition, lightning, and sea-level details remain extra attributes.

## References

- [Issue #111](https://github.com/anand-p-r/fmi-hass-custom/issues/111), including maintainer query evidence, checked 2026-07-31.
- [Issue #112](https://github.com/anand-p-r/fmi-hass-custom/issues/112), checked 2026-07-31.
- [FMI current producer parameter metadata](https://opendata.fmi.fi/info?what=qengine), checked 2026-07-31.
- [FMI WFS examples and parameter guidance](https://en.ilmatieteenlaitos.fi/open-data-manual-wfs-examples-and-guidelines), checked 2026-07-31.
- [Home Assistant entity naming](https://developers.home-assistant.io/docs/core/entity/), checked 2026-07-31.
- [Home Assistant sensor entity contract](https://developers.home-assistant.io/docs/core/entity/sensor/), checked 2026-07-31.
- [Home Assistant entity registry](https://developers.home-assistant.io/docs/entity_registry_index/), checked 2026-07-31.
