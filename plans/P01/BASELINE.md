<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Plan P01 Baseline

## Snapshot

- Accessed: 2026-07-31
- Local repository: `kogeler/fmi-hass-custom`
- Repository: `kogeler/fmi-hass-custom`
- Default branch: `master`
- Base commit: `77a265cf910050aa6e2e37a4eb57d951bddc2910`
- Base commit date: `2025-07-24T23:53:46+03:00`
- Base commit subject: `Manifest updated for v0.6.2`
- Baseline release: `v0.6.2`, published 2025-07-24

The local `master` and its `origin/master` both pointed to the base commit at the start of maintenance. The latest baseline tag was `v0.6.2`.

## Repository layout

The integration code is stored at repository root. HACS uses `"content_in_root": true` from `hacs.json`, and the README instructs manual installers to place these root files in `<config>/custom_components/fmi/`. Current HACS documentation explicitly permits this legacy root-content layout. S01 must still prove that the current HACS validator, hassfest, and Home Assistant test harness all accept it before deciding whether it should be retained.

| Path | Current responsibility |
|---|---|
| `__init__.py` | Config-entry setup/unload, forecast and observation coordinators, best-condition calculation, and optional lightning/sea-level retrieval and parsing. |
| `config_flow.py` | Latitude/longitude config flow, FMI validation, and the existing options flow. |
| `weather.py` | Current, hourly, daily, and observation `WeatherEntity` exposure. |
| `sensor.py` | Weather-value, best-time, lightning, and sea-level sensor entities. |
| `utils.py` | Bounding-box calculations and FMI-to-Home-Assistant weather-symbol mapping, including sun-event lookup. |
| `const.py` | Domain, update intervals, options/defaults, FMI stored-query URLs, and symbol constants. |
| `manifest.json` | Home Assistant integration metadata and runtime requirements. |
| `strings.json`, `translations/` | Config/options UI strings and English/Finnish translations. |
| `debug/test_lightning.py` | Manual network diagnostic; it is not an automated or offline test. |
| `.github/workflows/verify.yml` | Existing flake8/pylint workflow for Python 3.12 and 3.13. |

There is no `tests/` directory, package/development lock, coverage configuration, type-check job, hassfest workflow, HACS validation workflow, dependency audit, or live FMI workflow.

## Dependencies

`manifest.json` declares runtime requirements installed by Home Assistant:

- `fmi-weather-client==0.7.0`
- `geopy>=2.1.0`

The current `requirements.txt` is an unfrozen mixture of runtime transitive packages and development tools. It permits `fmi-weather-client>=0.7.0`, which does not reproduce the manifest's runtime selection. Per the updated maintenance plan, S01 must establish a separate source of intended direct development/test dependencies, and S03 must regenerate root `requirements.txt` as a complete exact `python -m pip freeze` from a clean supported environment after direct dependency upgrades.

Versions published on PyPI on the access date are:

| Existing direct entry | Current constraint | Latest stable | Declared Python |
|---|---|---|---|
| `python-dateutil` | unbounded | `2.9.0.post0` | `>=2.7`, excluding Python 3.0-3.2 |
| `async-timeout` | unbounded | `5.0.1` | `>=3.8` |
| `voluptuous` | unbounded | `0.16.0` | `>=3.9` |
| `requests` | `>=2.32.4` | `2.34.2` | `>=3.10` |
| `fmi-weather-client` | `>=0.7.0` | `1.0.0` | `>=3.10` |
| `geopy` | `>=2.1.0` | `2.5.0` | `>=3.8` |
| `xmltodict` | `>=0.14.2` | `1.0.4` | `>=3.9` |
| `flake8` | unbounded | `7.3.0` | `>=3.9` |
| `pylint` | unbounded | `4.0.6` | `>=3.10` |

No package was upgraded in S00.

The `fmi-weather-client` 1.0.0 wheel was inspected without installing it. It is GPL-3.0, declares `requests~=2.32` and `xmltodict~=1.0`, and exposes synchronous functions plus `async_` executor-backed variants for weather, forecast, and observation queries. Its public named tuples still include `Weather`, `Forecast`, `WeatherData`, `wind_gust`, and `wind_max`. This is characterization only; S02/S03 must add offline contract tests before changing the runtime pin.

## Current CI and command baseline

The only workflow runs on pull requests and `master` pushes. It uses mutable `actions/checkout@v4` and `actions/setup-python@v5` tags, installs `requirements.txt`, runs flake8's selected fatal-error check plus a non-blocking `--exit-zero` report, and runs pylint. The base commit's workflow run completed successfully on 2025-07-24. The polar sunrise/sunset proposal had no completed validation result.

| Command | Result | Evidence |
|---|---|---|
| `git status --short --branch` | PASS | Started on `master...origin/master`; only the owner-provided plan was initially untracked. |
| `git log --oneline --decorate -n 12` | PASS | HEAD was `77a265c`; recent history was inspected. |
| `python3 --version` | PASS | Host provides Python 3.13.5. |
| `python --version` | FAIL | `python` is not installed. |
| `flake8 --version` | FAIL | `flake8` is not installed. |
| `pylint --version` | FAIL | `pylint` is not installed. |
| Existing flake8 workflow commands | FAIL | Could not start because `flake8` is absent. |
| Existing pylint workflow command | FAIL | Could not start because `pylint` is absent. |

S00 did not install tools because reproducible environment setup belongs to S01. The host's Python 3.13.5 is also below the current Home Assistant requirement, so it cannot be treated as a valid current Home Assistant test environment.

## Maintenance report inventory

The reports reviewed at the maintenance baseline exactly match the maintenance plan. No additional closure-matrix row was needed.

| Reference | State | Opened/updated UTC | Maintenance relevance |
|---|---|---|---|
| Lightning maximum age | Open | 2025-08-01 / 2025-08-01 | Required S09 enhancement/reliability work. |
| Wind gust unavailable | Open | 2025-08-03 / 2026-01-28 | Required S06 regression. |
| Sensors not grouped by location | Open | 2025-08-12 / 2025-08-12 | Required S06/S11 naming and migration work. |
| Incorrect daily forecast | Open | 2025-11-07 / 2025-11-07 | Required S05 correctness work. |
| Location selection | Open | 2026-05-21 / 2026-05-21 | Required S07/S11 reconfigure and identity work. |
| Polar sunrise/sunset | Open | 2026-07-02 / 2026-07-02 | Required S08 review and regression tests. |
| Forecast failure disables observations | Open | 2026-07-20 / 2026-07-20 | Required S04 availability work. |

Previously closed reports reviewed for regression context:

| Reference | Closed UTC | Relevance |
|---|---|---|
| Missing integration icon | 2025-09-17 | Closed UI/brand report; no production-code change was present at the baseline. |
| Forecast output format | 2025-07-24 | Closed around v0.6.2; forecast API behavior remains relevant to S05/S10. |
| Error fetching FMI data | 2025-07-24 | Closed service/setup failure report; relevant to S04/S13. |
| Wrong observation location | 2025-07-22 | Closed v0.6.0 regression; relevant to naming, station, and migration tests. |
| Incorrect weather icons | 2025-07-22 | Closed v0.6.0 regression; relevant to symbol characterization. |
| Empty weather state | 2025-07-22 | Closed v0.6.0 regression; relevant to current-weather entity tests. |
| Separate update intervals | 2025-07-22 | Implemented by separate coordinators; lifecycle/update behavior requires tests. |
| Sensor unique IDs | 2025-07-18 | Closed regression; directly relevant to S06/S11 identity coverage. |

## Current ecosystem support assumptions

- Latest Home Assistant stable is `2026.7.4`; latest beta is `2026.8.0b2`.
- Home Assistant `2026.7.4` and `dev` both declare Python `>=3.14.2`, and the developer setup documentation requires Python 3.14.2 or newer. The repository's Python 3.12/3.13 CI matrix is therefore not a current Home Assistant compatibility matrix.
- Current Home Assistant testing guidance uses pytest, recommends tests through integration-facing state/public behavior, and warns against testing private integration details. The exact standalone custom-component harness and commands remain an S01 decision.
- Home Assistant Core's complete `dev` tree has no `homeassistant/components/fmi` path. Domain `fmi` is not currently owned by an official Core integration, so S00 is not blocked.
- Latest HACS release is `2.0.5`. HACS documents root content as valid with `content_in_root: true`, but its repository rules also expect integration metadata such as `issue_tracker`; default-store inclusion additionally expects brands, topics, releases, HACS validation, and hassfest. The repository had no GitHub topics at the baseline.
- The official standalone hassfest action runs `ghcr.io/home-assistant/hassfest` in Docker. Its README demonstrates `home-assistant/actions/hassfest@master`; this plan's stricter supply-chain rule requires pinning the eventual workflow to a reviewed full commit SHA.

## FMI Open Data contract

- FMI publishes machine-readable WFS data without charge under CC BY 4.0; use requires accepting the license and providing attribution.
- The WFS download service limit is 20,000 requests/day. Download and view services share a limit of 600 requests/5 minutes; view service also has a 10,000 requests/day limit.
- FMI recommends selecting only required parameters and using an appropriate timestep, start time, and time window to avoid oversized or misaligned queries.
- The newest changelog entry is dated 2025-10-02. The most relevant recent forecast change is the 2025-02-06 removal of deprecated `WeatherSymbol1` from edited Scandinavian forecast queries in favor of `WeatherSymbol3`; numeric values are not equivalent.

## Known gaps and risks

- There is no deterministic offline safety net before dependency or behavior changes.
- Runtime and development dependency constraints are inconsistent and non-reproducible; `requirements.txt` is not a complete freeze yet.
- Current local tooling cannot run the repository's existing validation, and the available Python is below current Home Assistant's requirement.
- Current CI proves only limited linting on obsolete Python targets. It does not prove importability, config-entry setup, entity behavior, HACS/hassfest compliance, dependency safety, or live FMI behavior.
- Root layout is documented as HACS-compatible, but actual hassfest/HACS validation of this repository has not been run.
- Code inspection confirms the risk areas already assigned by the plan: all-or-nothing forecast setup, partial-date comparisons, optional-source parsing/network boundaries, manual coordinator listeners, global logging configuration, mutable coordinate-based identity, and absent-value handling. These are audit hypotheses until reproduced in their owning sessions.
- External support is not declared in `hacs.json` or README. Compatibility with Home Assistant 2026.7.4 remains unproven until S01/S10/S14.

## Authoritative sources

All sources below were accessed on 2026-07-31.

### Repository

- [Repository](https://github.com/kogeler/fmi-hass-custom)

### Home Assistant, HACS, and hassfest

- [Home Assistant 2026.7.4](https://github.com/home-assistant/core/releases/tag/2026.7.4)
- [Home Assistant 2026.8.0b2](https://github.com/home-assistant/core/releases/tag/2026.8.0b2)
- [Home Assistant 2026.7.4 pyproject](https://github.com/home-assistant/core/blob/2026.7.4/pyproject.toml)
- [Home Assistant development environment](https://developers.home-assistant.io/docs/development_environment/)
- [Home Assistant testing guidance](https://developers.home-assistant.io/docs/development_testing/)
- [Home Assistant integration test structure](https://developers.home-assistant.io/docs/creating_integration_tests_file_structure/)
- [Home Assistant integration manifest](https://developers.home-assistant.io/docs/creating_integration_manifest/)
- [Home Assistant Core component tree](https://github.com/home-assistant/core/tree/dev/homeassistant/components)
- [HACS integration repository rules](https://www.hacs.xyz/docs/publish/integration/)
- [HACS general repository rules](https://www.hacs.xyz/docs/publish/start/)
- [HACS validation action](https://www.hacs.xyz/docs/publish/action/)
- [HACS 2.0.5 release](https://github.com/hacs/integration/releases/tag/2.0.5)
- [Home Assistant standalone hassfest action](https://github.com/home-assistant/actions/tree/master/hassfest)
- [hassfest action source inspected at `ab22029681aa532bfe7de5774a9972d67bfbd2c0`](https://github.com/home-assistant/actions/commit/ab22029681aa532bfe7de5774a9972d67bfbd2c0)

### FMI and client package

- [`fmi-weather-client` on PyPI](https://pypi.org/project/fmi-weather-client/)
- [`fmi-weather-client` source](https://codeberg.org/saaste/fmi-weather-client)
- [FMI Open Data overview](https://en.ilmatieteenlaitos.fi/open-data)
- [FMI Open Data manual](https://en.ilmatieteenlaitos.fi/open-data-manual)
- [FMI WFS services and limits](https://en.ilmatieteenlaitos.fi/open-data-manual-fmi-wfs-services)
- [FMI WFS examples and guidelines](https://en.ilmatieteenlaitos.fi/open-data-manual-wfs-examples-and-guidelines)
- [FMI time-series data](https://en.ilmatieteenlaitos.fi/open-data-manual-time-series-data)
- [FMI Open Data changelog](https://en.ilmatieteenlaitos.fi/open-data-changelog)
- [FMI Open Data CC BY 4.0 license](https://en.ilmatieteenlaitos.fi/open-data-licence)
