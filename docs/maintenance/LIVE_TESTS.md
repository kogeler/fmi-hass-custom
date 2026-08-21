<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Live FMI Test Maintenance

Normative network isolation, public inputs, request budget, dependency/HA assertions, and CI status
are owned exclusively by [the live-test contract](../contracts/LIVE_TESTS.md).

## Commands

Run the complete bounded suite through:

```bash
make live
```

Use `PYTEST_WORKERS=<N>` only to diagnose parallel behavior. Prove ordinary marker/socket isolation
with `make test-fast` and `make test-network-block`. A direct pytest, Python, or container command is
not a supported alternative.

## Change Checklist

1. Map any public location, request, retry, budget, freshness, or assertion change to `LIV-*`.
2. Preserve one shared cross-process attempt counter and semaphore under automatic xdist.
3. Add an offline fixture/regression before adapting production code to observed contract drift.
4. Never add exact weather/place/length assertions or store live response values as artifacts.
5. Keep the Home Assistant probe on production coordinator/entity/service paths.
6. Run `make test-fast`, `make test-network-block`, and one final `make live` after all offline work
   is green.

## Failure Classification

- **Transport/service:** the bounded retry still ended in timeout/network/HTTP/server failure.
  Re-run once and inspect FMI status before changing code.
- **Request contract:** FMI rejected the query/parameters. Recheck the installed client's request
  construction and FMI stored-query metadata.
- **Parsing/model contract:** response shape, timestamps, ranges, or ordering drifted. Preserve only
  public metadata and create a small synthetic offline fixture.
- **Home Assistant exposure:** valid client data failed to reach setup/entity/forecast APIs.
  Reproduce offline at the coordinator/entity boundary.

An outage remains visible and blocking under `LIV-006`; failure classification is not permission to
weaken or skip the contract.

## Authoritative Sources

- [FMI WFS services, terms, and limits](https://en.ilmatieteenlaitos.fi/open-data-manual-fmi-wfs-services)
- [FMI stored-query examples](https://en.ilmatieteenlaitos.fi/open-data-manual-wfs-examples-and-guidelines)
- [FMI open-data changelog](https://en.ilmatieteenlaitos.fi/open-data-changelog)
- [FMI observation stations](https://en.ilmatieteenlaitos.fi/observation-stations)
- [FMI Kumpula metadata](https://en.ilmatieteenlaitos.fi/ghg-kumpula)
- [FMI open-data attribution statement](https://en.ilmatieteenlaitos.fi/download-observations-questions)
- [Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/)
