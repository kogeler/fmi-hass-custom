<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Dependency Model And Inventory

This document explains which dependency files are authoritative, why the supported environment
uses its current direct selections, and what must be reviewed when they change. Keep it focused on
the current dependency contract rather than historical before/after reporting.

Last verified: 2026-08-01. Supported environment: Home Assistant 2026.7.4 on Python 3.14.2.

## File Roles

| File | Ownership |
|---|---|
| `custom_components/fmi/manifest.json` | Exact direct runtime requirements not guaranteed by Home Assistant Core |
| `requirements-direct.txt` | Human-reviewed exact direct selections for the supported development/test environment |
| `requirements.txt` | Generated complete 173-package `pip freeze`; never edit manually |
| `requirements-bootstrap.txt` | Exact standalone pip bootstrap selection because normal `pip freeze` omits pip |
| `requirements-compatibility-homeassistant.txt` | Unpinned Home Assistant channel inputs for moving compatibility resolution |
| `requirements-compatibility-direct.txt` | Unpinned helper/integration inputs for moving compatibility resolution |
| `requirements-compatibility-*-resolved.txt` | Ignored per-run full freezes generated and recreated by compatibility checks |

The committed root freeze is one coherent supported environment: Home Assistant stable, its exact
test helper, integration dependencies, and maintenance tools. Stable and prerelease drift checks
resolve in isolated temporary environments and never mutate this lock.

Every maintained `pip install` in workflows, the Makefile, container recipes, and repository CI
helpers consumes a requirements or generated constraint file. Do not add inline package names or
versions.

## Supported Direct Selections

| Component | Selected | Role and constraint |
|---|---:|---|
| Python | 3.14.2 | Required by Home Assistant 2026.7.4; official slim image is pinned by multi-architecture digest |
| Home Assistant | 2026.7.4 | Supported runtime/test host; prereleases belong only to moving compatibility checks |
| `pytest-homeassistant-custom-component` | 0.13.348 | Pins the exact supported Home Assistant release |
| `fmi-weather-client` | 1.0.0 | Direct GPL-3.0 runtime dependency, exact manifest pin |
| `geopy` | 2.5.0 | Direct MIT runtime dependency, exact manifest pin |
| `pip` | 26.2 | Isolated in `requirements-bootstrap.txt` |
| `ruff` | 0.16.1 | Sole flake8-style linter and formatter |
| `pylint` | 4.0.6 | Complementary static analysis |
| `mypy` | 2.3.0 | Type checker; current source tree must remain zero-error |
| `pip-audit` | 2.10.1 | Vulnerability inventory and exact-exception enforcement |
| `pip-licenses` | 5.5.5 | Complete resolved license inventory |

`requests` and `voluptuous` are supplied by Home Assistant's exact graph. `xmltodict` is supplied
through the FMI client. `python-dateutil` remains test-transitive only. The removed
`async-timeout` dependency is replaced by `asyncio.timeout` on the supported Python version.
Do not promote these packages to direct requirements unless the integration starts owning a
contract that Home Assistant or the FMI client no longer guarantees.

The stable FMI client requests `WindGust`, but the selected forecast producer publishes
`HourlyMaximumGust`. `custom_components/fmi/fmi_client.py` is the explicit private-API adapter that
adds this field to the same request and maps it by timestamp. It is guarded by request, parser,
field-precedence, timestep, and one-request contract tests. Do not remove or broaden that boundary
without rechecking current FMI metadata and upstream client behavior.

## Actions And Images

All JavaScript actions use immutable commit SHAs and executable containers use immutable registry
digests. Dependabot tracks action references, but a maintainer must review release notes,
permissions, runtime changes, and nested actions/images before accepting an update.

| Action or image | Purpose | Selected reference |
|---|---|---|
| `actions/checkout` | Repository checkout | `3d3c42e5aac5ba805825da76410c181273ba90b1` (v7.0.1) |
| `actions/github-script` | PR metadata and release publication | `3a2844b7e9c422d3c10d287c895573f7108da1b3` (v9.0.0) |
| `actions/dependency-review-action` | Native dependency diff | `a1d282b36b6f3519aa1f3fc636f609c47dddb294` (v5.0.0) |
| `github/codeql-action` | Python and Actions security analysis | `7211b7c8077ea37d8641b6271f6a365a22a5fbfa` (v4.36.0) |
| `ghcr.io/home-assistant/hassfest` | Home Assistant validation | `sha256:a77f1cf7cfc21ad626ebaae52ecb6131a45ab20223f8c2c0750bfca487aa4f05` |
| `ghcr.io/hacs/action` | HACS validation | `sha256:ea472b182558d08e50221c550fc5cdbba9e1bc1efba53f92bc4fed38e7bc56b9` |
| `docker.io/rhysd/actionlint` | Workflow syntax and static analysis | `sha256:b1934ee5f1c509618f2508e6eb47ee0d3520686341fec936f3b79331f9315667` |

Direct container invocation is intentional for hassfest and HACS: their higher-level actions use
mutable nested image tags. Only the final release job receives `contents: write`; CodeQL receives
`security-events: write` solely to upload results.

## Vulnerabilities, Licenses, And Drift

- The integration-declared FMI/geopy dependency closure has no accepted vulnerability exception.
- Home Assistant 2026.7.4 pins Pillow 12.2.0 and PyJWT 2.12.1 with known advisories. The integration
  does not import or declare them. The owner-approved private-testing exception is exact by package,
  version, and advisory ID in `.github/dependency-audit-exceptions.json`; `TODO.md` defines when it
  must be removed.
- `make audit` passes only when the complete freeze matches that exact reviewed set. New findings,
  changed affected versions, and stale exceptions fail. `make audit-raw` intentionally remains
  nonzero while the upstream pins are vulnerable.
- `make licenses` must report no unknown license. The full development graph includes copyleft
  packages selected by the FMI client and Home Assistant tooling; the inventory does not relicense
  this MIT repository. Review redistribution separately from local/CI installation.
- `make outdated` is diagnostic. Do not override resolver-controlled transitives independently of
  their Home Assistant/helper parent merely to reduce the list.
- Current stable and prerelease checks write independent full freezes, recreate clean environments
  with `--no-deps`, run `pip check`, verify the selected release channel, and execute the complete
  offline suite. A generated drift freeze is evidence for one run, not a committed support promise.

## Change Checklist

1. Verify the desired release and constraints from authoritative package/project metadata.
2. Change `requirements-direct.txt`, `requirements-bootstrap.txt`, or the integration manifest only
   at the owning boundary; never edit root `requirements.txt` manually.
3. Run `make lock` for supported direct or transitive changes and review every line of lock drift.
4. Run `make dev-build`, `make test-full`, `make lint`, `make type-check`, `make validate`,
   `make audit`, and `make licenses`.
5. Run both compatibility targets and determine whether a moving-channel failure changes the
   supported contract or only reports upstream drift.
6. Update this inventory, `DEVELOPMENT.md`, `COMPATIBILITY_SECURITY.md`, `TODO.md`, and
   `CHANGELOG.md` when their contracts or accepted risks change.

## Sources

- [Home Assistant on PyPI](https://pypi.org/project/homeassistant/)
- [`pytest-homeassistant-custom-component` on PyPI](https://pypi.org/project/pytest-homeassistant-custom-component/)
- [`fmi-weather-client` on PyPI](https://pypi.org/project/fmi-weather-client/)
- [`fmi-weather-client` source](https://codeberg.org/saaste/fmi-weather-client)
- [geopy on PyPI](https://pypi.org/project/geopy/)
