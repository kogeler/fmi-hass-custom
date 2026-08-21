<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# FMI Custom Integration User Guide

This guide applies to the
[latest published GitHub Release](https://github.com/kogeler/fmi-hass-custom/releases/latest).
Check that page before installation or upgrade for the current version, release notes, and source
archives. The minimum Home Assistant version is declared in `hacs.json` within that release.
Current stable and prerelease compatibility checks detect upcoming changes, but do not promise
support for every future release. The integration needs internet access to FMI. HACS is recommended
but not required. The supported product geography is Finland; optional observation and sea-level
datasets can cover only part of that area. A place-search result outside Finland does not establish
support for that location.

## Install With HACS

1. Install and configure [HACS](https://www.hacs.xyz/docs/use/) for your Home Assistant system.
2. Open HACS, use the top-right menu, and select **Custom repositories**.
3. Enter `https://github.com/kogeler/fmi-hass-custom`, select **Integration**, and add it.
4. Open the FMI repository in HACS, select **Download**, and choose the newest published version.
   Confirm it against the [latest GitHub Release](https://github.com/kogeler/fmi-hass-custom/releases/latest).
5. Restart Home Assistant.
6. Open **Settings > Devices & services > Add integration**, search for **Finnish Meteorological
   Institute**, and choose a location method:
   - **Choose on map** starts at Home Assistant's configured Home location. Accept the marker or
     move it to another forecast point.
   - **Search by place name** sends a city or place name to FMI, then shows FMI's result on the map.
     Confirm that point or adjust the marker before saving.
7. Enter the display name requested on the selected path. FMI validates the final map point before
   Home Assistant creates the entry.

Repeat the last step to configure another location. The same coordinates cannot be used by two
entries.

### Switch From Another FMI Repository

Create and download a Home Assistant backup before changing the repository source. Do not delete
the FMI entry under **Settings > Devices & services**: that entry owns the existing configuration,
devices, and entity-registry records.

If the previous FMI source was added to HACS as a custom repository:

1. Open HACS, use the top-right menu, and select **Custom repositories**.
2. Remove the previous FMI repository URL from that list.
3. Add `https://github.com/kogeler/fmi-hass-custom` with type **Integration**.
4. Open the FMI repository in HACS and select **Download** or **Redownload** for the newest
   published release.
5. Restart Home Assistant.

This changes the repository from which HACS installs `custom_components/fmi/`; it does not create a
new Home Assistant integration. The fork retains the `fmi` domain and migrates existing config and
registry state in place, including customized entity IDs. If HACS removes the old downloaded files
during the switch, complete the fork download before restarting Home Assistant.

## Install Manually

1. Open the [latest GitHub Release](https://github.com/kogeler/fmi-hass-custom/releases/latest)
   and download its **Source code** archive.
2. Stop Home Assistant or make sure no integration files are being updated.
3. Copy the archive's complete `custom_components/fmi/` directory to
   `<Home Assistant config>/custom_components/fmi/`. The resulting path must contain
   `manifest.json` directly inside the `fmi` directory.
4. Restart Home Assistant.
5. Add the integration from **Settings > Devices & services** as described above.

Do not copy the whole repository into `custom_components/fmi/`, and do not install packages from
any root `requirements*.txt` file into Home Assistant. Those files are generated maintainer locks;
Home Assistant installs the exact runtime requirements declared by the integration manifest.

## Upgrade

Create and download a Home Assistant backup before an upgrade.

- **HACS:** install the offered FMI update from **Settings > Updates** or use **Redownload** on the
  HACS repository, then restart Home Assistant.
- **Manual:** replace the complete `custom_components/fmi/` directory with the directory from the
  new release archive, then restart Home Assistant. Do not remove the integration entry first.

Upgrading from the legacy integration line migrates config and registry identity in place. Existing
customized IDs remain usable; the exact compatibility guarantees and conservative rename boundary
are maintained in the [migration contract](contracts/MIGRATIONS.md).

The lightning direction release intentionally changes the existing lightning sensor value and
attributes in place. An old address/native-state comparison or template reading `location` must be
updated to use `direction`, `bearing`, or `distance`. The entity-registry record, unique ID,
customized entity ID, device, config entry, options, and Recorder history remain intact.

The useful forecast-metrics release keeps the existing **Best time of day** entity and its IDs,
but improves its selection in place. Temperature limits now mean acceptable **feels-like**
temperature, the current time is no longer a fallback, and a healthy day with no matching hour has
the translated `no_suitable_time` state. Review automations that assumed this sensor always
contained an `HH:MM` value or selected the warmest hour.

## Configure

Initial setup accepts a display name and either a map point or an FMI place search followed by map
confirmation. FMI resolves the final location name used for new device and entity names. Open
**Settings > Devices & services > Finnish Meteorological
Institute**, select an entry, and choose **Configure** to change these options:

- forecast days (`0` disables future samples, otherwise up to 10 days);
- forecast interval used by the **Best time of day** calculation;
- feels-like temperature, humidity, wind, and precipitation limits used by that calculation;
- legacy daily weather entity, which is optional because the main weather entity already supplies
  both hourly and daily forecasts;
- lightning sensor, search radius, and inclusive maximum age from 1 to 1440 minutes;
- numeric FMI observation station ID (`0` disables the station observation entity).

The sea-level sensor does not have an enable switch. It becomes available only when FMI provides
a valid forecast for the configured coordinates.

### Move A Location

Changing the Home zone does not update an FMI entry. From the integration entry menu select
**Reconfigure**, then choose either the map or place-name search. The map starts at the entry's
current point, not the current Home location. A search always shows FMI's result on the map before
anything is changed; confirm it or move the marker. FMI validates the final point before Home
Assistant saves and reloads only that entry. Existing entity IDs, including customized IDs used by
dashboards and automations, remain unchanged.

## Find Your Entities

Open the integration entry and its device/entity list in **Settings > Devices & services**. A new
Helsinki entry usually has IDs such as `weather.helsinki` and
`sensor.helsinki_temperature`, but migration history, duplicate names, and user customization can
produce different IDs. Always use the IDs shown in your own entity registry.

The main location device normally contains a weather entity and sensors for place, condition,
temperature, feels like, dew point, atmospheric pressure, wind speed/direction/gust, humidity,
total/low/medium/high cloud cover, rain, precipitation probability, thunderstorm probability,
forecast time, best time of day, and sea level. Enabling lightning adds a lightning sensor. A
configured station creates a separate observation device and weather entity; it does not duplicate
the main forecast-backed metric sensors. Enabling legacy daily mode adds another weather entity,
but it is not needed to request daily forecasts from the main entity.

## Useful Weather Metrics

The dedicated numeric sensors can be graphed, recorded, and used directly in automations:

| Sensor | Native unit | Meaning |
|---|---:|---|
| Feels like | °C | Apparent temperature calculated by `fmi-weather-client` from FMI temperature, humidity, and wind data. Home Assistant converts it to the configured unit system. |
| Dew point | °C | Temperature at which air with the forecast moisture content would reach saturation. A value close to air temperature indicates moist air and a greater condensation/fog potential. |
| Atmospheric pressure | hPa | FMI mean-sea-level pressure, suitable for comparing weather-system pressure between locations; it is not unadjusted station pressure. |
| Low cloud cover | % | Forecast fraction of the sky covered by low cloud. |
| Medium cloud cover | % | Forecast fraction covered by middle cloud. |
| High cloud cover | % | Forecast fraction covered by high cloud. |
| Rain | mm/h | FMI one-hour precipitation value exposed as a precipitation-intensity sensor. Weather entities expose the same one-hour forecast quantity as accumulated `mm`, as required by Home Assistant's weather schema. |
| Precipitation probability | % | FMI `PoP`: probability of at least 0.1 mm during the preceding forecast hour. It is a chance, not a precipitation amount. |
| Thunderstorm probability | % | FMI forecast probability of thunder at the point/hour. It does not mean lightning has been observed. |

Cloud layers can overlap vertically, so low, medium, and high percentages must not be added. The
authoritative value/range/availability rules are `SNS-001` and `SNS-002` in the
[sensor contract](contracts/SENSORS.md).

The main and station weather entities expose only fields supported by their selected source.
Hourly/daily field and aggregation rules, including why daily PoP is absent, are maintained in the
[forecast-semantics contract](contracts/FORECAST_SEMANTICS.md).

Thunderstorm probability and the optional lightning sensor answer different questions. The
probability is a forecast for an hour; the lightning sensor reports recent FMI-observed strike
groups within the configured radius and age.

## Best Time Of Day

**Best time of day** chooses a remaining current-day forecast hour under your configured
feels-like temperature, humidity, wind, and precipitation limits. It prefers lower thunder/rain
risk and feels-like comfort without inventing a hidden weighted score. Only the fixed FMI weather
symbols listed by the contract are eligible; thunderstorm and other excluded conditions are
rejected before ranking. The exact candidate fields, hard gates, symbol list, tie-break order,
state/attribute schema, `no_suitable_time` classification, and unavailable behavior are maintained
in `TIM-003` through `TIM-007` of the
[time and missing-data contract](contracts/TIME_AND_MISSING_DATA.md).

This is a transparent convenience ordering under your configured limits, not a medical, heat-,
lightning-, or activity-safety score. It does not model direct sun, radiant temperature, clothing,
health, acclimatization, or activity intensity. Follow official warnings and appropriate safety
guidance instead of using this sensor as an alert system.

## Lightning State And Automations

The optional lightning sensor describes recent FMI strike groups relative to the coordinates
stored by its own integration entry. Home Assistant's global Home coordinates are only the initial
map position during setup; they are not substituted for the entry's point. The configured radius
is an inclusive circle, and the maximum age controls both the FMI query window and local freshness
filter.

The current state has three user-facing meanings:

- A successful response with no qualifying strike is available with backend state `no_strikes`.
  The frontend displays **No lightning strikes** in English or **Ei salamaniskuja** in Finnish.
- A qualifying group has a state such as `42.3 km · SE`. `0.0 km · HERE` means the strike point and
  configured point coincide, so no bearing exists.
- A transport, timeout, unsafe payload, parser, or unusable response is `unavailable`. Old strike
  state and dynamic attributes are cleared; the next valid refresh recovers without a reload.

The exact state/attribute schema, direction sectors, empty/failure behavior, and coordinate boundary
are maintained in `SNS-006` of the [sensor contract](contracts/SENSORS.md) and `OPT-003` through
`OPT-006` of the [optional-source contract](contracts/OPTIONAL_SOURCES.md). FMI remains the only
lightning network provider.

Use attributes for automations instead of parsing the display state. For example:

```yaml
direction: "{{ state_attr('sensor.helsinki_lightning_strikes', 'direction') }}"
bearing: "{{ state_attr('sensor.helsinki_lightning_strikes', 'bearing') }}"
distance_km: "{{ state_attr('sensor.helsinki_lightning_strikes', 'distance') }}"
empty: "{{ is_state('sensor.helsinki_lightning_strikes', 'no_strikes') }}"
```

Direction is only the initial bearing from the configured point to an observed strike group. It
does not identify or track a storm cell, show whether a storm is approaching, estimate arrival or
closest approach, or provide safety guidance.

## Dashboard Examples

Replace every example entity ID with the exact ID from your entity registry. The examples use only
standard Home Assistant cards.

### Current Conditions And Daily Forecast

```yaml
type: weather-forecast
entity: weather.helsinki
name: Helsinki
show_current: true
show_forecast: true
forecast_type: daily
```

### Hourly Forecast

```yaml
type: weather-forecast
entity: weather.helsinki
name: Helsinki hourly
show_current: false
show_forecast: true
forecast_type: hourly
```

### Current Sensors

```yaml
type: entities
title: Helsinki details
show_header_toggle: false
entities:
  - entity: sensor.helsinki_temperature
  - entity: sensor.helsinki_feels_like
  - entity: sensor.helsinki_dew_point
  - entity: sensor.helsinki_atmospheric_pressure
  - entity: sensor.helsinki_humidity
  - entity: sensor.helsinki_wind_speed
  - entity: sensor.helsinki_wind_gust
  - entity: sensor.helsinki_cloud_coverage
  - entity: sensor.helsinki_low_cloud_cover
  - entity: sensor.helsinki_medium_cloud_cover
  - entity: sensor.helsinki_high_cloud_cover
  - entity: sensor.helsinki_rain
  - entity: sensor.helsinki_precipitation_probability
  - entity: sensor.helsinki_thunderstorm_probability
  - entity: sensor.helsinki_best_time_of_day
```

### Station Observation

Use the station's weather entity. It supplies current observations and intentionally has no
forecast.

```yaml
type: weather-forecast
entity: weather.helsinki_kaisaniemi_observation
name: Kaisaniemi observation
show_current: true
show_forecast: false
```

### Optional Lightning And Sea Level

```yaml
type: entities
title: FMI optional sources
show_header_toggle: false
entities:
  - entity: sensor.helsinki_lightning_strikes
  - entity: sensor.helsinki_sea_level
```

## Troubleshoot

- **The integration is not listed:** verify
  `<Home Assistant config>/custom_components/fmi/manifest.json` exists and restart Home Assistant.
  Review Home Assistant logs for a manifest or import error.
- **A place search finds nothing:** try a more specific city or place name. No entry is created or
  changed until a result is confirmed and the final point passes validation.
- **The selected point is already configured:** choose another point. Two FMI entries cannot own
  the same final coordinates.
- **Setup or reconfiguration cannot connect:** verify internet access and check FMI Open Data
  availability. Retry the form after a temporary service failure; failed and canceled flows leave
  existing entries unchanged.
- **The map point produces an unexpected error:** choose another point inside normal WGS84 bounds
  and FMI forecast coverage. Non-finite, out-of-range, or malformed locations are rejected before
  they can be saved.
- **Forecast is unavailable but observations work:** sources intentionally fail independently.
  Wait for the next refresh; valid data restores availability automatically without a reload.
- **Station observation is missing:** confirm that the configured value is a valid numeric FMI
  station ID and that the station currently publishes observations.
- **Lightning is missing:** enable it in **Configure**. A successful response with no qualifying
  strikes remains available as `no_strikes`; stale, malformed, or failed data makes only that
  sensor unavailable. Wait for the next refresh to recover automatically.
- **Sea level is unavailable:** the configured location may be outside FMI sea-level forecast
  coverage, or the optional response may be empty or unavailable.
- **Best time says “No suitable time today”:** FMI forecast data is healthy, but there is no
  complete remaining current-day hour that passes your configured limits. Widen the limits if
  appropriate. `unavailable` instead means the remaining forecast data cannot support a result.
- **A dashboard example reports an unknown entity:** replace the sample ID with the entity ID shown
  in your registry. Reconfigured and migrated entries deliberately retain their established IDs.

When reporting a problem, attach sanitized Home Assistant diagnostics and relevant integration log
lines. Diagnostics redact configured coordinates and legacy coordinate-derived identity. Do not
publish precise home coordinates or raw external responses.

## Remove

1. Open **Settings > Devices & services > Finnish Meteorological Institute**.
2. Open the entry menu and select **Delete**. This removes its devices and entities from Home
   Assistant.
3. Remove the repository from HACS, or delete `custom_components/fmi/` for a manual installation.
4. Restart Home Assistant.

## External Services And Privacy

FMI receives place-search text when that optional path is used and receives the final coordinates
needed for validation, weather, lightning-area, and sea-level requests. Search text is transient:
it is not stored in the config entry, logs, or diagnostics. FMI lightning strike coordinates are
processed transiently in memory for local distance/bearing calculation. They are not sent to a
second provider and are not exposed in state, attributes, logs, or diagnostics. See the
[security and privacy contract](contracts/COMPATIBILITY_SECURITY.md).

Documentation references verified 2026-08-20:

- [HACS custom repositories](https://www.hacs.xyz/docs/faq/custom_repositories/)
- [HACS repository download and update behavior](https://www.hacs.xyz/docs/use/repositories/dashboard/)
- [Home Assistant weather forecast card](https://www.home-assistant.io/dashboards/weather-forecast/)
- [Home Assistant entities card](https://www.home-assistant.io/dashboards/entities/)
- [Home Assistant integration removal](https://www.home-assistant.io/common-tasks/general/#removing-an-integration-instance)
