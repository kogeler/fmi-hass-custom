# Changelog

All notable changes to this project are documented in this file.

## Unreleased

### Fixed

- Fixed issue #117 by falling back to place observations during forecast-current outages, keeping configured station observations independent, clearing stale forecast/current data, and recovering automatically on later successful refreshes.

### Added

- Added a reproducible rootless Podman development and test environment targeting Home Assistant 2026.7.4 on Python 3.14.2.
- Added deterministic offline FMI fixtures, dependency contract tests, Home Assistant setup coverage, entity characterization tests, and explicit regression cases for the known maintenance issues.
- Added Ruff formatting/linting, coverage, type checking, network-blocking tests, hassfest/HACS validation, and pinned GitHub Actions checks.
- Added a verified maintenance baseline, dependency/license inventory, session handoffs, and repository guidance for future maintenance work.

### Changed

- Moved the integration to the standard `custom_components/fmi/` layout required by current Home Assistant validation.
- Upgraded `fmi-weather-client` from 0.7.0 to 1.0.0 and `geopy` to 2.5.0; added an exact `python-dateutil` runtime requirement.
- Replaced `async-timeout` with the Python standard-library timeout and removed redundant direct dependencies already supplied by Home Assistant or the FMI client.
- Replaced flake8 completely with Ruff and upgraded existing CI action references to reviewed immutable commits.
- Split reviewed direct dependencies from the complete 173-package `pip freeze` lock generated in a clean container.

### Security

- Upgraded the container and CI installer to pip 26.2 and added vulnerability/license audit commands.
- Documented a temporary owner-approved exception for Pillow and PyJWT versions pinned by Home Assistant 2026.7.4. The required follow-up is tracked in `TODO.md`.
