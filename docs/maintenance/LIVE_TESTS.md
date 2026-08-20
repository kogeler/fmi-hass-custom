<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Live FMI Tests

Live suite last verified: 2026-08-20 against Home Assistant 2026.8.1 and
`fmi-weather-client` 1.0.0. FMI WFS documentation/metadata last reviewed: 2026-08-17.

## Purpose And Selection

The live suite is a marker-isolated compatibility probe, not part of the ordinary offline pytest selection. It checks the installed dependency against FMI WFS and then loads the integration through current Home Assistant config-entry, entity-state, entity-registry, and weather forecast-service APIs. The Home Assistant test helper installs a per-test DNS/socket guard independently of pytest's command-line socket option, so the live module narrowly restores real DNS/sockets in an autouse fixture and reinstates the guard during teardown. Required `ci.yml` runs the four live tests in a separate online rootless-Podman job after the offline quality gate for every pull request and every `master` push.

The public locations are deliberately unrelated to the repository owner's Home Assistant configuration:

| Probe | Public identifier | Reason |
|---|---|---|
| Place resolution and final coordinate validation | Helsinki | A public city name exercises FMI's place-name boundary; the resolved point is checked only against a broad northern-European bound before normal coordinate validation. |
| Northern forecast | Kilpisjarvi, `69.05,20.79` | Rounded public station-area coordinates exercise high-latitude output near Finland's north-western boundary. FMI's current station table lists Enontekio Kilpisjarvi as an operative weather station at approximately `69.0,20.8`. |
| Observation | Helsinki Kumpula, `FMISID 101004` | FMI publishes the station identifier and meteorological role; the selected client returns current observations for this public station. |

## Commands

Run the complete live suite with automatic xdist workers and the shared global request budget.
Xdist derives the worker count from CPUs visible inside the container, and the Make target prints
the actual number of FMI request attempts on completion:

```bash
make live
```

Use a fixed worker count only for diagnosis:

```bash
make live PYTEST_WORKERS=2
```

Prove default/offline marker separation:

```bash
make test-fast
make test-network-block
```

The offline suite must collect and deselect live tests without attempting a socket. Do not run
selected live tests with `--network=none` and interpret the resulting transport failure as an FMI
outage. Project source is tar-streamed into private tmpfs; a bind-mounted checkout is not a
supported command.

## WFS Surface And Request Budget

All calls use `https://opendata.fmi.fi/wfs`, WFS 2.0 `GetFeature`, and the installed client's bounded ten-second HTTP timeout.

| Level | Stored query | Nominal requests | Maximum |
|---|---|---:|---:|
| Dependency place resolution and resolved-coordinate validation | `fmi::forecast::edited::weather::scandinavia::point::multipointcoverage` | 2 | 4 |
| Dependency northern forecast | `fmi::forecast::edited::weather::scandinavia::point::multipointcoverage` | 1 | 2 |
| Dependency station observation | `fmi::observations::weather::multipointcoverage` | 1 | 2 |
| Home Assistant current, hourly forecast, and station observation | Both queries above | 3 | 4 |
| Total | - | 7 | 12 |

Each dependency call retries once, after one second, only for timeout, transport, or FMI server errors. Client/request and parsing/shape errors are not retried. The Home Assistant probe uses the integration's 40-second coordinator bound and performs no test-level retry. It suppresses the unrelated optional sea-level request and permits at most one place-observation fallback, while retaining real forecast/current/station calls and their normal parsers. All xdist workers share a file-locked counter and two-slot semaphore in the container's `/tmp`; every real attempt reserves before I/O, and attempt thirteen fails locally without contacting FMI.

FMI currently publishes limits of 20,000 Download Service requests per day and 600 combined Download/View requests per five minutes. The twelve-request worst case is 0.06% of the daily Download limit and 2% of the short-window combined limit. Automatic xdist is required, but its worker count never changes the shared twelve-attempt/two-concurrent-request bounds. Never add unbounded parameterization, response polling, or automatic retry plugins.

## Assertions

The dependency probes require a non-empty canonical place, a resolved point inside a broad northern-European bound, non-empty forecast series, aware strictly ordered timestamps, at least one usable core meteorological value, broad physical plausibility for finite values, and an observation no more than 45 minutes old. The resolved point is validated through the same coordinate-weather boundary used by the config flow; no exact external label or coordinates are asserted. The selected client requests a 20-minute observation window at a 10-minute timestep, and the integration refreshes station data every 10 minutes; the 45-minute bound adds service/clock margin without accepting materially stale dashboard data. FMI/client `NaN` missing sentinels are treated as absent; infinity, non-numeric present values, and out-of-range finite values are contract failures.

The Helsinki coordinate-current result requires finite 0–100 PoP and thunder probability. The
Kilpisjärvi dependency forecast and Helsinki Home Assistant production coordinator require both
probabilities for every sample on the first available future Europe/Helsinki local forecast date.
This selects the current date when a future hour remains and the next represented date after the
last hourly boundary, so the permanent probe is equally strict at every wall-clock time. These
assertions use the production adapter and existing calls; they add no request and accept valid zero
probabilities.

The Home Assistant probe additionally requires:

- loaded main and Kumpula observation weather entities;
- current/observation temperature values matching their live source models within Home Assistant's
  display precision, and current apparent temperature matching the client-derived feels-like value;
- expected Home Assistant temperature/pressure units and an available temperature sensor;
- available, finite, broadly plausible states for feels like, dew point, atmospheric pressure,
  all three cloud layers, precipitation probability, and thunderstorm probability;
- non-empty hourly and daily forecast service payloads with aware ordered timestamps;
- finite apparent temperature and PoP on every first-available-future-local-day hourly forecast
  item;
- finite, broadly plausible values exposed to dashboards, including valid zero probabilities;
- each daily precipitation value to equal the sum of matching hourly values under the configured
  `Europe/Helsinki` local-day rule, within the exact maximum error introduced when Home Assistant
  independently rounds every hourly value and the daily total to two decimal places;
- at most four live calls during setup.

No test asserts an exact temperature, condition, precipitation, station reading, place label, or forecast length.

## Failure Classification

- `FMI transport/service failure`: timeout, network/HTTP transport, or FMI server response remained unavailable after the single retry. Re-run once manually and inspect FMI status before changing code.
- `FMI request/contract failure`: FMI rejected the selected query or parameters. Check current stored-query descriptions and the installed client's request construction.
- `FMI parsing/contract failure` or `LiveContractError`: response/model/service shape, timestamps, values, or ordering drifted. Preserve the failing public metadata and add an offline fixture before adapting code.
- `Home Assistant setup/exposure failure`: client data did not complete config-entry setup or reach entity/service APIs. Reproduce offline at the coordinator/entity boundary before changing lifecycle behavior.

The exact four bounded tests and request budget are a required `ci.yml` job after quality. The job
uses no secret and runs for pull requests and every `master` push; a new-version release invokes
the reusable CI a second time before publication. There is no standalone or scheduled live
workflow. An FMI transport/service outage is intentionally merge- and release-blocking; use the
failure classification above and re-run once before diagnosing an integration regression.

## Licence, Attribution, And Privacy

FMI open data is licensed under Creative Commons Attribution 4.0 International (CC BY 4.0). Runtime entities retain the attribution `Weather Data provided by FMI`. Tests store no response payload or weather values as artifacts; logs may contain only the public identifiers above, failure classifications, and normal pytest diagnostics, never query parameters or response bodies. Never substitute owner coordinates, secrets, private station choices, Home Assistant storage, or captured owner data.

## Authoritative Sources

Accessed 2026-08-17:

- FMI WFS service, stored-query discovery, terms, and limits: <https://en.ilmatieteenlaitos.fi/open-data-manual-fmi-wfs-services>
- FMI stored-query examples and parameter guidance: <https://en.ilmatieteenlaitos.fi/open-data-manual-wfs-examples-and-guidelines>
- FMI open-data changelog: <https://en.ilmatieteenlaitos.fi/open-data-changelog>
- FMI observation station metadata: <https://en.ilmatieteenlaitos.fi/observation-stations>
- FMI Kumpula metadata (`FMISID 101004`): <https://en.ilmatieteenlaitos.fi/ghg-kumpula>
- FMI open-data CC BY 4.0 statement: <https://en.ilmatieteenlaitos.fi/download-observations-questions>
- Creative Commons Attribution 4.0 licence: <https://creativecommons.org/licenses/by/4.0/>
