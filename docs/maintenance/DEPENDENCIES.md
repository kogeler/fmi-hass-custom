<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Dependency Inventory

Inventory date: 2026-07-31; S14 audit refreshed 2026-08-01. Versions were checked against package metadata from PyPI and action metadata from the upstream GitHub repositories. The supported test environment is Home Assistant 2026.7.4 on Python 3.14.2.

## Resolution model

- `custom_components/fmi/manifest.json` contains only packages the integration requires and Home Assistant Core does not already guarantee.
- `requirements-direct.txt` is the reviewed input for the stable Home Assistant test environment and development tools.
- Root `requirements.txt` is generated only by `make lock` in a clean Podman stage. Its 173 exact entries are the complete `pip freeze` result, not a manually selected subset.
- `Containerfile.dev` upgrades the base image's installer to `pip==26.2` before resolving or installing packages. `pip` is a bootstrap tool and is omitted by normal `pip freeze` output.

## Runtime and platform selections

| Dependency | Purpose / class | Previous | Newest stable | Selected | License | Compatibility decision and source |
|---|---|---:|---:|---:|---|---|
| Python | HA runtime; direct platform | 3.14.2 | 3.14.2 | 3.14.2 | PSF | Home Assistant 2026.7.4 requires Python >=3.14.2. The official slim image remains pinned by multi-architecture digest. [Image](https://hub.docker.com/_/python) |
| Home Assistant | Test host; direct development | 2026.7.4 | 2026.7.4 | 2026.7.4 | Apache-2.0 | Current stable release; prereleases are excluded from the supported environment. [PyPI](https://pypi.org/project/homeassistant/) |
| `pytest-homeassistant-custom-component` | HA test harness; direct development | 0.13.348 | 0.13.350 | 0.13.348 | MIT | 0.13.348 pins HA 2026.7.4. Release 0.13.350 pins HA 2026.8.0b2; current HA beta b3 is one prerelease ahead of its helper, so neither represents the stable support matrix. [PyPI](https://pypi.org/project/pytest-homeassistant-custom-component/) |
| `fmi-weather-client` | FMI API; direct runtime | 0.7.0 | 1.0.0 | 1.0.0 | GPL-3.0 | Exact manifest pin. Public models, errors, and async methods remain compatible. S06 found that 1.0.0 still requests forecast `WindGust`, which FMI returns as NaN for the selected producer; the integration now uses a narrow contract-tested adapter to add `HourlyMaximumGust` to the same request and normalize the existing model. [PyPI](https://pypi.org/project/fmi-weather-client/), [source](https://codeberg.org/saaste/fmi-weather-client) |
| `geopy` | Reverse geocoding/distance; direct runtime | >=2.1.0 | 2.5.0 | 2.5.0 | MIT | Exact manifest pin because integration modules import it directly. [PyPI](https://pypi.org/project/geopy/) |
| `python-dateutil` | Legacy time-zone conversion; removed direct runtime | unpinned | 2.9.0.post0 | Test transitive only | Apache-2.0 / BSD-3-Clause | S08 replaced integration imports with Home Assistant's current timezone helpers. It remains in the complete freeze through `freezegun`, selected by the Home Assistant pytest helper. [PyPI](https://pypi.org/project/python-dateutil/) |
| `async-timeout` | Legacy timeout helper; removed | unpinned / 5.0.1 resolved | 5.0.1 | removed | Apache-2.0 | Replaced by `asyncio.timeout`, available in the supported Python. No installed dependency still requires this package. [PyPI](https://pypi.org/project/async-timeout/) |
| `requests` | FMI-client/config-flow exception boundary; Core-supplied transitive | >=2.32.4 | 2.34.2 | 2.34.2 | Apache-2.0 | HA 2026.7.4 requires exactly 2.34.2 and the FMI client requires `~=2.32`; it remains transitive rather than a direct input. S09 moved integration-owned lightning/sea-level HTTP to Home Assistant's shared aiohttp session, leaving only the FMI-client exception boundary. [PyPI](https://pypi.org/project/requests/) |
| `voluptuous` | Config schema; Core-supplied transitive | unpinned | 0.16.0 | 0.15.2 | BSD-3-Clause | Integration imports it, but HA 2026.7.4 guarantees exactly 0.15.2. Selecting 0.16.0 would violate Core metadata. [PyPI](https://pypi.org/project/voluptuous/) |
| `xmltodict` | FMI XML parser; FMI transitive | >=0.14.2 | 1.0.4 | 1.0.4 | MIT | Not imported by the integration; FMI client 1.0.0 requires `~=1.0`. Removed from direct inputs. [PyPI](https://pypi.org/project/xmltodict/) |

The FMI 1.0.0 PyPI source distribution was inspected because the upstream Codeberg API returned HTTP 503 during S03. It contains no changelog file. S06 later compared the installed source, current upstream branch, wind-gust availability evidence, and FMI's current producer metadata: the stable client still requests forecast `WindGust`, while the edited Scandinavia producer publishes `HourlyMaximumGust`. `custom_components/fmi/fmi_client.py` is therefore an explicit private-API boundary protected by offline request, parser, field-precedence, and timestep contract tests; it does not add another FMI request.

## Development tools

| Dependency | Purpose | Previous | Newest stable / selected | License | Source and note |
|---|---|---:|---:|---|---|
| `pip` | Container installer | 25.3 from base image | 26.2 | MIT | Upgraded explicitly in both Podman stages and CI. [PyPI](https://pypi.org/project/pip/) |
| `mypy` | Type checking | 2.3.0 | 2.3.0 | MIT | Existing 18-error production baseline remains visible; no ignores added. [PyPI](https://pypi.org/project/mypy/) |
| `pip-audit` | Vulnerability inventory | not present | 2.10.1 | Apache-2.0 | New direct audit tool. [PyPI](https://pypi.org/project/pip-audit/) |
| `pip-licenses` | License inventory | not present | 5.5.5 | MIT | New direct license tool. [PyPI](https://pypi.org/project/pip-licenses/) |
| `pylint` | Complementary static analysis | 4.0.6 | 4.0.6 | GPL-2.0-or-later | Continues to pass at 10.00/10. [PyPI](https://pypi.org/project/pylint/) |
| `ruff` | Formatter and primary linter | 0.16.1 | 0.16.1 | MIT | Ruff remains the sole flake8-style tool. [PyPI](https://pypi.org/project/ruff/) |

## GitHub Actions

All action references are immutable commit SHAs. Branch-tip actions do not have a current corresponding release tag, so their reviewed branch and date are recorded.

| Action | Purpose | Previous | Newest reviewed | Selected | License | Source / reason |
|---|---|---|---|---|---|---|
| `actions/checkout` | Repository checkout | v4.2.2 / `11bd719...` | v7.0.1 | `3d3c42e5aac5ba805825da76410c181273ba90b1` | MIT | Latest release on 2026-07-31. [Releases](https://github.com/actions/checkout/releases) |
| `home-assistant/actions/hassfest` | HA validation | `ab220296...` | master 2026-07-30 | `ab22029681aa532bfe7de5774a9972d67bfbd2c0` | Apache-2.0 | Current master; no stable release tag is used by upstream guidance. [Commit](https://github.com/home-assistant/actions/commit/ab22029681aa532bfe7de5774a9972d67bfbd2c0) |
| `hacs/action` | HACS validation | `1ebf01c...` | main 2026-06-08 | `1ebf01c408f29afcb6406bd431bc98fd8cbb15aa` | MIT | Current main is newer than latest tag 22.5.0 and was already pinned. [Commit](https://github.com/hacs/action/commit/1ebf01c408f29afcb6406bd431bc98fd8cbb15aa) |

S14 verified the top-level action references remain current and immutable. The selected hassfest composite action nevertheless runs unpinned `ghcr.io/home-assistant/hassfest`, and the selected HACS Docker action declares `ghcr.io/hacs/action:main`. This nested mutability is documented as a Medium supply-chain finding for S15 replacement with digest-pinned execution; current workflow permissions remain `contents: read` and no repository secrets are provided.

## Outdated transitive report

`make outdated` reports 24 packages below their individual newest releases. Every item is resolver-controlled rather than an independently selectable direct dependency:

| Constraint owner | Packages reported outdated | Reason not overridden |
|---|---|---|
| Home Assistant/Core closure | `acme`, `astral`, `boto3`, `botocore`, `cryptography`, `pillow`, `PyJWT`, `pyOpenSSL`, `snitun`, `uv`, `voluptuous` | HA 2026.7.4 or an HA dependency selects these versions. Independent overrides make `pip check` fail or create an unsupported Core graph. |
| HA pytest helper | `aiohasupervisor`, `coverage`, `license-expression`, `numpy`, `pipdeptree`, `pytest`, `pytest-github-actions-annotate-failures`, `syrupy`, `tqdm`, `unidiff` | Helper 0.13.348 pins its tested versions exactly. |
| Resolver compatibility | `astroid`, `pydantic_core` | Latest versions are outside the selected Pylint/Pydantic constraints. |
| Stable HA matrix | `pytest-homeassistant-custom-component` | Newer helper releases require Home Assistant 2026.8 prereleases. |

## Vulnerability and license results

- The integration-declared dependency closure (`fmi-weather-client`, `geopy`, and their resolved transitives) reports no known vulnerability.
- The complete HA development/test graph reports 28 advisory rows for two HA-pinned packages: Pillow 12.2.0 (fixed in 12.3.0) and PyJWT 2.12.1 (fixed in 2.13.0). The advisories include High-severity findings. Home Assistant 2026.7.4 requires both affected versions exactly.
- The repository owner accepted this temporary risk on 2026-07-31 for private testing. The exception is tracked in root `TODO.md`; fixed versions must not be forced over Core's exact metadata.
- Upgrading the container installer from pip 25.3 to 26.2 removed the installer advisories found in the first audit.
- `make licenses` reports no unknown license. Copyleft packages in the full test graph include the selected GPL-3.0 FMI client and packages brought in by Home Assistant/test tooling; the inventory describes development/test installation and does not relicense this repository.
- S14 re-ran all three inventories. The runtime-only FMI/geopy closure remains clean, current beta HA 2026.8.0b3 selects fixed Pillow/PyJWT versions, and the stable owner exception remains necessary until those pins reach a stable HA/helper pair.

Representative advisory evidence: [Pillow PYSEC-2026-2253](https://osv.dev/vulnerability/PYSEC-2026-2253), [PyJWT PYSEC-2026-179](https://osv.dev/vulnerability/PYSEC-2026-179), and [pip PYSEC-2026-196](https://osv.dev/vulnerability/PYSEC-2026-196). All links and versions in this document were last checked on 2026-08-01.
