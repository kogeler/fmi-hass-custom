<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Changelog

All notable changes to this project are documented in this file.

## 1.0.0 - 2026-08-01

### Fixed

- Preserved observations during forecast-current outages by falling back to place observations, keeping configured station observations independent, clearing stale forecast/current data, and recovering automatically on later successful refreshes.
- Corrected daily forecasts with timezone-aware aggregation: hourly precipitation is summed, temperatures use daily highs/lows, and condition, wind, pressure, humidity, cloud, and dew-point values follow documented deterministic policies.
- Restored forecast wind gusts by requesting FMI's available hourly maximum gust while preserving observation gusts, valid zero values, and missing-data availability.
- Grouped fresh-entry sensors under location devices and generated location-aware entity IDs; exact legacy defaults migrate conservatively without changing customized IDs or overwriting collisions.
- Added a validated location reconfigure flow that reloads the moved entry while preserving config, device, and entity identity, including customized entity IDs.
- Prevented polar-day/night crashes with a deterministic daytime fallback for incomplete sun events.
- Fixed best-time selection across month/year boundaries and made forecast output reject malformed timestamps, unknown symbols, missing fields, and non-finite values without crashing.
- Kept optional lightning bounding boxes inside valid WGS84 limits at the geographic poles and across the antimeridian.
- Corrected weather entity naming under current Home Assistant semantics so fresh daily and observation entities no longer duplicate their device names or generated entity IDs, while retaining their existing unique IDs.
- Kept transport and malformed-response failures inside their individual FMI source boundaries, preserving place fallback and current weather when only forecast parsing fails, and removed the integration's global logging configuration side effect.

### Added

- Added a translated lightning maximum-age option with a backward-compatible 24-hour default and exact inclusive age filtering.
- Added a reproducible rootless Podman development and test environment targeting Home Assistant 2026.7.4 on Python 3.14.2.
- Added deterministic offline FMI fixtures, dependency contract tests, full Home Assistant config-flow/lifecycle and public-entity coverage, realistic v0.6.2 registry migration tests, entity characterization tests, and explicit regression cases for the known maintenance issues.
- Added bounded live FMI dependency and Home Assistant probes for southern/northern forecasts, station observations, dashboard-facing entity/forecast output, and daily precipitation semantics.
- Added Ruff formatting/linting, coverage, type checking, network-blocking tests, hassfest/HACS validation, and pinned GitHub Actions checks.
- Added a verified maintenance baseline, dependency/license inventory, session handoffs, and repository guidance for future maintenance work.
- Added privacy-safe Home Assistant diagnostics with configured coordinates and legacy coordinate-derived identities redacted.
- Added production pull-request, dependency, CodeQL, event/manual current stable and prerelease compatibility, and release workflows with a mandatory version increase, 95% coverage gate, and required bounded live FMI probes after offline tests.
- Added automatic PR-body synchronization from the source branch's latest changelog section while preserving manually written PR context.
- Added a local Home Assistant brand icon and clean-distribution smoke tests for the exact HACS/manual installation tree.

### Changed

- Moved lightning and sea-level HTTP to Home Assistant's shared async session with bounded connect/read/total timeouts, response-size limits, validated aware timestamps, isolated availability, and cached rate-limited address enrichment.
- Moved the integration to the standard `custom_components/fmi/` layout required by current Home Assistant validation.
- Upgraded `fmi-weather-client` from 0.7.0 to 1.0.0 and `geopy` to 2.5.0.
- Replaced direct `python-dateutil` use with Home Assistant timezone helpers and removed it from the integration's runtime requirements.
- Replaced `async-timeout` with the Python standard-library timeout and removed redundant direct dependencies already supplied by Home Assistant or the FMI client.
- Replaced flake8 completely with Ruff and upgraded existing CI action references to reviewed immutable commits.
- Split reviewed direct dependencies from the complete 173-package `pip freeze` lock generated in a clean container.
- Updated weather forecasts to Home Assistant's separate hourly/daily API with UTC timestamps and complete one-hour FMI source data; the deprecated forecast property was removed.
- Updated sensors to Home Assistant's current `SensorEntity`, entity-description, device-class, state-class, translated-name, and native-unit conventions while retaining existing unique IDs.
- Migrated config entries from coordinate-based identifiers to stable internal identities so coordinates and resolved place names can change safely, while conservatively preserving registry/unique IDs, customized or ambiguous suffixed entity IDs, and the optional legacy daily entity.
- Moved per-entry coordinators and listener cleanup to typed `ConfigEntry.runtime_data` and aligned read-only coordinator platforms with current Home Assistant parallel-update guidance.
- Made root `.version` the enforced version source for the manifest, changelog section, exact Git tag, and GitHub Release; version `1.0.0` is published automatically only after the `master` quality gates pass.

### Security

- Upgraded the container and CI installer to pip 26.2 and added vulnerability/license audit commands.
- Documented a temporary owner-approved exception for Pillow and PyJWT versions pinned by Home Assistant 2026.7.4. The required follow-up is tracked in `TODO.md`.
- Prevented precise configured coordinates, raw FMI responses, and external exception payloads from reaching integration or dependency logs.
- Replaced mutable nested hassfest/HACS images with reviewed digests and restricted release write access to the final post-validation publication job.
