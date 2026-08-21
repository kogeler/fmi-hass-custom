<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Changelog

All notable changes to this project are documented in this file.

## 1.3.0 - 2026-08-20

### User-facing features

- Added dedicated **Feels like**, **Dew point**, **Atmospheric pressure**, low/medium/high cloud
  cover, **Precipitation probability**, and **Thunderstorm probability** sensors to the existing
  location device, with native Home Assistant units, translations, history-friendly numeric
  states, and independent missing-data recovery.
- Added apparent temperature to current weather and hourly/daily forecast output, plus FMI hourly
  PoP to Home Assistant's standard precipitation-probability forecast field. Daily PoP remains
  omitted because hourly event probabilities cannot be combined without an unavailable dependence
  model.
- Added an optional Detailed Weather Forecast dashboard example that exposes more of those FMI
  values than Home Assistant's fixed standard weather-card layout: current metric chips, expandable
  cloud-layer details, hourly apparent temperature, and additional hourly/daily forecast details.
- Made **Best time of day** choose a remaining current-day hour using transparent thunder risk,
  feels-like comfort, rain chance/amount, and earliest-time priorities under the user's configured
  limits.

### Changed

- Consolidated normative integration and repository behavior in a test-traceable contract catalog;
  audited user and maintainer documentation against the current code, Make surface, and CI graph;
  and added automated checks for documentation links, command references, translation structure,
  and the completed-plan archive boundary.
- Kept the Best-time entity, registry/unique IDs, customized entity ID, `HH:MM` selected state, and
  existing attributes/options, while interpreting its stored temperature range as acceptable
  feels-like temperature instead of air temperature.
- Replaced the misleading current-time and warmest-hour fallback with a translated
  `no_suitable_time` result for a healthy day with no matching hour. Missing or unusable forecast
  data remains `unavailable`, and both outcomes clear stale selection attributes.
- Added apparent temperature, precipitation probability, and thunderstorm probability to selected
  Best-time attributes without exposing an opaque comfort score or making a medical/safety claim.

### Fixed

- Kept PoP and thunder-probability values aligned to their aware forecast timestamps and cleared
  them with their owning current/forecast data, preventing stale values after replacement or
  failure without adding another FMI request or runtime dependency.
- Preserved customized and disabled entity-registry records through upgrade/reload while adding
  the complete sensor set exactly once on the existing location device.

## 1.2.0 - 2026-08-19

### User-facing features

- Made a successful FMI lightning response with no qualifying strikes an available, translated
  `no_strikes` state instead of reporting the sensor unavailable.
- Replaced best-effort lightning addresses with a concise locally calculated state such as
  `42.3 km · SE`, relative to the coordinates stored by that specific FMI entry. Primary and
  retained observation attributes now include numeric `distance`, `bearing`, and stable compass
  `direction` without claiming storm motion or arrival.
- Improved lightning privacy and reliability: FMI, the integration's primary read-only source for
  weather and geospatial observations, is now the only external data service needed at runtime.
  After an FMI response arrives, strike coordinates remain inside Home Assistant and all distance
  and direction calculations happen locally. This keeps subsequent data processing under the
  user's control while eliminating disclosure to a secondary provider and removing Nominatim's
  availability, usage-policy, and rate-limit failure modes.

### Changed

- Restricted normal HACS downloads to published releases instead of offering the moving default
  branch alongside them, while keeping manual source installation available.
- **Compatibility migration:** the lightning sensor no longer stores a reverse-geocoded address or
  raw-coordinate fallback as its native state, and primary/`OBSERVATIONS` rows no longer contain
  `location`. Templates and automations using those values must migrate to `direction`, `bearing`,
  or `distance`. Existing entity-registry records, unique IDs, customized entity IDs, devices,
  config entries, options, and Recorder history remain unchanged.
- Enforced the configured lightning radius as an inclusive circle after FMI's square bounding-box
  request prefilter while retaining the five-nearest/newest presentation order.
- Added a structured bug-report form that requests reproducible versioned evidence and explicitly
  requires coordinates, secrets, and raw FMI responses to be removed.
- Split HACS and hassfest into separately visible CI checks while retaining immutable validator
  image digests, private tar-streamed source snapshots, and read-only workflow permissions.

### Fixed

- Cleared every stale lightning state and dynamic attribute on empty or failed refreshes, kept
  optional-source failures independent from weather/forecast/observation/sea-level availability,
  and allowed later valid refreshes to recover without reloading the entry.

### Security

- Removed Nominatim, OpenStreetMap address attribution, strike-coordinate disclosure to a second
  service, geocoder caches/rate limiting, and the unused geopy/geographiclib dependency graph.
  Lightning geometry is now local and network-free after the bounded FMI response is received.

## 1.1.0 - 2026-08-17

### User-facing features

- Added map-based setup and reconfiguration together with FMI place-name search and explicit map confirmation, so a location can be selected or moved without entering raw coordinates and without replacing the existing integration entry or its entity identities.

### Added

- Added a content-addressed rootless Podman toolbox with tar-streamed source, read-only filesystems, private namespaces, dropped capabilities, no-new-privileges, bounded resources, and offline networking by default.
- Added containerized Bandit and ShellCheck gates while retaining Pylint, mypy, pip-audit, actionlint, hassfest, HACS, Dependency Review, and CodeQL checks.
- Added trusted `master`-only Dependency Submission for the complete runtime, development, and Ruff hash locks using the job-scoped standard GitHub token.

### Changed

- Moved all direct Python dependencies to PEP 621 metadata and replaced the legacy requirement inputs with three generated SHA-256 hash locks for runtime review, the container toolbox, and host-only Ruff.
- Made every offline, network-block, live FMI, and moving-compatibility pytest run use automatic xdist workers while preserving one shared twelve-request live budget.
- Serialized Make orchestration around shared locks, images, and reports; made failed exports return an atomic empty archive; and prevented partial coverage output from being published as a completed report.
- Consolidated read-only GitHub checks into one reusable CI workflow, retained isolated PR metadata and release write boundaries, and aligned Dependabot with the pip and GitHub Actions manifests.
- Updated the reproducible development and test reference to Home Assistant 2026.8.1 with its matching test helper and regenerated development hash lock, while retaining the existing HACS minimum because no functional incompatibility was found.
- Retained version-free latest-stable and prerelease CI compatibility resolution because it already selects and tests the current Home Assistant channels independently of the reference lock.
- Removed concrete Home Assistant and test-helper version assertions from repository tests; compatibility is established by behavior, while exact selections remain in PEP 621 and the generated development lock.
- Documented a repeatable Home Assistant stable-release maintenance flow that keeps reference-only updates unreleased until the distributed integration contract changes.
- Clarified how to switch HACS from another FMI repository to this fork without deleting the existing Home Assistant integration entry or registry state.
- Made the informational prerelease compatibility job skip successfully when no newer installable Home Assistant prerelease exists, while retaining failures for actual prerelease regressions.
- Made the `master` release workflow finish successfully without repeating release gates when `.version` already has a published stable GitHub Release with its exact lightweight tag still attached to the recorded release commit.

### Fixed

- Kept reusable release CI read-only by moving Dependency Submission to its own trusted master-push workflow, and allowed workflow-only recovery commits to retain a release version until that version is actually published.
- Prevented valid live daily-precipitation checks from failing when Home Assistant independently rounds hourly values and their daily total for forecast service responses.
- Preserved the existing CodeQL SARIF identities after workflow consolidation so pull requests remain comparable with the `master` code-scanning baseline.

### Security

- Replaced integration-owned standard-library XML parsing with maintained `xmltodict==1.0.4`, explicit entity disabling, a 2 MiB parser ceiling, and an Expat 2.7.2 minimum; also made bounding-box input validation effective even when Python assertions are optimized away.
- Removed the Pillow and PyJWT vulnerability exceptions after Home Assistant selected their fixed releases, and documented an exact temporary exception for the vulnerable cryptography release still pinned by Home Assistant.

## 1.0.1 - 2026-08-01

### Added

- Added repository-wide code ownership for `@kogeler`.

### Changed

- Simplified local Podman environment updates by using stable development image and cache-stamp names while keeping Home Assistant and transitive dependency versions in the reviewed requirements freezes.

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
- Added a focused end-user guide with HACS/manual installation, configuration, upgrade, removal, troubleshooting, and standard Home Assistant dashboard examples.

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
- Removed an obsolete debug-only lightning script that logged precise coordinate-derived values and request URLs, resolving the PR CodeQL findings without suppressions.
- Replaced mutable nested hassfest/HACS images with reviewed digests and restricted release write access to the final post-validation publication job.
