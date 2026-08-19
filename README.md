<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# fmi-hass-custom

`fmi-hass-custom` is a maintained community custom integration for Home Assistant. It is developed
at [github.com/kogeler/fmi-hass-custom](https://github.com/kogeler/fmi-hass-custom) and uses
[Finnish Meteorological Institute (FMI) Open Data](https://en.ilmatieteenlaitos.fi/open-data)
to provide current conditions, hourly and daily forecasts, weather sensors, optional station
observations, lightning data, and sea-level forecasts for a configured location.

Check the [latest published GitHub Release](https://github.com/kogeler/fmi-hass-custom/releases/latest)
for the current integration version and its release notes. The minimum Home Assistant version is
declared in `hacs.json` for each release. Moving compatibility checks exercise the current stable
and prerelease channels as early warnings, but do not create a blanket support promise for future
releases. Install it through HACS as a custom repository or copy the released integration manually.
It is not bundled with Home Assistant Core and does not claim an official Core quality tier.

## Main Limitations

- Data depends on FMI and network availability. Forecast/current data refresh every 30 minutes;
  configured station observations refresh every 10 minutes.
- The supported product geography is Finland. An FMI place search result outside Finland does not
  expand that boundary, and optional station or sea-level products can have narrower local
  coverage.
- The committed reference graph and the moving current-stable graph are continuously checked. The
  installation floor remains the value in `hacs.json` until a real integration incompatibility
  requires raising it.
- Changing Home Assistant's Home zone does not move an entry automatically. Use the integration's
  **Reconfigure** action to choose a new map point or search FMI by place name and confirm the
  result on the map.
- Lightning is opt-in. Its state reports locally calculated direction and distance from that FMI
  entry's configured point to a recent strike group; it does not predict storm movement or safety.
- Station observations require a valid FMI station ID. Sea-level and lightning sensors can be
  unavailable when an optional external source fails. A successful lightning response with no
  qualifying strikes remains available and says so explicitly.

## Documentation

### Users

- [Installation, configuration, upgrades, dashboards, and troubleshooting](docs/USER_GUIDE.md)
- [Current release and release notes](https://github.com/kogeler/fmi-hass-custom/releases/latest)
- [Release notes](CHANGELOG.md)
- [Known limitations and follow-up work](TODO.md)

### Maintainers

- [Development environment and commands](docs/maintenance/DEVELOPMENT.md)
- [Dependency ownership and review](docs/maintenance/DEPENDENCIES.md)
- [CI and release gates](docs/maintenance/CI.md)
- [Home Assistant release maintenance](docs/maintenance/HA_RELEASE_MAINTENANCE.md)
- [HACS repository and release model](docs/maintenance/HACS_RELEASES.md)
- [Runtime architecture and invariants](docs/maintenance/RUNTIME.md)
- [Source availability](docs/maintenance/AVAILABILITY.md)
- [Optional lightning and sea-level sources](docs/maintenance/OPTIONAL_SOURCES.md)
- [Live FMI tests](docs/maintenance/LIVE_TESTS.md)
- [Forecast semantics](docs/maintenance/FORECAST_SEMANTICS.md)
- [Time and missing-data policy](docs/maintenance/TIME_AND_MISSING_DATA.md)
- [Sensor and gust contract](docs/maintenance/SENSORS.md)
- [Migration guarantees](docs/maintenance/MIGRATIONS.md)
- [Location reconfiguration and identity](docs/maintenance/RECONFIGURATION.md)
- [Compatibility, security, and privacy contract](docs/maintenance/COMPATIBILITY_SECURITY.md)
- [License](LICENSE)

## Maintainer

[@kogeler](https://github.com/kogeler) maintains this fork. Report integration problems in the
[canonical repository issue tracker](https://github.com/kogeler/fmi-hass-custom/issues).

## Project History

This repository continues the work originally published by
[Anand Radhakrishnan](https://github.com/anand-p-r/fmi-hass-custom), retains its contributor
history, and preserves the original MIT attribution. Current maintenance and support belong to
this repository; the upstream project is not responsible for this fork.
