<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# P04 Verified Execution Baseline

## Metadata

- Verified: 2026-08-20T19:01:27Z
- Branch: `feature/useful-forecast-sensors`
- Starting commit: `4fd9861e3c752c3efa33c2227fc41ac4b3e93f08`
- Starting release: `.version` and manifest `1.2.0`
- Planned release: `1.3.0`; release files remain unchanged until S05
- Locked reference: Home Assistant `2026.8.1`, Python `3.14`,
  `fmi-weather-client==1.0.0`
- Worktree before P04 execution: only the untracked P04 plan; no unrelated owner changes

## Repository and tooling evidence

- `make doctor` verified Podman `5.7.0`, rootless operation, and the content-addressed toolbox and
  resolver images. Podman emitted a host `pasta --version` warning, but the supported doctor target
  completed successfully and confirmed rootless operation.
- `make dev-build` completed successfully without changing dependency locks.
- The owner required agents to use only supported Make targets for all project, package, and
  container operations. `AGENTS.md`, `PLAN.md`, and `DEVELOPMENT.md` now state this explicitly.
- S00 added the offline confined `make reference-contracts` target because package inspection had
  no supported Make surface. It performs no request and prints no coordinates or payload.
- The initial full offline suite passed before feature implementation. After adding the two
  Best-time characterization regressions, `make test-fast` reported `394 passed`.
- The unmodified live suite reported `4 passed` and `7/12` FMI request attempts.

## Selected client and source contract

`make reference-contracts` proved the following installed-package facts:

- `WeatherData` contains `feels_like`, `dew_point`, `pressure`, `cloud_low_cover`,
  `cloud_mid_cover`, and `cloud_high_cover`.
- Its fixed NamedTuple has no precipitation- or thunder-probability field.
- The selected forecast request already carries all six direct/client-derived fields plus the
  other existing weather values, but omits `PoP` and `ProbabilityThunderstorm`.
- Current integration code adds `HourlyMaximumGust` to that one parameter list and parses the same
  bounded XML by field name and aware UTC timestamp. This is the retained extension boundary.
- The selected request contains only accumulated radiation fields. The client feels-like formula
  looks for instantaneous `RadiationGlobal`, so current feels-like output is based on temperature,
  sustained wind, and humidity without an instantaneous radiation correction.

Official FMI sources accessed 2026-08-20 confirm:

- current `pal_skandinavia` producer metadata lists `Pressure`, `DewPoint`, `LowCloudCover`,
  `MediumCloudCover`, `HighCloudCover`, `PoP`, `ProbabilityThunderstorm`, `HourlyMaximumGust`, and
  `RadiationGlobal`;
- the metadata describes `Pressure` as mean-sea-level pressure;
- FMI's weather-service guide defines PoP as the probability of at least 0.1 mm during the hour
  preceding the forecast timestamp.

Authoritative URLs:

- <https://opendata.fmi.fi/info?param=Pressure&what=qengine>
- <https://www.ilmatieteenlaitos.fi/saapalvelut-verkossa>
- <https://en.ilmatieteenlaitos.fi/open-data-manual-wfs-examples-and-guidelines>

S01 owns live range/completeness proof for the new values through the completed production adapter.
This corrects the original plan ordering: a test-only duplicate request/parser is not introduced in
S00 merely to precede the production boundary.

## Home Assistant contract

The locked `2026.8.1` package and official developer contract accessed 2026-08-20 prove:

- current weather supports `native_apparent_temperature`;
- forecast items support `native_apparent_temperature` and integer
  `precipitation_probability`;
- `SensorDeviceClass.ATMOSPHERIC_PRESSURE` has value `atmospheric_pressure`;
- apparent temperature uses the weather entity's native temperature unit and Home Assistant's
  standard conversion path;
- Home Assistant does not coerce a fractional PoP to integer for an integration.

P04 therefore validates finite 0–100 source probabilities and uses `int(round(value))`. Python's
half-to-even behavior is frozen explicitly: `12.5 -> 12`, `13.5 -> 14`. Daily PoP remains absent.

Authoritative URL: <https://developers.home-assistant.io/docs/core/entity/weather/>.

## Frozen adapter model

S01 must implement these immutable integration-owned boundaries:

- `ForecastProbabilities(precipitation, thunderstorm)`;
- `CurrentWeatherResult(weather, probabilities)`;
- `ForecastResult(forecast, probabilities_by_time)` with a `MappingProxyType` UTC timestamp map.

Observation helpers retain the upstream `Weather` model. The coordinator stores and clears each
supplement atomically with its current/forecast owner. There is no mutable global map, hidden parser
side channel, second request, dependency change, or upstream model mutation.

## Sensor identity and metadata inventory

Repository code, published plan history, and registry fixtures contain none of the eight new keys or
suffix inputs. Existing unique IDs are therefore unaffected. New suffixes follow the current
`legacy_name.replace(" ", "_")` construction and remain scoped by the existing entry identity and
configured name.

| Key | English / Finnish | Metadata | Icon |
|---|---|---|---|
| `feels_like` | Feels like / Tuntuu kuin | temperature, °C, measurement | `mdi:thermometer` |
| `dew_point` | Dew point / Kastepiste | temperature, °C, measurement | `mdi:thermometer-water` |
| `atmospheric_pressure` | Atmospheric pressure / Ilmanpaine | atmospheric pressure, hPa, measurement | `mdi:gauge` |
| `low_cloud_cover` | Low cloud cover / Alapilvisyys | %, measurement | `mdi:weather-cloudy` |
| `medium_cloud_cover` | Medium cloud cover / Keskipilvisyys | %, measurement | `mdi:weather-cloudy` |
| `high_cloud_cover` | High cloud cover / Yläpilvisyys | %, measurement | `mdi:weather-cloudy` |
| `precipitation_probability` | Precipitation probability / Sateen todennäköisyys | %, measurement | `mdi:weather-rainy` |
| `thunderstorm_probability` | Thunderstorm probability / Ukkosen todennäköisyys | %, measurement | `mdi:weather-lightning` |

All new sensors belong only to the existing main location device. A current `1.2.0` registry
snapshot will be added with the combined S04 compatibility proof; the existing v0.6.2 two-entry
fixture remains the historical migration acceptance source.

## Best-time reproduction and frozen behavior

Two deterministic offline regressions reproduce the current defects:

- among otherwise eligible hours, the current algorithm selects the highest air temperature;
- when no forecast hour qualifies, it retains current weather/time while reporting no available
  forecast candidate.

The replacement contract remains the plan's lexicographic ordering of thunder probability,
distance from the configured feels-like midpoint, PoP, precipitation amount, and timestamp.
Existing option keys/values remain valid and are not migrated. Their labels will state that the
temperature bounds apply to apparent temperature. A healthy evaluated forecast with no qualifying
hour produces the available `no_suitable_time` token; absent or unusable forecast data remains
unavailable.

UTCI and WBGT remain excluded because the selected runtime request and client calculation do not
provide the complete mean-radiant-temperature/radiation inputs those indices require. No
proprietary or arbitrary weighted activity score is introduced.

## S00 verification snapshot

| Command | Result |
|---|---|
| `make doctor` | PASS; rootless Podman and images identified |
| `make dev-build` | PASS |
| `make reference-contracts` | PASS; locked contracts printed offline |
| `make test-fast` | PASS; 394 tests |
| `make format-check` | PASS; 50 files formatted after one supported `make format` correction |
| `make lint` | PASS; Ruff clean, Pylint 10.00/10 |
| `make type-check` | PASS; 42 source files |
| `make test-network-block` | PASS; 1 test |
| `make live` | PASS; 4 tests, 7/12 attempts |
| `make version-check` | PASS; `1.2.0` |
