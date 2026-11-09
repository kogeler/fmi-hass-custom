<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# FMI Custom Integration User Guide

This guide applies to the
[latest published GitHub Release](https://github.com/kogeler/fmi-hass-custom/releases/latest).
Check that page before installation or upgrade for the current version, release notes, and source
archives. The minimum Home Assistant version is declared in `hacs.json` within that release.
Current stable and prerelease compatibility checks detect upcoming changes, but do not promise
support for every future release. The integration needs internet access to FMI. The Home Assistant
Marketplace or HACS, whichever your Home Assistant release provides, is recommended but not
required. The supported product geography is Finland; optional observation and sea-level
datasets can cover only part of that area. A place-search result outside Finland does not establish
support for that location.

## Install With The Marketplace Or HACS

The integration is listed in the default catalog as **FMI Weather**. Starting with Home Assistant
2026.11, HACS is built into Home Assistant as the **Marketplace** under **Settings > Marketplace**,
and the HACS custom integration can no longer be installed. Older Home Assistant releases keep using
HACS. Both show the same catalog and install the same published releases. This only changes the
installation tool; the minimum supported Home Assistant version is still the one declared in
`hacs.json`.

1. Open the **FMI Weather** repository:
   - Open
     [this My Home Assistant link](https://my.home-assistant.io/redirect/hacs_repository/?owner=kogeler&repository=fmi-hass-custom&category=integration).
     It opens the repository in the Marketplace on Home Assistant 2026.11 and newer, and in HACS on
     older releases.
   - Alternatively, open **Settings > Marketplace**, or HACS on older releases, and search for
     **FMI Weather**.
2. Select **Download** and choose the newest published version. Confirm it against the
   [latest GitHub Release](https://github.com/kogeler/fmi-hass-custom/releases/latest).
3. Restart Home Assistant when asked. HACS always requires a restart; the Marketplace creates a
   repair with a restart button when one is needed.
4. Open **Settings > Devices & services > Add integration**, search for **Finnish Meteorological
   Institute**, and choose a location method:
   - **Choose on map** starts at Home Assistant's configured Home location. Accept the marker or
     move it to another forecast point.
   - **Search by place name** sends a city or place name to FMI, then shows FMI's result on the map.
     Confirm that point or adjust the marker before saving.
5. Enter the display name requested on the selected path. FMI validates the final map point before
   Home Assistant creates the entry.

Repeat the last step to configure another location. The same coordinates cannot be used by two
entries.

### Switch From Another FMI Repository

Create and download a Home Assistant backup before changing the repository source. Do not delete
the FMI entry under **Settings > Devices & services**: that entry owns the existing configuration,
devices, and entity-registry records.

If this repository was added as a custom repository before it joined the default catalog, nothing
needs to change: it is the same repository, and updates keep arriving.

If the previous FMI source was another repository added to HACS or the Marketplace as a custom
repository:

1. Remove that custom repository from HACS (top-right menu, **Custom repositories**) or from
   **Settings > Marketplace**. The Marketplace refuses a second repository that installs the same
   `fmi` domain.
2. Open **FMI Weather** from the catalog as described above and select **Download** or
   **Redownload** for the newest published release.
3. Restart Home Assistant.

This changes the repository from which HACS or the Marketplace installs `custom_components/fmi/`;
it does not create a new Home Assistant integration. The fork retains the `fmi` domain and
migrates existing config and registry state in place, including customized entity IDs. If HACS
removes the old downloaded files during the switch, complete the fork download before restarting
Home Assistant.

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

- **Marketplace or HACS:** install the offered FMI update from **Settings > Updates**, or use
  **Redownload** on the repository, then restart Home Assistant.
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
- numeric FMI observation station ID (`0` disables the station observation entity);
- official weather warnings and their original text language (Finnish, Swedish, English, or
  automatic selection from Home Assistant's configured language, with English fallback).

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

## Official Weather Warnings

Enable **Official weather warnings** in the entry's options. Warnings use the location selected
on the map, independently of the observation station. The location device gains a warning count
sensor, a warning-level sensor, and a binary sensor showing whether any warning is active.
They use the same device and keep their identity when the location or language changes.

Choose Finnish, Swedish, or English for the original FMI messages. Automatic selection uses the
language configured for Home Assistant, falling back to English for other languages. The message's
`language` field identifies the actual original language if FMI does not include the requested one.
Entity labels follow Home Assistant's interface translation; message text has one language per
entry. No translation service receives the data.

The count includes warnings active now. Its `warnings` attribute contains those messages and
`upcoming_warnings` contains published future warnings; `upcoming_count` counts the latter.
Messages include official headlines, descriptions, severity, area names, language, and UTC
publication/start/end times. Optional instructions or typical impacts appear only when FMI supplies
them. Warning polygons are checked locally and are not copied into entity attributes.

Level values are `none`, `green`, `yellow`, `orange`, `red`, and `unclassified`. The interface
translates these labels. FMI's current warning profile does not use green; the value remains for
the official Minor severity. An unknown severity remains visible as unclassified. The binary sensor
is off when there is no matching active message; this does not mean the weather is safe. A future
warning does not turn it on before its start time.
When known and unclassified warnings coexist, the level is unclassified; the individual warning
list still includes every known color, ordered red through green after unclassified messages.

Warnings refresh independently every five minutes and change at their start/end times locally.
Unavailable means warning data could not be checked; it is different from an available count of
zero. A brief network problem, such as a timeout, a dropped connection, or an FMI server error,
keeps the last accepted messages and their start/end transitions until the 15-minute freshness
deadline, so a single slow download does not interrupt dashboards or automations. Other source
failures, such as an invalid publication, clear previous message attributes immediately. A later
successful refresh restores them without recreating entities. Forecast/current-weather failures do
not disable an independently working warning source. Large message lists are omitted from Recorder
attributes while remaining accessible in current state for cards and templates. An unchanged
publication does not change the entity state, so repeated retrieval adds no history rows and does
not trigger state automations.
The 15-minute freshness deadline measures successful retrieval. Repeated successful delivery of an
unchanged publication refreshes it; it cannot detect a frozen provider publication by itself.
If FMI briefly serves an older publication, the newer data stays until its freshness deadline
instead of being replaced by older messages. Sanitized diagnostics include a reason code for source
failures and the time of the last accepted retrieval. Each refresh downloads the selected national
feed, which can be several megabytes during widespread warnings. A download may take up to 30
seconds, with up to 10 seconds to connect or between received data. Publications larger than
16 MiB and overly complex or invalid polygons that could cover the configured location make this
source unavailable rather than silently omitting messages. A malformed message for an area that
cannot reach the location is ignored.

Coverage is limited to the supported FMI CAP weather-warning feed, not every emergency notice or
warning-like product on FMI's website. The official source remains
[FMI's warning service](https://en.ilmatieteenlaitos.fi/warnings).

Use your actual entity IDs in these examples. Only the **Weather warnings** count sensor, such as
`sensor.helsinki_weather_warnings`, carries the message lists; the warning-level sensor and the
**Weather warning** binary sensor do not. A standard Markdown card can show every current and
future message without installing a custom frontend card. This example picks an icon from the FMI
event code and shows red and orange messages as errors, yellow as warnings, green as success, and
upcoming or unclassified messages as information. Pointed at an entity without message lists, it
reports that mistake instead of claiming that no warning is active:

```yaml
type: markdown
title: FMI weather warnings
content: |
  {% set entity = 'sensor.helsinki_weather_warnings' %}
  {% set icons = {'wind': 'mdi:weather-windy', 'seaWind': 'mdi:weather-windy-variant',
     'rain': 'mdi:weather-pouring', 'thunderstorm': 'mdi:weather-lightning',
     'seaThunderstorm': 'mdi:weather-lightning-rainy', 'trafficWeather': 'mdi:road-variant',
     'pedestrianSafety': 'mdi:walk', 'forestFireWeather': 'mdi:fire',
     'hotWeather': 'mdi:thermometer-high', 'coldWeather': 'mdi:snowflake-thermometer',
     'uvNote': 'mdi:weather-sunny-alert', 'seaIcing': 'mdi:snowflake-alert',
     'seaWaterHeight': 'mdi:waves-arrow-up', 'seaWaveHeight': 'mdi:waves'} %}
  {% set types = {'red': 'error', 'orange': 'error', 'yellow': 'warning', 'green': 'success'} %}
  {% set active = state_attr(entity, 'warnings') %}
  {% if not has_value(entity) %}
  <ha-alert alert-type="error">Warning data is unavailable.</ha-alert>
  {% elif active is none %}
  <ha-alert alert-type="error">{{ entity }} is not an FMI weather warnings count sensor.</ha-alert>
  {% else %}
  {% for w in active %}
  <ha-alert alert-type="{{ types.get(w.color, 'info') }}" title="{{ w.headline | e }}"><ha-icon icon="{{ icons.get(w.event_code, 'mdi:alert') }}"></ha-icon> {{ w.description | e }}<br>Ends: {{ as_local(as_datetime(w.expires)).strftime('%a %d %b %H:%M') }}</ha-alert>
  {% else %}
  No active warnings for this location.
  {% endfor %}
  {% for w in state_attr(entity, 'upcoming_warnings') or [] %}
  <ha-alert alert-type="info" title="Upcoming: {{ w.headline | e }}"><ha-icon icon="{{ icons.get(w.event_code, 'mdi:alert') }}"></ha-icon> {{ w.description | e }}<br>Starts: {{ as_local(as_datetime(w.onset)).strftime('%a %d %b %H:%M') }}</ha-alert>
  {% endfor %}
  {% endif %}
```

An automation can notify on a changed active message list, including replacement warnings when
the count stays the same. Comparing the list avoids repeating a notification for each retrieval:

```yaml
alias: FMI active warning changed
triggers:
  - trigger: state
    entity_id: sensor.helsinki_weather_warnings
conditions:
  - condition: template
    value_template: >-
      {{ trigger.from_state is not none and trigger.to_state is not none
         and trigger.to_state.state not in ['unknown', 'unavailable']
         and trigger.to_state.state | int(0) > 0
         and trigger.from_state.attributes.get('warnings', [])
             != trigger.to_state.attributes.get('warnings', []) }}
actions:
  - action: persistent_notification.create
    data:
      title: FMI weather warnings
      message: >-
        {{ trigger.to_state.attributes.warnings
           | map(attribute='headline') | join('; ') | e }}
```

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

Replace every example entity ID with the exact ID from your entity registry. The first examples
use only standard Home Assistant cards. The optional Detailed Weather Forecast example uses an
independently maintained dashboard card to expose more of the integration's current and forecast
metrics in one weather view.

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

### More Detailed Weather Card (Optional)

Home Assistant's standard weather card has a fixed presentation and does not render every current
or forecast field supplied by this integration. The independently maintained
[Detailed Weather Forecast Card](https://github.com/tobiasb80/detailed-weather-forecast) can add:

- current feels-like temperature, precipitation probability, and thunderstorm probability as
  always-visible header chips;
- dew point, pressure, and low/medium/high cloud-cover sensors in expandable current details;
- apparent temperature below every hourly and daily forecast item;
- dew point, pressure, and total cloud coverage in the expandable hourly and daily details.

Add the repository URL above as a custom repository with category **Dashboard** in the Marketplace
or HACS, install the card, and refresh the browser. Both normally register its dashboard resource.
If the card type is still unavailable, add
`/local/community/detailed-weather-forecast/detailed-weather-forecast.js` (Marketplace) or
`/hacsfiles/detailed-weather-forecast/detailed-weather-forecast.js` (HACS; this path also keeps
working after the Marketplace takes over) as a JavaScript module under
**Settings > Dashboards > Resources**.

This card is optional and is not distributed or maintained by the FMI integration. Its
installation, updates, and card-specific support remain with its own project. The following
configuration uses only generic example IDs:

```yaml
type: custom:detailed-weather-forecast-card
entity: weather.helsinki
name: Helsinki

show_header: true
show_background: false
compact_header_chips: false
hourly_forecast: true
daily_forecast: true

header_chips:
  - type: attribute
    attribute: apparent_temperature
    name: Feels like
    icon: mdi:thermometer
  - type: entity
    entity: sensor.helsinki_precipitation_probability
    name: Rain probability
    icon: mdi:weather-rainy
  - type: entity
    entity: sensor.helsinki_thunderstorm_probability
    name: Thunder
    icon: mdi:weather-lightning

header_info:
  - type: attribute
    attribute: dew_point
    name: Dew point
    icon: mdi:thermometer-water
  - type: attribute
    attribute: pressure
    name: Air pressure
    icon: mdi:gauge
  - type: entity
    entity: sensor.helsinki_low_cloud_cover
    name: Low cloud cover
    icon: mdi:weather-cloudy
  - type: entity
    entity: sensor.helsinki_medium_cloud_cover
    name: Medium cloud cover
    icon: mdi:weather-cloudy
  - type: entity
    entity: sensor.helsinki_high_cloud_cover
    name: High cloud cover
    icon: mdi:weather-cloudy

hourly_extra_attribute:
  attribute: apparent_temperature
  color: var(--secondary-text-color)

hourly_info:
  - attribute: apparent_temperature
    name: Feels like
    icon: mdi:thermometer
  - attribute: dew_point
    name: Dew point
    icon: mdi:thermometer-water
  - attribute: pressure
    name: Air pressure
    icon: mdi:gauge
  - attribute: cloud_coverage
    name: Cloud cover
    icon: mdi:weather-cloudy

daily_extra_attribute:
  attribute: apparent_temperature
  color: var(--secondary-text-color)

daily_info:
  - attribute: apparent_temperature
    name: Maximum feels like
    icon: mdi:thermometer
  - attribute: dew_point
    name: Mean dew point
    icon: mdi:thermometer-water
  - attribute: pressure
    name: Mean air pressure
    icon: mdi:gauge
  - attribute: cloud_coverage
    name: Mean cloud cover
    icon: mdi:weather-cloudy
```

The hourly weather forecast already carries apparent temperature, precipitation probability, dew
point, pressure, and total cloud coverage, so the card can render them for each forecast item. The
daily apparent-temperature value is the day's maximum; daily pressure, dew point, and total cloud
coverage are means. Daily precipitation probability is intentionally absent because it cannot be
derived correctly from the available hourly event probabilities.

Low/medium/high cloud cover and thunderstorm probability are currently separate forecast-backed
sensor states rather than fields in Home Assistant's hourly forecast schema. The example therefore
shows them for the sensor's selected current forecast hour, not as a separate value for every
future hour. Dashboard YAML cannot change that data boundary. Click the header condition to reveal
`header_info`, and click an hourly or daily item to reveal its configured detail list.

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
- **Warnings are unavailable or the log reports warning timeouts:** download the entry's
  diagnostics and check `failure_reason` in the `warnings` section. A single `timeout` keeps the
  last messages for up to 15 minutes and is harmless. If the log repeatedly shows lines such as
  `FMI warnings retrieval failed (timeout): exceeded the read timeout of 10 s`, report them in the
  issue tracker. They name the limit that expired, so its value can be reviewed.
- **Best time says “No suitable time today”:** FMI forecast data is healthy, but there is no
  complete remaining current-day hour that passes your configured limits. Widen the limits if
  appropriate. `unavailable` instead means the remaining forecast data cannot support a result.
- **A dashboard example reports an unknown entity:** replace the sample ID with the entity ID shown
  in your registry. Reconfigured and migrated entries deliberately retain their established IDs.

When reporting a problem, attach sanitized Home Assistant diagnostics and relevant integration log
lines. Diagnostics redact configured coordinates, the entry's display name, the observation
station ID, and legacy coordinate-derived identity. Do not publish precise home coordinates or raw
external responses.

## Remove

1. Open **Settings > Devices & services > Finnish Meteorological Institute**.
2. Open the entry menu and select **Delete**. This removes its devices and entities from Home
   Assistant.
3. Remove the repository from the Marketplace or HACS, or delete `custom_components/fmi/` for a
   manual installation.
4. Restart Home Assistant.

## External Services And Privacy

FMI receives place-search text when that optional path is used and receives the final coordinates
needed for validation, weather, lightning-area, and sea-level requests. Search text is transient:
it is not stored in the config entry, logs, or diagnostics. FMI lightning strike coordinates are
processed transiently in memory for local distance/bearing calculation. They are not sent to a
second provider and are not exposed in state, attributes, logs, or diagnostics. See the
[security and privacy contract](contracts/COMPATIBILITY_SECURITY.md).
Warning requests fetch a fixed national-language feed without sending configured coordinates;
point-in-polygon filtering happens locally. Diagnostics contain warning-source health and cadence,
without warning texts, area names, message IDs, or warning counts.

Documentation references verified 2026-11-05:

- [Home Assistant Marketplace and HACS](https://www.hacs.xyz/docs/marketplace/)
- [HACS custom repositories](https://www.hacs.xyz/docs/faq/custom_repositories/)
- [HACS repository download and update behavior](https://www.hacs.xyz/docs/use/repositories/dashboard/)
- [Home Assistant weather forecast card](https://www.home-assistant.io/dashboards/weather-forecast/)
- [Home Assistant entities card](https://www.home-assistant.io/dashboards/entities/)
- [Home Assistant integration removal](https://www.home-assistant.io/common-tasks/general/#removing-an-integration-instance)
