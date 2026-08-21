<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# P04 Implementation Plan: Useful Forecast Sensors And Deterministic Best Time

> **Archive notice:** This completed plan is a dated execution record. Use the current
> [contract catalog](../../docs/contracts/README.md), [maintenance runbooks](../../docs/maintenance/),
> and [plan archive index](../README.md) instead of treating historical commands or requirements
> below as current policy.

> **Target repository:** [`kogeler/fmi-hass-custom`](https://github.com/kogeler/fmi-hass-custom)
> **Intended executor:** OpenAI Codex
> **Plan baseline date:** 2026-08-20
> **Execution model:** sequential green session checkpoints
> **Plan status:** `DONE`
> **Planning branch/commit:** `master` at `4fd9861e3c752c3efa33c2227fc41ac4b3e93f08`
> **Execution branch:** `feature/useful-forecast-sensors`
> **Starting release:** published `1.2.0`
> **Release train:** `1.3.0` for additive sensors and weather attributes plus a documented
> Best-time behavior change
> **Canonical agent entry point:** `AGENTS.md`
> **Verified execution baseline:** `plans/P04/BASELINE.md`
> **Execution reports:** `plans/P04/S00.md` through `plans/P04/S05.md`

---

## 1. How to use this plan

The canonical plan path is:

```text
plans/P04/PLAN.md
```

Before execution, P04 contains only `PLAN.md`. Successful execution must produce:

```text
plans/P04/
  PLAN.md
  BASELINE.md
  S00.md
  S01.md
  S02.md
  S03.md
  S04.md
  S05.md
```

Do not create an unverified baseline or empty reports. S00 owns `BASELINE.md`; every session owns
its chronological report. `PLAN.md` is the living tracker, requirement matrix, decision log, and
definition of done. Current technical contracts belong in `docs/maintenance/` only after tests
prove the implemented behavior. Do not store execution progress there.

P01-P03 are complete historical records. Do not extend or rewrite them for P04.

To execute the whole plan after the owner selects a branch and release:

```text
Read AGENTS.md and plans/P04/PLAN.md in full. Inspect git status and execute S00 through
S05 sequentially. At every boundary update PLAN.md, write the owning report, run all
session gates, and continue only from a green checkpoint. Correct the plan immediately
when verified reality differs. Do not commit or push.
```

To resume:

```text
Read AGENTS.md and plans/P04/PLAN.md in full. Inspect git status, the current weather,
sensor, FMI-adapter, options, and forecast code, and the previous P04 report. Execute the
next NOT_STARTED or IN_PROGRESS session whose prerequisites are DONE. Do not repeat
completed work or claim checks that were not run.
```

### Context-safety rule

Each session owns one coherent concern. If a session becomes too large:

1. Stop at a green, documented checkpoint.
2. Add explicit sub-sessions such as `S02-A` and `S02-B` to this plan.
3. Record the revised dependency order and reason immediately.
4. Keep the parent `IN_PROGRESS` until every mandatory sub-session is `DONE`.
5. Finish the split concern before starting the next numbered session.

Do not silently include unrelated location, lightning, sea-level, station, CI, dependency, or
container work.

---

## 2. Mission

Expose eight useful metrics already available from the selected FMI forecast request or calculated
by the selected client, enrich the Home Assistant weather contract where it has a standard field,
and replace the current warmest-hour Best-time heuristic with a deterministic, transparent
outdoor-comfort selection.

The required new sensor entities are:

| Sensor | Native unit | Source and meaning |
|---|---|---|
| Feels like | °C | `WeatherData.feels_like`; deterministically calculated by `fmi-weather-client` from FMI temperature, humidity, and wind |
| Dew point | °C | FMI `DewPoint`; already exposed on weather entities |
| Atmospheric pressure | hPa | FMI `Pressure`; mean-sea-level pressure, already exposed on weather entities |
| Low cloud cover | % | FMI `LowCloudCover` |
| Medium cloud cover | % | FMI `MediumCloudCover` |
| High cloud cover | % | FMI `HighCloudCover` |
| Precipitation probability | % | FMI `PoP`; probability of at least 0.1 mm during the preceding forecast hour |
| Thunderstorm probability | % | FMI `ProbabilityThunderstorm`; forecast probability of thunder for the point/hour |

The same FMI request must continue to carry all forecast-backed data. P04 adds no provider, API
key, HTTP request, runtime dependency, captured private payload, or locally invented weather
observation.

Home Assistant's standard weather interface must additionally expose:

- current `native_apparent_temperature` on the main forecast-backed weather entity and the
  configured observation weather entity when a finite client value exists;
- `native_apparent_temperature` in every hourly forecast item with a finite value;
- daily maximum finite apparent temperature as the daily apparent-temperature value;
- hourly `precipitation_probability` from FMI `PoP`;
- no fabricated daily precipitation probability, because hourly event probabilities cannot be
  combined without a dependence model that FMI does not provide.

The existing **Best time of day** entity remains in place with its registry identity, customized
entity ID, `HH:MM` state shape, device, config entry, and existing automation-facing attributes.
Its selection must no longer initialize to current weather or maximize air temperature.
When a valid forecast contains no suitable remaining hour, the entity remains available with a
translated `no_suitable_time` state instead of pretending the current time is best or reporting an
FMI outage.

---

## 3. Scope boundaries and non-goals

### 3.1 Included behavior

P04 includes:

- additive sensor entities for all eight listed metrics on the existing main location device;
- correct Home Assistant device classes, native units, state classes, availability, translation
  keys, icons, naming, unit conversion, and recorder-safe numeric states;
- reuse of already parsed `dew_point`, `pressure`, `cloud_low_cover`, `cloud_mid_cover`,
  `cloud_high_cover`, and `feels_like` client fields;
- adding `PoP` and `ProbabilityThunderstorm` to the adapter's existing coordinate request;
- safe one-pass, timestamp-aligned extraction of the two probability fields from the same bounded
  XML response used by the selected client;
- a typed integration-owned supplement model because upstream `WeatherData` 1.0.0 has no fields for
  the two probabilities;
- finite/range validation for probabilities, including valid `0.0` and `100.0` boundaries;
- weather current/hourly/daily apparent-temperature support through Home Assistant's native API;
- hourly weather forecast precipitation probability through Home Assistant's native API;
- a future-only, current-local-day Best-time candidate set and deterministic total ordering;
- retention of existing Best-time settings and identities, with a documented improvement in the
  meaning of the stored temperature range;
- offline, Home Assistant-level, live, migration, multi-entry, privacy, and release regressions;
- user guidance, current maintenance contracts, translations, changelog, and release metadata.

### 3.2 Additive and changed surfaces

| Existing surface | P04 result |
|---|---|
| Main location device | Gains eight new sensor entities; existing entities are unchanged |
| Main and configured-station weather current attributes | Gain apparent temperature when finite |
| Hourly weather forecast | Gains apparent temperature and precipitation probability when finite |
| Daily weather forecast | Gains maximum finite apparent temperature; no derived daily PoP |
| Best-time entity identity and state format | Preserved |
| Best-time selection | Changes from current-or-warmest eligible air temperature to the frozen future-only comfort/risk ordering |
| Valid forecast with no suitable remaining hour | Available stable state `no_suitable_time`, translated in the frontend |
| Existing min/max temperature option keys | Preserved; interpreted as acceptable feels-like temperature for Best-time selection |
| Existing Best-time attributes | Preserved and extended with apparent temperature and both probabilities |

The Best-time algorithm change is intentional and user-visible. Document it, but do not recreate
the entity or require users to repair dashboards and automations.

### 3.3 Explicitly excluded behavior

Do not implement any of the following in P04:

- `fmiopendata`, another Python FMI library, another weather service, or direct non-FMI data;
- a second FMI request for probabilities or fields already available in the edited forecast;
- UV index, visibility, solar radiation, air quality, pollen, radar, or a generic environmental
  index; these require separately proven data products and belong to future plans;
- UTCI, WBGT, HeatRisk, Humidex, a Tourism Climate Index, or a proprietary commercial activity
  index under the name of another operator;
- inferred mean radiant temperature, direct-sun exposure, shade, clothing, age, health, activity
  intensity, acclimatization, indoor comfort, or surface temperature;
- a numeric "scientific comfort score" assembled from arbitrary weights;
- a medical, occupational, lightning-safety, heat-warning, or outdoor-safety recommendation;
- daily precipitation probability calculated as a sum, average, maximum, or independent-event
  complement from hourly PoP;
- summing low/middle/high cloud percentages into total cloud cover;
- changing observation-station request semantics merely to make optional forecast-only fields
  appear there;
- changing update intervals, forecast horizon, live xdist policy, request budget, or source
  isolation without reproduced evidence;
- deleting or renaming the Best-time entity, its option keys, existing unique IDs, customized
  entity IDs, or Recorder history;
- a refactor of every upstream weather model solely for stylistic consistency.

### 3.4 Why P04 does not implement UTCI or WBGT

UTCI is the best-established all-climate outdoor thermal-stress index found in planning research.
It requires air temperature, vapour pressure/humidity, 10-metre wind, and **mean radiant
temperature**, which itself depends on short- and long-wave radiation and solar geometry. WBGT also
requires radiant/globe-temperature inputs for outdoor sun exposure.

The selected client's current request does not request `RadiationGlobal`; it requests accumulated
fields, while its `feels_like` calculation only applies a radiation correction when an instantaneous
`RadiationGlobal` value exists. Planning live probes found no reliable finite radiation series in
the selected edited forecast at the public Helsinki and Kilpisjärvi points. Treating mean radiant
temperature as air temperature, assuming shade, or reconstructing actual irradiance from cloud
percentages would add an environmental assumption expressly outside the repository's deterministic
data boundary.

P04 therefore uses the selected client's FMI-derived apparent temperature as one transparent input
and makes no UTCI/WBGT claim. Reconsider those indices only if a future plan proves all required FMI
radiation components, spatial/temporal semantics, and a maintained local implementation.

### 3.5 Why P04 does not copy a commercial activity index

AccuWeather and The Weather Company publish outdoor/activity index products, but their public
documentation exposes categories and outputs rather than a reproducible weighting formula.
Different products also separate running, hiking, dog walking, beach, skiing, and other activities,
demonstrating that one globally valid "best outdoor hour" does not exist without an activity and
personal context.

P04 must remain auditable and provider-independent after FMI data arrives. It therefore uses an
explicit ordered policy rather than reverse-engineering or imitating a proprietary score.

---

## 4. Frozen product contracts

### 4.1 Data ownership and single-request contract

- Continue using `fmi-weather-client==1.0.0` through `custom_components/fmi/fmi_client.py`.
- Retain the client's edited Scandinavian point query, timeout, executor boundary, privacy filter,
  safe XML parser, and current/hourly timing.
- Generalize the existing extra-parameter adapter so it requests exactly
  `HourlyMaximumGust`, `PoP`, and `ProbabilityThunderstorm` in the same parameter list.
- Parse the XML field-name order rather than assuming a fixed column index.
- Align values by aware UTC timestamp, as the gust adapter already does.
- For duplicate timestamps, retain the last row, matching the forecast normalization rule.
- Never replace a missing/invalid probability with zero and never clamp an out-of-range value.
- Keep the upstream `models.WeatherData` object intact. Do not place probability values in unrelated
  unused model fields.
- Return or store one narrow immutable supplement per timestamp, containing only finite validated
  precipitation and thunderstorm probabilities.
- Clear supplements whenever their owning current/forecast request fails or is replaced. A stale
  probability must never remain paired with a newer weather sample.
- Missing supplement fields make only their direct sensor/weather value unavailable; they do not
  disable temperature, weather condition, unrelated sensors, or the whole coordinator.

S00 must freeze the exact dataclass/envelope names. The expected shape is equivalent to:

```python
@dataclass(frozen=True, slots=True)
class ForecastProbabilities:
    precipitation: float | None
    thunderstorm: float | None


@dataclass(frozen=True, slots=True)
class CurrentWeatherResult:
    weather: models.Weather
    probabilities: ForecastProbabilities


@dataclass(frozen=True, slots=True)
class ForecastResult:
    forecast: models.Forecast
    probabilities_by_time: Mapping[datetime, ForecastProbabilities]
```

The mapping in `ForecastResult` must be wrapped in a read-only `MappingProxyType` before the result
crosses the adapter boundary. Observation calls retain their upstream model because they do not
request probability fields. A mutable global map or parser-to-entity hidden side channel is not
acceptable.

### 4.2 Metric validation and semantics

All numeric values must pass the existing finite-number boundary. Additional rules are:

| Metric | Valid range | Missing/invalid behavior |
|---|---:|---|
| feels like | finite °C | unavailable; never recalculate with a second integration formula |
| dew point | finite °C | unavailable |
| pressure | finite hPa | unavailable; do not relabel as station pressure |
| each cloud layer | 0–100% inclusive | unavailable outside range; do not clamp |
| PoP | 0–100% inclusive | unavailable outside range; preserve explicit zero |
| thunderstorm probability | 0–100% inclusive | unavailable outside range; preserve explicit zero |

Pressure from the selected edited forecast is mean-sea-level pressure. Cloud-layer percentages
represent cover in each modeled layer; layers overlap and must not be added. PoP is independent of
forecast precipitation amount: a low chance can coexist with a large conditional amount.

### 4.3 Sensor contract

All eight new sensors:

- belong to the existing main location device and config entry;
- use `_attr_has_entity_name = True` through the existing base class;
- have new stable description keys and unique-ID suffixes without changing any existing suffix;
- update from cached coordinator memory only;
- follow the existing forecast-backed sensor source-time policy, including the configured legacy
  interval;
- expose no broad copy of a forecast object in attributes;
- become unavailable when their own selected value is missing or invalid and recover on a later
  valid coordinator refresh;
- preserve valid `0.0` states;
- use FMI-only attribution.

Metadata is frozen as:

| Description key | English entity name / unique-ID suffix input | Device class | Native unit | State class | Icon |
|---|---|---|---|---|---|
| `feels_like` | Feels like | temperature | °C | measurement | `mdi:thermometer` |
| `dew_point` | Dew point | temperature | °C | measurement | `mdi:thermometer-water` |
| `atmospheric_pressure` | Atmospheric pressure | atmospheric pressure | hPa | measurement | `mdi:gauge` |
| `low_cloud_cover` | Low cloud cover | none | % | measurement | `mdi:weather-cloudy` |
| `medium_cloud_cover` | Medium cloud cover | none | % | measurement | `mdi:weather-cloudy` |
| `high_cloud_cover` | High cloud cover | none | % | measurement | `mdi:weather-cloudy` |
| `precipitation_probability` | Precipitation probability | none | % | measurement | `mdi:weather-rainy` |
| `thunderstorm_probability` | Thunderstorm probability | none | % | measurement | `mdi:weather-lightning` |

Finnish names are frozen respectively as `Tuntuu kuin`, `Kastepiste`, `Ilmanpaine`,
`Alapilvisyys`, `Keskipilvisyys`, `Yläpilvisyys`, `Sateen todennäköisyys`, and
`Ukkosen todennäköisyys`.

Do not use precipitation-intensity or any unrelated device class for probability. S00 must verify
the exact locked Home Assistant enum names before S02.

### 4.4 Weather entity contract

- Set `_attr_native_apparent_temperature` from finite `WeatherData.feels_like` for every current
  weather entity, including a configured station observation when its client model supplies it.
- Use the existing native temperature unit for apparent temperature.
- Add `ATTR_FORECAST_NATIVE_APPARENT_TEMP` to each hourly item.
- Add `ATTR_FORECAST_PRECIPITATION_PROBABILITY` as `int(round(value))` only after validating the
  finite 0–100 source value. This deliberately uses Python's deterministic half-to-even behavior
  (`12.5 -> 12`, `13.5 -> 14`) and never truncates.
- Add the maximum finite hourly apparent temperature to a daily item, parallel to daily maximum air
  temperature.
- Omit daily precipitation probability entirely.
- Keep current pressure, dew point, total cloud cover, humidity, wind, precipitation, condition,
  and existing daily aggregation unchanged.
- Do not expose low/middle/high cloud cover or thunder probability as ad hoc weather attributes;
  their dedicated sensors are the supported Home Assistant surface.

### 4.5 Best-time candidate contract

The retained entity describes the best **remaining forecast hour on the current Home Assistant
local date under the user's configured limits**. It is a planning aid for ordinary outdoor time,
not a safety guarantee.

Candidate construction is frozen as follows:

1. Start with the coordinator's existing configured-interval forecast series; retain the option and
   its persisted key.
2. Convert timestamps through Home Assistant's timezone helpers.
3. Include only aware samples whose local timestamp is not earlier than `dt_util.now()` and whose
   full local date equals the current local date.
4. Never insert current observations as a default candidate.
5. Require finite symbol, air temperature, feels-like temperature, humidity, sustained wind,
   preceding-hour precipitation, PoP, and thunderstorm probability.
6. Preserve the existing accepted weather-symbol set as a hard gate. Heavy rain/snow, sleet, and
   explicit thunderstorm symbols remain rejected unless S00 proves the current list contains a
   documented symbol error that must be corrected in this plan first.
7. Apply the persisted min/max temperature range to **feels-like temperature**, because this entity
   is selecting human-perceived outdoor conditions. Preserve the keys and values; update option
   labels/help and release notes to explain the clarified meaning.
8. Apply existing humidity, wind, and precipitation limits as inclusive hard gates with their
   current units and semantics.
9. The options form must reject a submitted minimum greater than its corresponding maximum for
   temperature, humidity, wind, or precipitation. Never silently swap or reset user values.
   Previously stored inverted limits remain loadable but yield no suitable candidate until the user
   saves a valid configuration; document that correction path rather than mutating data behind the
   user.
10. Distinguish three outcomes explicitly:
    - selected candidate: `best_state=available`, selected cached fields, native state `HH:MM`;
    - valid available forecast with no remaining hour on the current local date, or with at least
      one complete evaluated sample but none passing the symbol/preference gates: clear selected
      cached fields, set a distinct no-suitable status, and expose available native state
      `no_suitable_time`;
    - forecast disabled, failed, empty, or unusable for evaluation because remaining samples exist
      but none has a complete required metric set: clear selected cached fields, set
      `best_state=not_available`, and expose `None`/unavailable.
11. Do not emit the current time or a least-bad value outside the user's limits.

This deliberately fixes the current behavior where the coordinator initializes `best_time` and
attributes from current weather even when no forecast candidate qualifies.

### 4.6 Best-time deterministic ordering

For every candidate passing section 4.5, calculate the following tuple and select its minimum:

```text
(
  thunderstorm_probability,
  absolute(feels_like - midpoint(configured_min_temp, configured_max_temp)),
  precipitation_probability,
  precipitation_amount,
  timestamp,
)
```

This order is intentional:

1. Lower forecast thunder risk wins before ordinary comfort refinements.
2. Thermal choice uses FMI-derived apparent temperature and the user's own acceptable range; it
   never rewards the hottest hour.
3. Among equally safe/thermally close hours, lower rain probability wins.
4. Then lower predicted one-hour amount wins.
5. Exact ties select the earliest remaining hour for stable, unsurprising automation behavior.

Humidity and wind are not scored again after their inclusive gates because both already influence
the selected client's apparent-temperature calculation; counting them again would silently weight
them twice. Pressure and cloud-layer cover are not generic human-comfort criteria and do not enter
the ordering. No arbitrary weighted sum, normalization constant, or false 0–100 precision is
published.

### 4.7 Best-time state and attributes

- Preserve the existing `best_time_of_day` description key, unique ID suffix, entity registry row,
  customized entity ID, device, and `HH:MM` native state.
- Add stable finite state token `no_suitable_time` with source/English/Finnish frontend translations
  (`No suitable time today` / `Ei sopivaa aikaa tänään`, subject to S00 language review).
- Preserve existing `location`, `time`, `temperature`, `relative_humidity`, `precipitation`, and
  `wind_speed` attributes for a selected candidate.
- Add `apparent_temperature`, `precipitation_probability`, and
  `thunderstorm_probability` attributes for transparency.
- Keep `time` as the aware selected datetime, not only the display string.
- Clear all dynamic selection attributes when unavailable; never retain yesterday's or an earlier
  refresh's candidate.
- Clear the same dynamic selection attributes for `no_suitable_time`; the token itself is the
  complete valid result.
- Do not expose the ordering tuple as a numeric score.
- Recompute on every coordinator refresh and option reload without recreating the entity.

---

## 5. Engineering constraints

### 5.1 Evidence before change

For each behavior:

1. Characterize the selected client, FMI response, Home Assistant schema, current sensor metadata,
   and Best-time defect.
2. Add a deterministic regression and confirm its pre-change failure when practical.
3. Implement the smallest coherent boundary.
4. Run focused tests and all owning session gates.
5. Record exact results and any plan correction in the owning report.

If execution discovers an error, inaccuracy, omission, ambiguity, stale assumption, or unsafe or
infeasible instruction in this plan, or the executor deliberately chooses a materially different
course:

1. Continue the affected work; do not pause execution solely because the plan requires correction.
2. In parallel, correct `PLAN.md` immediately in the same session as soon as the error,
   inaccuracy, or departure becomes known.
3. Update every impacted requirement, session, decision, risk, test, and definition-of-done entry,
   not only the paragraph that exposed the problem.
4. Record the evidence and reason in the owning report; the report does not substitute for
   correcting the plan.

Treat correction of the plan as part of the affected implementation work and keep both synchronized
throughout execution. Never defer a known correction to a report, handoff, or final review.

### 5.2 Async, parsing, and privacy

- Retain one executor-bound synchronous selected-client request/parser operation per current or
  forecast call.
- Parse bounded safe XML; do not add a second unbounded XML parser pass.
- Preserve cancellation and the enclosing coordinator timeout.
- Do not log coordinates, query parameters, raw XML, raw responses, arbitrary upstream exception
  bodies, or coordinate-derived identity.
- A parser error in mandatory upstream weather data retains current primary-source failure
  semantics. A missing optional probability column/value must not abort otherwise usable weather.
- Keep all entity properties memory-only.

### 5.3 Missing data and availability

- `None`, malformed values, NaN, infinities, and out-of-range percentages are missing, not zero.
- Existing forecast/current source failure continues to clear stale primary data and marks its
  coordinator unavailable.
- One missing new metric affects only that sensor/weather field. Other new and old fields continue
  to update.
- Best-time selection requires its complete candidate tuple; incomplete samples are skipped.
- A healthy non-empty forecast with no suitable remaining current-day result exposes the available
  `no_suitable_time` token. Forecast disabled/failure/empty/unusable remains unavailable. Neither
  outcome disables the weather coordinator.
- Later complete data recovers without reload.

### 5.4 Identity and migration

- Keep config-entry version 2 unless execution discovers an actual persisted-data transformation;
  no version bump is expected.
- Preserve every existing sensor/weather unique ID, entity registry row, customized entity ID,
  device identifier, entry identity, options, and disabled state.
- New sensor keys must not collide with legacy suffixes or existing entities.
- Do not rename an existing entity to improve English wording.
- Preserve all current option keys. Only translated labels/help clarify that the temperature range
  controls apparent-temperature comfort for Best-time selection.
- Exercise the v0.6.2/two-entry registry fixture plus a current 1.2.0 loaded-entry fixture. Existing
  entities must remain attached while new entities are added normally.
- Do not alter Recorder history.

### 5.5 Dependencies and network policy

- Keep `fmi-weather-client==1.0.0` and existing direct dependencies unchanged.
- Add no runtime or development dependency for comfort calculations.
- Do not hand-edit generated requirement locks.
- Invoke project tooling, Python, Home Assistant, validators, dependency operations, and containers
  only through supported `make` targets. Never invoke Podman or an image directly. Add or extend a
  confined Make target before performing an operation that the existing tooling does not expose.
- Ordinary tests remain deterministic and socket-blocked.
- Permanent live probes remain explicitly marked, public-location-only, shared-budgeted, and
  xdist-safe.
- Adding parameters to an existing request must not increase the current twelve-attempt suite
  ceiling or two-request semaphore. If S00 measures an actual additional request, stop and correct
  the design rather than silently raising the budget.

### 5.6 Release and documentation policy

- Published `1.2.0` history is immutable.
- P04 is release-bearing because it adds user-visible entities/attributes and changes Best-time
  selection. The owner selects the exact next version before S05; `1.3.0` is recommended.
- Update `.version`, manifest mirror, and one matching dated changelog section only in S05.
- Lead the changelog with useful new sensors and weather apparent temperature, then explain the
  Best-time improvement and the clarified option semantics.
- Update `SENSORS.md`, `FORECAST_SEMANTICS.md`, `TIME_AND_MISSING_DATA.md`, `RUNTIME.md`,
  `AVAILABILITY.md`, `COMPATIBILITY_SECURITY.md`, and `LIVE_TESTS.md` only where their current
  contract changes.
- Update `MIGRATIONS.md` only to record that additive sensors and the in-place Best-time behavior
  change require no registry/config migration.
- Do not record execution progress in current maintenance documentation.

### 5.7 Git and living-plan rules

- Execute on an owner-selected non-`master` branch.
- Do not commit, push, tag, publish, or mutate GitHub issues.
- Suggested owner commit messages must describe completed behavior and must not contain `P04`,
  session numbers, or plan/step identifiers.
- Never reset, stash, overwrite, or reformat unrelated owner work.

---

## 6. Planning baseline to verify in S00

This is a read-only planning snapshot from 2026-08-20. It is not execution evidence.

### 6.1 Repository and release state

- Planning worktree was clean on `master` at
  `4fd9861e3c752c3efa33c2227fc41ac4b3e93f08` before this plan file was added.
- `.version` and manifest are `1.2.0`.
- Runtime direct dependencies are `fmi-weather-client==1.0.0` and `xmltodict==1.0.4`.
- P01-P03 are complete; P04 did not previously exist.
- The rootless Podman, tar-stream confinement, wheel/hash locks, automatic xdist, live budget,
  release gates, and privacy rules are not being redesigned.

### 6.2 Current client and FMI data path

- The selected client requests
  `fmi::forecast::edited::weather::scandinavia::point::multipointcoverage` for both current and
  future coordinate forecasts.
- Its request already includes temperature, dew point, pressure, humidity, wind, total/low/middle/
  high cloud cover, precipitation, and accumulated radiation fields.
- `WeatherData` 1.0.0 already contains `dew_point`, `pressure`, `cloud_low_cover`,
  `cloud_mid_cover`, `cloud_high_cover`, and `feels_like`.
- `feels_like` is calculated by the client using code ported from FMI SmartMet math. With the
  selected request it uses temperature, wind, and humidity; the optional instantaneous
  `RadiationGlobal` correction is not supplied by the current request.
- Upstream `WeatherData` has no PoP or thunder-probability field.
- The integration already adds `HourlyMaximumGust` to the same private request boundary and parses
  it by field name and UTC timestamp. P04 can generalize this reviewed boundary instead of adding a
  call or replacing the client.
- Planning FMI metadata identifies `Pressure` as mean-sea-level pressure and publishes `PoP` plus
  `ProbabilityThunderstorm` for the edited `pal_skandinavia` product.
- Prior bounded public-location research observed finite PoP and thunder probabilities for all 48
  checked hourly samples at Helsinki and Kilpisjärvi. S00 must reproduce this through the marked
  live harness and record exact timestamps/results rather than treating planning notes as proof.

### 6.3 Current Home Assistant surface

- The weather entity already exposes current pressure and dew point and hourly/daily pressure and
  dew point.
- It does not set apparent temperature.
- Current Home Assistant defines `native_apparent_temperature` for weather state and
  `native_apparent_temperature` plus `precipitation_probability` for forecast items.
- The integration already exposes dedicated temperature, humidity, total cloud cover,
  precipitation, and wind sensors but no dedicated feels-like, dew-point, pressure, layered-cloud,
  PoP, or thunder-probability sensors.
- Sensor setup currently adds every description to the main location device. New descriptions are
  additive and require new unique IDs only.

### 6.4 Current Best-time defect

- The coordinator initializes Best-time state/time/attributes from current weather on every
  calculation.
- Forecast candidates are filtered by current local date, a finite allowlist of symbols, and
  configured temperature/humidity/wind/precipitation bounds.
- Among passing candidates it replaces the selection only when air temperature is greater than the
  stored value.
- Consequently it selects the warmest passing hour and retains current time when no warmer passing
  forecast exists, even when current weather itself did not pass every configured gate.
- It does not use feels-like temperature, PoP, thunder probability, or a deterministic full-tie
  policy.
- Its state is `HH:MM`; existing attributes are location, aware time, air temperature, relative
  humidity, precipitation, and wind speed.

### 6.5 Comfort-method research conclusion

- UTCI is a recognized all-climate outdoor thermal-stress index, but it requires mean radiant
  temperature in addition to air temperature, humidity, and wind.
- WBGT for outdoor sun/activity also needs radiation/globe-temperature inputs.
- NWS Heat Index is intended for warm/humid conditions and Wind Chill for cold/windy conditions;
  neither alone is an all-season best-hour method.
- FMI and Met Office both describe apparent temperature as a human-perception aid based on
  temperature, wind, and humidity, with substantial individual variation.
- WHO advises avoiding the hottest time during heat and moving strenuous activity to cooler hours,
  which directly contradicts the current maximize-temperature rule but does not define a universal
  optimum or cross-weather weighting formula.
- Commercial activity indices are activity-specific and do not publish reproducible calculation
  weights.
- Therefore P04 freezes a transparent risk/comfort ordering under user-configured limits and makes
  no universal physiological-score claim.

### 6.6 Questions S00 must close

1. Does the locked Home Assistant reference expose the exact current/hourly/daily apparent-
   temperature constants and atmospheric-pressure sensor device class described here?
2. What exact integer conversion does the locked Home Assistant forecast contract expect for a
   finite decimal PoP, and how will half values be handled deterministically?
3. Does the S01 production adapter expose finite 0–100 `PoP` and `ProbabilityThunderstorm` values
   for every sample on the first available future Europe/Helsinki local forecast date at both
   public live points?
4. Does adding both fields preserve one request per adapter call and all existing gust behavior?
5. What narrow typed envelope best prevents timestamp supplement drift without refactoring all
   upstream model consumers?
6. Does configured-station observation parsing produce a finite client `feels_like`; if not, the
   standard weather field must remain absent rather than locally recalculated a second way.
7. Does the exact current Best-time test reproduce both warmest-hour selection and current-time
   fallback?
8. Are all persisted option values valid when the temperature range is interpreted as feels-like,
   and what translation/release wording makes that behavior change explicit?
9. Are the proposed new unique-ID suffixes collision-free against every registry fixture and
   published integration line?
10. What owner-selected execution branch and release replace the placeholders in this plan?

---

## 7. Requirement closure matrix

Update status, evidence, report, and commit at every session boundary.

| ID | Required outcome | Owner | Primary evidence | Report | Commit | Status |
|---|---|---|---|---|---|---|
| R01 | All eight sensor entities expose correct finite values, metadata, units, availability, translations, device ownership, and stable identities | S02/S04 | sensor metadata, HA lifecycle, registry tests | `plans/P04/S02.md` | `OWNER_TO_COMMIT` | DONE |
| R02 | PoP and thunder probability are added and parsed from the same bounded FMI request with no extra network call or dependency | S01 | adapter request/parser/contract tests | `plans/P04/S01.md` | `OWNER_TO_COMMIT` | DONE |
| R03 | Probability supplements align by timestamp, reject invalid values, clear on replacement/failure, and cannot become stale | S01/S04 | parser/coordinator transition tests | `plans/P04/S04.md` | `OWNER_TO_COMMIT` | DONE |
| R04 | Current weather exposes apparent temperature through the standard HA property when finite, including station observation only when upstream supplies it | S02 | weather state tests | `plans/P04/S02.md` | `OWNER_TO_COMMIT` | DONE |
| R05 | Hourly forecasts expose apparent temperature and PoP; daily forecasts expose max apparent temperature and never fabricate daily PoP | S02 | forecast characterization/HA service tests | `plans/P04/S02.md` | `OWNER_TO_COMMIT` | DONE |
| R06 | Best-time considers only remaining current-local-day configured-interval forecast candidates, never defaults to current time, and distinguishes valid `no_suitable_time` from unavailable forecast data | S03 | deterministic time/candidate/state tests | `plans/P04/S03.md` | `OWNER_TO_COMMIT` | DONE |
| R07 | Best-time applies stored limits to apparent comfort and uses the frozen thunder/thermal/PoP/amount/time ordering without a weighted score | S03 | table-driven algorithm tests | `plans/P04/S03.md` | `OWNER_TO_COMMIT` | DONE |
| R08 | Best-time identity, `HH:MM` state, existing attributes/options, lifecycle, and custom entity IDs remain compatible; added attributes are additive and stale data clears | S03/S04 | registry/options/reload/multi-entry tests | `plans/P04/S04.md` | `OWNER_TO_COMMIT` | DONE |
| R09 | Missing one requested metric does not disable unrelated current weather, forecast, sensors, station, lightning, or sea level; recovery requires no reload | S04 | availability transition matrix | `plans/P04/S04.md` | `OWNER_TO_COMMIT` | DONE |
| R10 | Public live probes verify all fields/ranges at two climate-distinct FMI locations within the unchanged request budget | S01/S04 | marked live evidence | `plans/P04/S04.md` | `OWNER_TO_COMMIT` | DONE |
| R11 | User guide, translations, maintenance contracts, changelog, version, and release notes match proven semantics and limitations | S05 | documentation/version review | `plans/P04/S05.md` | `OWNER_TO_COMMIT` | DONE |
| R12 | Full offline, HA, validation, compatibility, security, dependency, distribution, live, and confinement gates pass with no unrelated diff | S05 | final verification matrix | `plans/P04/S05.md` | `OWNER_TO_COMMIT` | DONE |

Status values: `NOT_STARTED`, `IN_PROGRESS`, `BLOCKED`, `DONE`.

---

## 8. Candidate risks to investigate

| Risk | Why it matters | Required handling |
|---|---|---|
| Supplement timestamp drift | PoP/thunder could be attached to the wrong forecast hour | One typed response boundary, aware UTC keys, duplicate policy, alignment tests, atomic replacement |
| Fixed upstream NamedTuple | Adding fields with `_replace` is impossible and abusing another field corrupts semantics | Keep upstream model intact and own a narrow supplement model |
| Missing probability interpreted as zero | Would turn unknown risk into false certainty | Preserve `None`, validate 0–100, prove zero separately |
| Decimal PoP conversion | HA forecast schema exposes integer probability | Freeze and test one explicit rounding policy against locked HA behavior |
| Daily PoP temptation | Max/sum/average is not the probability of any daily precipitation | Omit it and assert absence |
| Apparent-temperature overclaim | Client calculation lacks current solar-radiation correction | Document temperature/wind/humidity boundary; do not label UTCI/WBGT/full-sun comfort |
| Best-time still shows now | Initial current-data fallback may survive a partial rewrite | Clear all fields first; construct forecast-only candidates; explicit regression |
| Hottest-hour bias survives | Ranking actual temperature or upper bound would preserve the defect | Use distance from configured apparent-temperature midpoint |
| No suitable time looks like FMI failure | Users lose a valid calculation result and source health becomes ambiguous | Available translated token for healthy forecast/no candidate; unavailable only for disabled/failed/empty/unusable forecast |
| Arbitrary hidden weights | A composite score would imply unsupported precision | Lexicographic tuple, no score, direct factor attributes |
| Probability dominates all comfort | Safety-first thunder priority is intentional but must be visible | Document exact order and provide attributes; do not call it universal optimum |
| Reinterpreted temperature option | Existing users may expect air temperature bounds | Keep keys/values, update labels/help/changelog, add migration note, owner review |
| New entity ID collision | Eight additions could conflict with registry history | Search fixtures, freeze keys/suffixes, exercise upgrade/custom-ID tests |
| Generic sensor attributes | Existing base attaches Best-time attributes broadly | Do not use P04 as an unrelated attribute refactor; add only required Best-time fields carefully |
| Station observation gap | Observation may not provide calculated feels-like | Expose standard field only if upstream supplies finite value; no second formula |
| Added FMI parameters fail at one point | Could make whole request fail | S00 live proof; retain selected query; correct plan before implementation if unsupported |
| Live request budget inflation | Extra calls would violate repository policy | Assert call count; same parameter list only; no budget increase |
| Stale data after options reload | Best-time or new sensor could retain previous selection | Clear-and-rebuild coordinator/entity state; transition and reload tests |

---

## 9. Required test architecture

### 9.1 Selected-client and parser contract tests

- Pin the relevant installed `WeatherData` fields and client release.
- Reproduce that upstream query omits PoP/thunder while the product publishes them.
- Assert the adapter parameter list adds gust, PoP, and thunder exactly once.
- Assert current and forecast calls each make one upstream request.
- Parse fields in reordered XML columns.
- Cover missing columns, blank/nil values, malformed rows, short rows, mismatched position/value
  counts, duplicate timestamps, naive/unrepresentable timestamps, NaN/infinity, below-zero, above-
  100, and valid 0/100 probabilities.
- Prove gust precedence remains unchanged after parser generalization.
- Prove unsafe/oversized XML is rejected before the upstream parser.
- Prove privacy filters/log records do not expose request parameters or raw XML.

### 9.2 Sensor metadata and state tests

- Assert exactly eight new description keys, unique-ID suffixes, names, icons, units, device
  classes, and state classes.
- Exercise native-to-user temperature and pressure conversion through Home Assistant state.
- Exercise percentage values and explicit zero through Home Assistant state.
- Assert invalid/missing values are unavailable and later valid values recover.
- Assert all new sensors belong to the existing main device and do not appear on the optional
  station observation device.
- Assert current configured-interval source selection matches existing sensor behavior.
- Assert translation parity for source, English, and Finnish.

### 9.3 Weather tests

- Current main weather apparent temperature.
- Current configured-station apparent temperature when finite and absence when missing.
- Hourly apparent temperature and PoP through both direct helper output and HA forecast service.
- Decimal PoP rounding boundaries.
- Daily maximum apparent temperature across finite/missing samples.
- Explicit absence of daily PoP.
- Fahrenheit conversion for current/hourly/daily apparent temperature.
- Missing apparent/PoP fields do not remove other forecast keys or abort output.
- Existing dew point, pressure, precipitation, condition, gust, and calendar aggregation remain
  unchanged.

### 9.4 Best-time algorithm tests

Use table-driven pure/coordinator tests plus Home Assistant entity tests for:

- reproduction of the old current-time fallback and warmest-hour bias before implementation;
- future-only selection at an exact hour and between hours;
- exclusion of past samples and next-local-day samples;
- month/year/leap-day and Helsinki DST boundaries;
- configured interval sampling;
- option-form rejection of every inverted min/max pair without persisting partial input;
- inclusive min/max feels-like, humidity, wind, and precipitation boundaries;
- hard rejection of non-accepted weather symbols;
- valid zero PoP/thunder/precipitation/wind values;
- missing/invalid required fields skipped without crashing;
- lower thunder probability winning;
- equal thunder risk then smaller apparent-temperature midpoint distance winning, including a
  summer case where the hottest hour loses;
- equal thermal distance then lower PoP, then lower amount, then earlier timestamp winning;
- exact symmetric thermal tie;
- healthy forecast with no suitable candidate producing translated available `no_suitable_time`
  with cleared attributes, never current time;
- disabled/failed/empty/unusable forecast producing unavailable state rather than the no-suitable
  token;
- later recovery;
- all old attributes retained and three new factor attributes correct;
- options update/reload changing the selected time without replacing the entity;
- two entries with different locations/options selecting independently.

### 9.5 Registry, lifecycle, and compatibility tests

- Load the realistic v0.6.2 two-entry registry fixture and a current 1.2.0 registry snapshot.
- Preserve all old entity IDs, unique IDs, customized IDs, disabled state, devices, and config
  entry ownership.
- Confirm new sensors receive distinct stable IDs without triggering legacy-ID rename logic.
- Unload/reload, failed setup/retry, options reload, reconfigure, and multiple entries.
- Forecast failure/recovery and partial new-field failure/recovery.
- Station, lightning, and sea-level independence.
- Recorder-facing state/attribute types remain JSON-serializable and timezone-aware where required.

### 9.6 Live and compatibility tests

- Reuse public Helsinki and Kilpisjärvi only.
- Extend existing production-boundary live calls; add no standalone request when one response can
  assert all fields.
- Assert finite sensible-range values for feels-like, dew point, pressure, cloud layers, PoP, and
  thunder probability for the first available future Europe/Helsinki local forecast date.
- Accept climatologically valid zero probabilities.
- Assert current/hourly Home Assistant apparent temperature and hourly PoP presentation.
- Keep the shared twelve-attempt counter, two-request semaphore, xdist auto workers, retries, and
  honest outage classification.
- Run stable compatibility as required; prerelease remains informational.

### 9.7 Coverage quality

- Keep the repository coverage threshold.
- Cover behavior at adapter, pure selection, coordinator, entity, and HA service levels in
  proportion to risk.
- Do not suppress, weaken, delete, or broaden an assertion to obtain green checks.
- Do not claim a command passed unless that exact invocation completed successfully.

---

## 10. CI and repository quality target

P04 does not redesign CI. It must preserve:

- rootless confined Podman for project-aware commands except hash-locked host Ruff;
- tar-streamed private tmpfs source and no checkout/venv/socket bind mounts;
- network-none default contours;
- purpose-limited online contours only where already authorized;
- automatic xdist with work stealing for every pytest path;
- serialized Make target graph;
- exact direct dependencies and generated hash locks;
- read-only PR workflow permissions and trusted release/dependency submission boundaries;
- current stable required compatibility and informational prerelease compatibility;
- version/changelog/release automation without manual publication.

No lock regeneration is expected. If implementation changes dependencies, stop and obtain an
owner-approved plan correction before continuing.

---

## 11. Session tracker

| Session | Objective | Prerequisite | Required report | Commit | Status |
|---|---|---|---|---|---|
| S00 | Verify repository/FMI/client/HA/comfort baseline and freeze exact model, rounding, identities, branch, and release | Owner-selected non-master branch | `plans/P04/BASELINE.md`; `plans/P04/S00.md` | `OWNER_TO_COMMIT` | DONE |
| S01 | Generalize the single-request adapter and add typed timestamp-aligned PoP/thunder supplements | S00 DONE | `plans/P04/S01.md` | `OWNER_TO_COMMIT` | DONE |
| S02 | Add eight sensors and standard Home Assistant weather apparent-temperature/hourly-PoP fields | S01 DONE | `plans/P04/S02.md` | `OWNER_TO_COMMIT` | DONE |
| S03 | Replace current/warmest fallback with the frozen deterministic Best-time candidate and ordering contract | S02 DONE | `plans/P04/S03.md` | `OWNER_TO_COMMIT` | DONE |
| S04 | Prove lifecycle, registry, multi-entry, missing-data, live, privacy, and locked-HA behavior | S03 DONE | `plans/P04/S04.md` | `OWNER_TO_COMMIT` | DONE |
| S05 | Finalize docs/translations/release and run complete release verification | S04 DONE | `plans/P04/S05.md` | `OWNER_TO_COMMIT` | DONE |

---

## 12. Standard session protocol

### 12.1 Start of session

1. Read `AGENTS.md`, this plan, baseline, prerequisite reports, and relevant current contracts.
2. Inspect branch, `git status`, current diff, and unexplained owner changes.
3. Confirm prerequisites are `DONE` and mark the session `IN_PROGRESS`.
4. Recheck any external/current API facts the session relies on.

### 12.2 During session

1. Add/confirm characterization evidence.
2. Implement only the session concern.
3. Correct plan discrepancies immediately.
4. Run focused tests after each coherent change.
5. Preserve unrelated work and avoid commits.

### 12.3 End of session

1. Run every required session gate.
2. Review the complete diff for scope, privacy, identity, stale data, and test quality.
3. Update requirements, decisions, and tracker only from actual evidence.
4. Write the report using section 14.
5. End at a green checkpoint with one concise owner commit suggestion without plan/session IDs.

---

## 13. Detailed session specifications

## Session S00 — Verified baseline and frozen contracts

### Objective

Turn planning claims into executable evidence and close all questions that affect source shape,
Home Assistant presentation, comfort ordering, compatibility, branch, or release.

### Required work

1. Record branch, commit, worktree, `.version`, manifest, dependency/reference versions, Podman
   health, test counts, and current release state.
2. Reproduce current Best-time warmest-hour and current-time fallback behavior offline.
3. Inspect installed `fmi-weather-client` source and pin consumed model/query/parser signatures.
4. Verify exact FMI parameter names, units, 0–100 ranges, preceding-hour PoP semantics, and product
   availability through official metadata.
5. Freeze the marked live assertions and public Helsinki/Kilpisjärvi coverage needed to prove the
   new production adapter in S01 without increasing requests; S00 must not add a test-only parser or
   modify the request before the production boundary exists.
6. Inspect locked Home Assistant source for current/forecast apparent temperature, PoP type,
   atmospheric-pressure sensor class, unit conversion, and forecast serialization.
7. Freeze the typed adapter envelope and integer PoP rounding policy.
8. Inventory the complete sensor key and unique-ID suffix set against registry fixtures, with one
   expected registry contract rather than feature-age categories.
9. Freeze exact English/Finnish names and icons.
10. Reconfirm the Best-time ordering and option semantic change with tests/examples covering
    winter, summer heat, rain chance, and thunder probability.
11. Record the evidence rejecting UTCI/WBGT/proprietary scores and confirm no newly available
    instantaneous radiation changes that boundary. If it does, correct this plan before work.
12. Record the owner-selected branch and release.
13. Write `BASELINE.md`, update decision rows, and write `S00.md`.

### Verification

- `make doctor`
- `make dev-build`
- `make reference-contracts`
- focused selected-client/Best-time characterization tests through supported Make/container paths
- `make test-fast`
- `make format-check`
- `make type-check`
- `make test-network-block`
- `make live` to preserve the pre-change live baseline under the existing budget
- `make version-check`
- `git diff --check`

### Exit criteria

- Every section 6.6 question except the production-adapter live proof explicitly assigned to S01
  is closed or the plan is corrected.
- Baseline distinguishes measured execution evidence from planning research.
- No user-visible partial feature is exposed.
- S00 report is complete and the next session has a stable typed source contract.

### Suggested owner commit

`Verify FMI forecast metrics and Home Assistant presentation contracts`

## Session S01 — Single-request supplemental probability adapter

### Objective

Add PoP and thunder-probability data to the existing bounded selected-client request without
changing entity behavior yet.

### Required work

1. Generalize the gust parameter/extraction boundary to include both probability fields exactly
   once.
2. Add the frozen immutable typed supplement/envelope.
3. Parse field names and values in one safe bounded XML document where practical; do not add an
   unbounded duplicate parse.
4. Normalize timestamp keys to aware UTC and atomically pair the base forecast with supplements.
5. Validate finite 0–100 values without clamping or zero substitution.
6. Return current sample supplements alongside current weather and future supplements alongside
   forecasts through a narrow adapter API.
7. Update the typed coordinator to store/clear the current and future supplements atomically with
   their owner data.
8. Preserve upstream model objects, gust precedence, executor behavior, timeouts, privacy filters,
   and failure classification.
9. Add all section 9.1 tests plus coordinator replacement/failure tests.
10. Extend the existing production-boundary live assertions for Helsinki and Kilpisjärvi and prove
    finite 0–100 probabilities without adding a request or raising the budget.
11. Update plan decisions and write `S01.md`.

### Verification

- focused adapter/parser/coordinator tests
- `make test-fast`
- `make format-check`
- `make lint`
- `make type-check`
- `make bandit`
- `make test-network-block`
- `make live`
- `git diff --check`

### Exit criteria

- R02 is `DONE`; R03 has adapter/coordinator evidence.
- Existing entities behave exactly as before because S02 has not exposed new values.
- One request and no new dependency are proven.
- Missing probability values cannot poison mandatory weather parsing or survive replacement.
- The actual production adapter exposes both probability fields at both public live points within
  the unchanged request budget.

### Suggested owner commit

`Parse FMI precipitation and thunder probabilities in the existing forecast request`

## Session S02 — New sensors and standard weather fields

### Objective

Expose the eight metrics as native Home Assistant sensors and enrich weather current/hourly/daily
data only through standard supported fields.

### Required work

1. Add eight sensor types/descriptions with frozen metadata and stable unique-ID suffixes.
2. Reuse the existing finite extraction path for client-model fields and add narrow probability
   lookup by the selected source timestamp.
3. Preserve configured-interval selection, valid zeros, per-field availability, and recovery.
4. Set weather current apparent temperature when finite.
5. Add hourly apparent temperature and integer PoP.
6. Add daily maximum apparent temperature and explicitly omit daily PoP.
7. Add source/English/Finnish translations in lockstep.
8. Extend fixtures/helpers with synthetic sanitized fields without capturing live/private XML.
9. Add section 9.2 and 9.3 tests, including unit conversion and partial-missing behavior.
10. Confirm the complete sensor identity set and forecast semantics remain compatible.
11. Update plan decisions and write `S02.md`.

### Verification

- focused sensor/weather/forecast/translation tests
- `make test-fast`
- `make format-check`
- `make lint`
- `make type-check`
- `make bandit`
- `make validate`
- `make test-network-block`
- `git diff --check`

### Exit criteria

- R01, R04, and R05 are `DONE` at focused/HA contract level.
- All new entities have correct values and metadata without disturbing old entities.
- Weather uses only native HA fields and daily PoP remains absent.
- No Best-time behavior changes until S03.

### Suggested owner commit

`Add FMI comfort, cloud, pressure, and probability sensors`

## Session S03 — Deterministic Best time of day

### Objective

Replace the misleading current-or-warmest heuristic with the frozen future-only, user-bounded,
transparent risk/comfort ordering while preserving the entity and its automation surface.

### Required work

1. Extract one pure, typed Best-time candidate/selection boundary if it materially improves
   testability; do not refactor unrelated coordinator code.
2. Clear cached Best-time fields before constructing candidates.
3. Use aware Home Assistant local time, current full local date, not-past samples, and the existing
   configured interval.
4. Apply complete finite validation, symbol allowlist, apparent-temperature range, and the existing
   humidity/wind/precipitation ranges.
5. Implement exactly the tuple in section 4.6 with documented midpoint and earliest tie behavior.
6. Never fall back to current weather or an out-of-range least-bad sample.
7. Implement the frozen selected/no-suitable/unavailable status contract and translated
   `no_suitable_time` token.
8. Preserve entity identity, `HH:MM`, and all old selected-candidate attributes; add the three
   transparent selection attributes.
9. Update option labels/descriptions to say feels-like/apparent temperature while preserving keys
   and values.
10. Add cross-field option validation for every min/max pair; keep old stored input loadable and do
   not silently rewrite it.
11. Add every section 9.4 regression at pure/coordinator and HA state levels.
12. Run options reload and multi-entry tests.
13. Update `TIME_AND_MISSING_DATA.md` only if the behavior is sufficiently proven in this session;
    S05 owns final documentation audit.
14. Update plan decisions and write `S03.md`.

### Verification

- focused Best-time/time/options/lifecycle tests
- `make test-fast`
- `make format-check`
- `make lint`
- `make type-check`
- `make bandit`
- `make test-network-block`
- `git diff --check`

### Exit criteria

- R06 and R07 are `DONE`; R08 has focused evidence.
- A summer regression proves a hotter but less comfortable candidate loses.
- Healthy no-candidate behavior is available `no_suitable_time` with cleared attributes, never
  current time; unavailable remains reserved for absent/unusable forecast data.
- Exact tie behavior is stable and documented.

### Suggested owner commit

`Make Best time of day use future apparent comfort and forecast risk`

## Session S04 — Recovery, live, and privacy proof

### Objective

Prove the combined feature under realistic Home Assistant lifecycle, registry history, independent
source failures, live FMI data, privacy, and the locked Home Assistant environment before release
work.

### Required work

1. Review the combined S01-S03 diff and reports for stale data, partial failures, identity drift,
   duplicate extraction, and hidden network work.
2. Complete section 9.5 registry/lifecycle/multi-entry/availability tests.
3. Exercise partial missing new fields separately from full current/forecast failure.
4. Prove lightning, sea level, and configured station remain independent.
5. Prove reload/options/reconfigure preserve every custom ID and keep the complete entity set
   idempotent.
6. Run permanent bounded live coverage at Helsinki and Kilpisjärvi, recording exact request counts
   and honest classifications.
7. Audit logs, diagnostics, state attributes, fixtures, and distribution for coordinate/raw-payload
   leakage.
8. Close R01/R03/R08-R10 only from complete evidence.
9. Update plan decisions and write `S04.md`.

### Verification

- focused registry/lifecycle/availability/privacy tests
- `make format-check`
- `make lint`
- `make type-check`
- `make bandit`
- `make syntax`
- `make shellcheck`
- `make test-fast`
- `make test-full`
- `make test-network-block`
- `make validate`
- `make live`
- `git diff --check`

### Exit criteria

- R01-R10 are `DONE` with report-backed evidence.
- No identity, source-isolation, privacy, request-budget, or stale-data regression remains.
- Live data proves the actual production request/presentation path at both public points, or an
  honest bounded upstream outage is recorded and retried only within policy.
- S05 can be documentation/release-only except for defects discovered by final gates.

### Suggested owner commit

`Prove forecast metric lifecycle, compatibility, and live FMI behavior`

## Session S05 — Documentation, release, and final verification

### Objective

Make the delivered contract explicit, synchronize the owner-selected release, and prove release
readiness with every required repository gate.

### Required work

1. Review the complete P04 baseline, decisions, reports, code, tests, generated state, and diff.
2. Update the user guide with all new sensors, units, layered-cloud overlap, mean-sea-level pressure,
   PoP/hour meaning, thunder forecast versus lightning observation, and apparent-temperature scope.
3. Document Best-time candidate limits, priority order, no-current fallback,
   `no_suitable_time` versus unavailable, attributes, option semantic clarification, and non-safety
   limitation.
4. Update every owning maintenance contract listed in section 5.6 where actual behavior changed.
5. Audit translations for source/English/Finnish structural and semantic parity.
6. Set `.version` and manifest to the owner-selected release and add one matching dated changelog
   section after published `1.2.0`.
7. Lead release notes with additive sensors/weather metrics. Explain the in-place Best-time behavior
   change without claiming a universal health score.
8. Run all final gates below. Inspect locks/snapshots even though no dependency change is expected.
9. Review `git status`, full diff, distribution contents, generated artifacts, and whitespace.
10. Mark R11-R12, sessions, and plan `DONE` only after every mandatory gate succeeds.
11. Write `S05.md` with remaining limitations and one concise owner commit suggestion.

### Verification

- `make doctor`
- `make dev-build`
- `make freeze-check`
- `make format-check`
- `make lint`
- `make type-check`
- `make bandit`
- `make syntax`
- `make shellcheck`
- `make test-fast`
- `make test-full`
- `make test-network-block`
- `make confinement-test`
- `make validate`
- `make version-check`
- `make live`
- `make audit`
- `make licenses`
- `make dependency-snapshot`
- `make check`
- `make ci`
- `git diff --check`
- final `git status --short`, full diff, dependency, privacy, and distribution review
- after every preceding gate passes and the candidate is unchanged: one
  `make compatibility-stable`
- last: one `make compatibility-prerelease` (informational result recorded accurately); reuse an
  already completed result for the exact candidate and never repeat an explicit no-newer-prerelease
  skip without evidence that the upstream channel changed

### Exit criteria

- R01-R12 and S00-S05 are `DONE`.
- Code, tests, docs, translations, release metadata, and user-visible behavior agree.
- Every required supported-environment gate passes; informational upstream results are classified
  rather than hidden.
- No unrelated feature, dependency, request, privacy leak, scientific overclaim, arbitrary comfort
  score, or stale plan placeholder remains.

### Suggested owner commit

`Release useful FMI forecast sensors and deterministic Best time selection`

---

## 14. Execution report template

Every report at `plans/P04/SXX.md` must use:

```markdown
<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# P04 Session SXX Report

## Metadata

- Date/time:
- Starting branch/commit:
- Ending commit: OWNER_TO_COMMIT
- Working tree at start:
- Suggested owner commit: `Describe completed behavior without plan/session identifiers`
- Status: DONE | IN_PROGRESS | BLOCKED

## Objective

One paragraph matching the owning session.

## Baseline and evidence

- Relevant code/API behavior verified before change.
- External references and access dates.
- Reproduction or characterization result.

## Changes made

- Behavioral and structural changes.
- Plan or contract corrections.

## Decisions

- Decision IDs added/updated.
- Alternatives rejected and evidence.

## Tests and checks run

| Command/check | Result | Evidence/notes |
|---|---|---|

Never mark PASS unless that exact command completed successfully.

## Files materially changed

- Paths and reasons, not a raw inventory.

## Requirement mapping

- RXX: status and evidence.

## Remaining risks or blockers

- Precise unresolved items, or `None within this session`.

## Instructions for the next session

- Preconditions, exact objective, and facts that must not be rediscovered.
```

---

## 15. Decision log

Update this table when execution evidence changes a decision.

| ID | Owner/session | Date | Decision | Rejected alternatives | Rationale/evidence | Status |
|---|---|---|---|---|---|---|
| D001 | Owner/P04 | 2026-08-20 | Stay on `fmi-weather-client==1.0.0` and use only FMI data available through the existing selected-client request boundary | Migrate to `fmiopendata`; add another provider/library | Owner explicitly selected the current library; all required P04 forecast values are available in the same FMI product or current client calculation | ACCEPTED |
| D002 | Owner/P04 | 2026-08-20 | Add feels-like, dew-point, pressure, low/middle/high cloud, PoP, and thunder-probability sensors while retaining values already present on weather | Keep values only as weather attributes; replace old entities | Dedicated numeric sensors are the HA-native automation/history surface and are additive | ACCEPTED |
| D003 | Owner/P04 | 2026-08-20 | Preserve and improve Best time of day rather than removing it | Delete/deprecate the entity; keep the current heuristic | Users may depend on its identity/state; current warmest/current fallback is known to be misleading | ACCEPTED |
| D004 | Plan/P04 | 2026-08-20 | Use the standard HA apparent-temperature current/hourly/daily fields and hourly precipitation-probability field | Ad hoc weather attributes; sensor-only apparent temperature | `make reference-contracts` proved Home Assistant 2026.8.1 exposes the exact native apparent-temperature key, integer PoP key/type, and atmospheric-pressure sensor class | ACCEPTED |
| D005 | Plan/P04 | 2026-08-20 | Keep upstream `WeatherData` intact; return `CurrentWeatherResult` and `ForecastResult` with immutable `ForecastProbabilities` supplements and a read-only UTC timestamp mapping | Abuse unused model fields; monkey-patch dependency; second request; global sidecar | The locked upstream model is a fixed NamedTuple without probability fields; explicit typed results preserve atomic ownership and prevent hidden timestamp side channels | ACCEPTED |
| D006 | Plan/P04 | 2026-08-20 | Do not implement UTCI/WBGT or claim full-sun thermal stress | Assume mean radiant temperature equals air temperature; infer irradiance from cloud cover | Recognized indices require radiation/MRT not reliably present in the selected product | ACCEPTED |
| D007 | Plan/P04 | 2026-08-20 | Do not expose a weighted numeric comfort score or copy a proprietary activity index | Arbitrary 0–100 weights; reverse-engineered commercial formula | No open universal best-hour formula exists; activities and personal limits differ | ACCEPTED |
| D008 | Plan/P04 | 2026-08-20 | Best-time candidates are not-past samples on the current HA local date from the configured interval; current weather is never a fallback | Initialize from current; include past hours; scan future days under a same-day name | S00 regressions reproduce both current-time fallback and warmest-hour selection; the future-only rule fixes the defect while preserving the same-day product boundary | ACCEPTED |
| D009 | Plan/P04 | 2026-08-20 | Interpret stored Best-time temperature bounds as feels-like temperature while preserving keys/values and documenting the semantic change | Continue filtering air temperature; add duplicate options; migrate/reset preferences | Existing stored values remain valid; applying them to FMI-derived apparent temperature matches the retained entity purpose without a config or registry migration | ACCEPTED |
| D010 | Plan/P04 | 2026-08-20 | Rank eligible hours by thunder probability, apparent-temperature midpoint distance, PoP, precipitation amount, then earliest timestamp | Max temperature; weighted sum; pressure/cloud scoring; least-bad out-of-range fallback | The ordered tuple is deterministic across winter, summer heat, rain, thunder, and exact ties without hidden weights or double-counting humidity/wind | ACCEPTED |
| D011 | Plan/P04 | 2026-08-20 | Expose available translated `no_suitable_time` when a healthy forecast has no suitable remaining current-day hour; use unavailable only for disabled/failed/empty/unusable forecast data; clear selected attributes in both cases | Emit current time; ignore limits; retain previous selection; treat every empty candidate set as source failure | Separates a valid calculation outcome from source health, preserves entity usefulness, and never invents a best hour | ACCEPTED |
| D012 | Plan/P04 | 2026-08-20 | Expose hourly PoP but omit daily PoP | Sum/mean/max hourly probabilities; assume independent hours | FMI supplies preceding-hour event probability; daily union probability requires unavailable dependence information | ACCEPTED |
| D013 | Plan/P04 | 2026-08-20 | Add no dependency/request and keep the live suite budget unchanged | New comfort package; separate probability query; raised live ceiling | Installed model fields and official product metadata show the required values fit the existing request; the pre-change live suite remains 7/12 attempts | ACCEPTED |
| D014 | Owner/S00 | 2026-08-20 | Execute on `feature/useful-forecast-sensors` and target release `1.3.0` | Execute on master; reuse published 1.2.0 | The owner authorized creation of an appropriately named branch and execution; `1.3.0` is the plan's additive-feature recommendation | ACCEPTED |
| D015 | Owner/S00 | 2026-08-20 | Run every project/container/package operation only through a supported Make target and add confined tooling when a target is missing | Direct Podman/image invocation for one-off inspection | Owner requirement; the Make boundary preserves the repository's confinement, transport, and network policy consistently | ACCEPTED |
| D016 | Plan/S00 | 2026-08-20 | Perform live probability proof in S01 through the completed production adapter, while S00 freezes assertions and preserves the existing live baseline | A duplicate test-only XML parser and request monkeypatch in S00 | Avoids temporary parallel parsing logic and proves the actual runtime boundary without another request | ACCEPTED |
| D017 | Plan/S00 | 2026-08-20 | Convert validated decimal hourly PoP with `int(round(value))` | Truncation; clamp; string value; invented fractional HA schema | Locked Home Assistant declares the forecast field as `int | None`; standard half-to-even rounding is explicit, deterministic, range-preserving, and consistent with existing HA percentage handling | ACCEPTED |
| D018 | Plan/S00 | 2026-08-20 | Freeze the eight description keys, English/Finnish names, legacy-style unique-ID suffix inputs, metadata, and icons in section 4.3 | Reuse unrelated existing suffixes; expose generic untyped sensors | Repository/fixture inventory found no collisions; the metadata matches Home Assistant's locked device-class/unit contracts | ACCEPTED |
| D019 | Plan/S01 | 2026-08-20 | Retain the single current/forecast request cadence and validate both probabilities through the production adapter at Helsinki and Kilpisjärvi | Add a second query; trust metadata without runtime proof; increase the live budget | `make live` passed all four probes with the unchanged 7/12 attempts, including aligned future hourly supplements at both public forecast points | ACCEPTED |
| D020 | Plan/S02 | 2026-08-20 | Expose every requested metric through one integrated sensor description/update path and use only standard Home Assistant weather fields | Separate legacy/new runtime paths; ad hoc weather attributes; daily probability aggregation | Unified entity setup preserves the existing source-time policy and identity mechanism; HA state/service tests prove native unit conversion, standard apparent temperature/hourly PoP, and daily PoP omission | ACCEPTED |
| D021 | Plan/S03 | 2026-08-20 | Keep candidate parsing, limits, outcome classification, and ordering as one cohesive pure `best_time.py` domain boundary with one typed result owned by the coordinator | Grow the coordinator with parallel scalar fields; split legacy/new algorithms; suppress structural lint findings | The first implementation exceeded module/local/boolean/public-surface quality limits; the cohesive boundary removed those findings, avoids duplicate implementations, and makes the frozen algorithm directly testable | ACCEPTED |
| D022 | Plan/S03 | 2026-08-20 | Use `no_suitable_time` only for a healthy exhausted/rejected current day and unavailable for empty, timestamp-unusable, or entirely incomplete remaining data; reject submitted inverted limits without rewriting stored values | Current-time fallback; least-bad candidate; silently swap/reset limits; treat every empty result as outage | HA lifecycle and table-driven tests prove all three states, stale clearing, later recovery, and explicit user correction of historical inverted settings | ACCEPTED |
| D023 | Plan/S04 | 2026-08-20 | Treat the registry and runtime entities as one complete contract, preserving customization/disabled state while adding missing descriptions idempotently | Partition acceptance assertions into old/new entity groups; recreate records; infer customization from suffixes | Current and v0.6.2 snapshots, reload, simultaneous-entry, partial-failure, privacy, live, and moving-stable tests pass without a second runtime or migration path | ACCEPTED |
| D024 | Plan/S05 | 2026-08-20 | Make permanent live hourly assertions target the first available future Europe/Helsinki local forecast date while leaving Best-time strictly current-day | Require a remaining current-day hour at every wall-clock time; skip hourly validation late at night; alter Best-time scope | A final run after 23:00 Helsinki proved the next FMI hourly sample begins at local midnight, so no remaining current-day sample can exist; the corrected rule stays strict over one represented date and is executable around the clock without another request | ACCEPTED |
| D025 | Owner/S05 | 2026-08-20 | Run moving stable and prerelease compatibility only once, after every cheaper final gate passes, and reuse evidence for an unchanged candidate | Run at intermediate sessions; repeat after documentation/report edits; rerun an unchanged explicit prerelease skip | Moving compatibility recreates the full Home Assistant graph in disposable environments; the former S04 and S05 gate lists duplicated this expensive proof without increasing confidence | ACCEPTED |

---

## 16. Final definition of done

### User-visible metrics

- Eight new dedicated sensors exist with correct values, units, metadata, names, translations,
  availability, history-friendly state, and stable identities.
- Existing pressure/dew-point weather attributes remain and their new sensor counterparts agree at
  the same source timestamp.
- Cloud layers remain independent percentages and are never summed.
- PoP and thunder probability are clearly distinguished from amount and observed lightning.
- Valid zero values remain available.

### Weather correctness

- Current forecast-backed weather exposes apparent temperature when finite.
- Configured-station weather exposes it only when the selected client supplies it.
- Hourly forecast exposes apparent temperature and PoP in native HA fields.
- Daily forecast exposes maximum apparent temperature and no fabricated PoP.
- Unit conversion and missing fields behave through actual Home Assistant state/service APIs.

### Best-time correctness

- The entity, unique ID, custom entity ID, device, state shape, options, and old attributes remain.
- Candidate times are aware, current-local-date, not in the past, and use the configured interval.
- Current weather is never an unconditional default.
- Apparent temperature, not maximum air temperature, drives thermal preference.
- The exact thunder/thermal/PoP/amount/time tuple and inclusive gates are tested at boundaries.
- A healthy forecast with no eligible candidate is available as translated `no_suitable_time` with
  cleared selection attributes; absent/unusable forecast data is unavailable; both recover on later
  valid data.
- No numeric scientific/medical comfort claim is made.

### Source, availability, and privacy

- All data comes from FMI through the selected current library boundary or its documented local
  feels-like calculation.
- Current and forecast calls retain one request each; no provider/dependency/budget increase exists.
- Probability supplements cannot drift across timestamps or remain stale after failure/replacement.
- Partial new-field failure does not disable unrelated weather, sensor, station, lightning, or sea
  level state.
- Logs, diagnostics, fixtures, states, and artifacts contain no private coordinates or raw payload.

### Compatibility and quality

- Every existing entity/config/device/registry identity and customized ID survives upgrade,
  reload, reconfigure, options changes, and multiple entries.
- No config-entry migration or Recorder rewrite is introduced without proven need.
- Offline/full/live/HA/validation/lint/type/security/network-block/confinement/compatibility/audit/
  license/dependency/distribution/release gates pass.
- Coverage stays above the repository gate without suppression or weakened assertions.
- The diff contains no unrelated change.

### Documentation and release

- User guide and owning maintenance contracts describe exact semantics, units, limitations,
  selection order, and unavailable behavior.
- Source, English, and Finnish translations match.
- Owner-selected version, manifest, and dated changelog section are synchronized after published
  `1.2.0`.
- `plans/P04/` contains its plan, verified baseline, and S00-S05 reports.
- No commit, push, tag, release, or issue mutation was performed by Codex.

---

## 17. Authoritative references to recheck

Record access dates in the executing baseline/report.

### Repository and selected client

- `AGENTS.md`
- `custom_components/fmi/fmi_client.py`
- `custom_components/fmi/__init__.py`
- `custom_components/fmi/sensor.py`
- `custom_components/fmi/weather.py`
- `docs/maintenance/SENSORS.md`
- `docs/maintenance/FORECAST_SEMANTICS.md`
- `docs/maintenance/TIME_AND_MISSING_DATA.md`
- [`fmi-weather-client` 1.0.0 package](https://pypi.org/project/fmi-weather-client/1.0.0/)
- [`fmi-weather-client` 1.0.0 models](https://codeberg.org/saaste/fmi-weather-client/src/tag/1.0.0/fmi_weather_client/models.py)
- [`fmi-weather-client` forecast parser](https://codeberg.org/saaste/fmi-weather-client/src/tag/1.0.0/fmi_weather_client/parsers/forecast.py)

### FMI

- [FMI WFS service manual](https://en.ilmatieteenlaitos.fi/open-data-manual-fmi-wfs-services)
- [FMI WFS examples and parameter guidance](https://en.ilmatieteenlaitos.fi/open-data-manual-wfs-examples-and-guidelines)
- [FMI current producer/parameter metadata](https://opendata.fmi.fi/info?what=qengine)
- [FMI online weather-service interpretation, including preceding-hour PoP and 0.1 mm threshold](https://www.ilmatieteenlaitos.fi/saapalvelut-verkossa)
- [FMI precipitation probability guidance](https://www.ilmatieteenlaitos.fi/sade)
- [FMI feels-like explanation](https://www.ilmatieteenlaitos.fi/ajankohtaista/6100469)
- [FMI cloud-level guide](https://www.ilmatieteenlaitos.fi/pilvikuvasto)

### Home Assistant

- [Weather entity contract](https://developers.home-assistant.io/docs/core/entity/weather/)
- [Current weather component source](https://github.com/home-assistant/core/blob/dev/homeassistant/components/weather/__init__.py)
- [Sensor entity contract](https://developers.home-assistant.io/docs/core/entity/sensor/)
- [Entity naming/lifecycle](https://developers.home-assistant.io/docs/core/entity/)
- [Entity registry](https://developers.home-assistant.io/docs/entity_registry_index/)
- [Entity unavailable rule](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/entity-unavailable/)
- [Async blocking operations](https://developers.home-assistant.io/docs/asyncio_blocking_operations/)
- Exact locked Home Assistant 2026.8.x toolbox source is execution evidence and takes precedence over
  moving `dev` documentation.

### Thermal comfort and health boundary

- [ECMWF/Copernicus UTCI user guide](https://confluence.ecmwf.int/spaces/CKB/pages/340759409/UTCI%2B-%2BUser%2BGuide)
- [UTCI calculator and required inputs](https://utci.org/utci_calc.php)
- [ECMWF mean-radiant-temperature technical memorandum](https://www.ecmwf.int/en/elibrary/81295-calculating-cosine-solar-zenith-angle-thermal-comfort-indices)
- [WHO/WMO heat-health warning-system guidance](https://www.who.int/docs/default-source/climate-change/heat-waves-and-health---guidance-on-warning-system-development.pdf)
- [WHO heatwave practical guidance](https://www.who.int/news-room/questions-and-answers/item/heatwaves-how-to-stay-cool)
- [NWS Heat Index and WBGT guidance](https://www.weather.gov/lch/wbgt)
- [NWS Wind Chill](https://www.weather.gov/ddc/windchillddc)
- [Met Office feels-like explanation](https://www.metoffice.gov.uk/blog/2012/what-is-feels-like-temperature)
- [AccuWeather activity index catalog](https://developer.accuweather.com/documentation/indices)

---

## 18. Owner review checkpoints

1. **Before S00:** select a non-`master` execution branch.
2. **S00:** approve the exact sensor names/IDs, supplement model, PoP rounding, feels-like option
   wording, frozen Best-time order, and release version.
3. **S01:** inspect proof that parameters are added to one bounded request and cannot become stale.
4. **S02:** inspect all new entities, Home Assistant weather state/forecast output, units,
   translations, and absence of daily PoP.
5. **S03:** inspect summer/winter/rain/thunder examples, no-current fallback,
   `no_suitable_time` versus unavailable behavior, preserved attributes/options, and explicit
   algorithm limitation.
6. **S04:** inspect registry/custom-ID/multi-entry/recovery/live/privacy evidence.
7. **S05:** approve user guide, maintenance contracts, changelog, version, final matrix, and
   remaining risks.

Routine execution must not re-ask decisions already accepted in D001-D003, D006-D007, and D012.
Stop only when S00 disproves the data/HA contract, owner review changes the product ordering, or a
new choice would materially affect compatibility, privacy, dependencies, network load, or release
scope.
