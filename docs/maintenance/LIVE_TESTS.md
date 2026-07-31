<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Live FMI Tests

Last verified: 2026-07-31 against Home Assistant 2026.7.4, `fmi-weather-client` 1.0.0, and the current FMI WFS documentation/metadata.

## Purpose And Selection

The live suite is a marker-isolated compatibility probe, not an ordinary regression suite. It checks the installed dependency against FMI WFS and then loads the integration through current Home Assistant config-entry, entity-state, entity-registry, and weather forecast-service APIs. The Home Assistant test helper installs a per-test DNS/socket guard independently of pytest's command-line socket option, so the live module narrowly restores real DNS/sockets in an autouse fixture and reinstates the guard during teardown. Default tests remain guarded and offline; the current `verify.yml` explicitly selects the live marker in a separate step after they pass.

The public locations are deliberately unrelated to the repository owner's Home Assistant configuration:

| Probe | Public identifier | Reason |
|---|---|---|
| Southern forecast | Helsinki, `60.17,24.94` | Rounded city-centre coordinates provide a stable southern Finland point inside the edited Scandinavia forecast domain. |
| Northern forecast | Kilpisjarvi, `69.05,20.79` | Rounded public station-area coordinates exercise high-latitude output near Finland's north-western boundary. FMI's current station table lists Enontekio Kilpisjarvi as an operative weather station at approximately `69.0,20.8`. |
| Observation | Helsinki Kumpula, `FMISID 101004` | FMI publishes the station identifier and meteorological role; the selected client returned a current observation during S12 verification. |

## Commands

Run the complete live suite, with networking enabled and no xdist workers:

```bash
make live
```

Equivalent explicit command in the supported Podman environment:

```bash
podman run --rm --userns=keep-id -v "$PWD:/workspace:Z" -w /workspace \
  localhost/fmi-hass-custom-dev:2026.7.4 \
  python -m pytest -o addopts= --strict-config --strict-markers -n 0 -m live
```

Prove default/offline marker separation:

```bash
make test-fast
podman run --rm --userns=keep-id -v "$PWD:/workspace:Z" -w /workspace \
  --network=none localhost/fmi-hass-custom-dev:2026.7.4 \
  python -m pytest -q tests/test_live_fmi.py
```

The second command must collect and deselect the live tests without attempting a socket. Do not run selected live tests with `--network=none` and interpret the resulting transport failure as an FMI outage.

## WFS Surface And Request Budget

All calls use `https://opendata.fmi.fi/wfs`, WFS 2.0 `GetFeature`, and the installed client's bounded ten-second HTTP timeout.

| Level | Stored query | Nominal requests | Maximum |
|---|---|---:|---:|
| Dependency forecasts, south and north | `fmi::forecast::edited::weather::scandinavia::point::multipointcoverage` | 2 | 4 |
| Dependency station observation | `fmi::observations::weather::multipointcoverage` | 1 | 2 |
| Home Assistant current, hourly forecast, and station observation | Both queries above | 3 | 4 |
| Total | - | 6 | 10 |

Each dependency call retries once, after one second, only for timeout, transport, or FMI server errors. Client/request and parsing/shape errors are not retried. The Home Assistant probe uses the integration's 40-second coordinator bound and performs no test-level retry. It suppresses the unrelated optional sea-level request and permits at most one place-observation fallback, while retaining real forecast/current/station calls and their normal parsers.

FMI currently publishes limits of 20,000 Download Service requests per day and 600 combined Download/View requests per five minutes. The ten-request worst case is 0.05% of the daily Download limit and about 1.67% of the short-window combined limit. Never add xdist, unbounded parameterization, response polling, or automatic retry plugins to this workflow.

## Assertions

The dependency probe requires a non-empty place and series, aware strictly ordered timestamps, at least one usable core meteorological value, broad physical plausibility for finite values, and an observation no more than 45 minutes old. The selected client requests a 20-minute observation window at a 10-minute timestep, and the integration refreshes station data every 10 minutes; the 45-minute bound adds service/clock margin without accepting materially stale dashboard data. FMI/client `NaN` missing sentinels are treated as absent; infinity, non-numeric present values, and out-of-range finite values are contract failures.

The Home Assistant probe additionally requires:

- loaded main and Kumpula observation weather entities;
- current/observation temperature values matching their live source models within Home Assistant's 0.1-degree display precision;
- expected Home Assistant temperature/pressure units and an available temperature sensor;
- non-empty hourly and daily forecast service payloads with aware ordered timestamps;
- finite, broadly plausible values exposed to dashboards;
- each daily precipitation value to equal the sum of matching hourly values under the configured `Europe/Helsinki` local-day rule;
- at most four live calls during setup.

No test asserts an exact temperature, condition, precipitation, station reading, place label, or forecast length.

## Failure Classification

- `FMI transport/service failure`: timeout, network/HTTP transport, or FMI server response remained unavailable after the single retry. Re-run once manually and inspect FMI status before changing code.
- `FMI request/contract failure`: FMI rejected the selected query or parameters. Check current stored-query descriptions and the installed client's request construction.
- `FMI parsing/contract failure` or `LiveContractError`: response/model/service shape, timestamps, values, or ordering drifted. Preserve the failing public metadata and add an offline fixture before adapting code.
- `Home Assistant setup/exposure failure`: client data did not complete config-entry setup or reach entity/service APIs. Reproduce offline at the coordinator/entity boundary before changing lifecycle behavior.

The interim `verify.yml` step follows the workflow's pull-request and default-branch push triggers, is blocking, and does not use `continue-on-error`. This owner-selected S12 arrangement deliberately keeps the probe next to the main tests; S15 owns the final CI trigger, job separation, and upstream-outage policy.

## Licence, Attribution, And Privacy

FMI open data is licensed under Creative Commons Attribution 4.0 International (CC BY 4.0). Runtime entities retain the attribution `Weather Data provided by FMI`. Tests store no response payload or weather values as artifacts; logs may contain only the three public identifiers above, query parameters, classifications, and normal pytest diagnostics. Never substitute owner coordinates, secrets, private station choices, Home Assistant storage, or captured owner data.

## Authoritative Sources

Accessed 2026-07-31:

- FMI WFS service, stored-query discovery, terms, and limits: <https://en.ilmatieteenlaitos.fi/open-data-manual-fmi-wfs-services>
- FMI stored-query examples and parameter guidance: <https://en.ilmatieteenlaitos.fi/open-data-manual-wfs-examples-and-guidelines>
- FMI open-data changelog: <https://en.ilmatieteenlaitos.fi/open-data-changelog>
- FMI observation station metadata: <https://en.ilmatieteenlaitos.fi/observation-stations>
- FMI Kumpula metadata (`FMISID 101004`): <https://en.ilmatieteenlaitos.fi/ghg-kumpula>
- FMI open-data CC BY 4.0 statement: <https://en.ilmatieteenlaitos.fi/download-observations-questions>
- Creative Commons Attribution 4.0 licence: <https://creativecommons.org/licenses/by/4.0/>
