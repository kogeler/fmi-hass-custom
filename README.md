<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# fmi-hass-custom

`fmi-hass-custom` is a custom Home Assistant integration maintained at
[github.com/kogeler/fmi-hass-custom](https://github.com/kogeler/fmi-hass-custom). It uses
[Finnish Meteorological Institute (FMI) Open Data](https://en.ilmatieteenlaitos.fi/open-data)
to provide current conditions, hourly and daily forecasts, weather sensors, optional station
observations, lightning data, and sea-level forecasts for a configured location.

Check the [latest published GitHub Release](https://github.com/kogeler/fmi-hass-custom/releases/latest)
for the current integration version and its release notes. The minimum Home Assistant version is
declared in `hacs.json` for each release. Moving compatibility checks exercise the current stable
and prerelease channels as early warnings, but do not create a blanket support promise for future
releases. This fork is intended for owner testing as a HACS custom repository or a manual custom
integration, not as an official Home Assistant Core integration.

## Main Limitations

- Data depends on FMI and network availability. Forecast/current data refresh every 30 minutes;
  configured station observations refresh every 10 minutes.
- The committed reference graph and the moving current-stable graph are continuously checked. The
  installation floor remains the value in `hacs.json` until a real integration incompatibility
  requires raising it.
- Changing Home Assistant's Home zone does not move an entry automatically. Use the integration's
  **Reconfigure** action to change coordinates.
- Lightning is opt-in and its address enrichment uses the public Nominatim service. This is
  accepted only for small private deployments until the tracked provider limitation is resolved.
- Station observations require a valid FMI station ID. Sea-level and lightning sensors can be
  unavailable where FMI returns no applicable data or an optional external source fails.

## Documentation

### Users

- [Installation, configuration, upgrades, dashboards, and troubleshooting](docs/USER_GUIDE.md)
- [Current release and release notes](https://github.com/kogeler/fmi-hass-custom/releases/latest)
- [Release notes](CHANGELOG.md)
- [Known limitations and follow-up work](TODO.md)

### Maintainers

- [Home Assistant release maintenance](docs/maintenance/HA_RELEASE_MAINTENANCE.md)
- [Development environment and commands](docs/maintenance/DEVELOPMENT.md)
- [CI and release gates](docs/maintenance/CI.md)
- [HACS repository and release model](docs/maintenance/HACS_RELEASES.md)
- [Forecast semantics](docs/maintenance/FORECAST_SEMANTICS.md)
- [Migration guarantees](docs/maintenance/MIGRATIONS.md)
- [Compatibility, security, and privacy contract](docs/maintenance/COMPATIBILITY_SECURITY.md)
- [Runtime architecture and invariants](docs/maintenance/RUNTIME.md)
- [License](LICENSE)

## Maintainer

[@kogeler](https://github.com/kogeler) maintains this fork. Report integration problems in the
[canonical repository issue tracker](https://github.com/kogeler/fmi-hass-custom/issues).
