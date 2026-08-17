<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Dependency Ownership And Review

Last verified: 2026-08-17.

## Authoritative Inputs And Generated Outputs

| File or field | Ownership |
|---|---|
| Root `pyproject.toml` dependencies | Exact integration runtime dependencies; identical to manifest requirements |
| Root `pyproject.toml` `dev` extra | Exact direct Home Assistant reference, test, audit, and analysis tools |
| `tools/lint/pyproject.toml` | Exact Ruff-only host environment |
| `requirements.txt` | Generated hashed runtime closure for review, audit, and dependency graph |
| `requirements-dev.txt` | Generated hashed toolbox closure |
| `requirements-lint.txt` | Generated hashed Ruff-only closure |
| Toolbox `lock` stage | Exact self-hosting pip-tools bootstrap; the only inline install exception |

There are no maintained `.in` files, `requirements/` directory, compatibility inputs, bootstrap
requirements file, or additional lock environment. `pip-compile` headers are retained so
Dependabot can update a direct manifest and regenerate the matching graph. Root lock files are
generated mode `0644` and are never hand-edited.

The runtime lock is not installed into Home Assistant and does not replace Home Assistant's own
constraints. After HACS or a manual installation provides the integration files, Home Assistant
installs the exact requirements from `custom_components/fmi/manifest.json`. `hacs.json`
independently owns the minimum supported Home Assistant release.

## Reviewed Direct Selections

| Dependency | Selected version | Reason |
|---|---:|---|
| `fmi-weather-client` | 1.0.0 | FMI WFS runtime client |
| `geopy` | 2.5.0 | Optional lightning reverse geocoding |
| `xmltodict` | 1.0.4 | Maintained Expat-based FMI XML parser with entity declarations disabled |
| `homeassistant` | 2026.8.1 | Stable reference test environment, not the HACS floor |
| `pytest-homeassistant-custom-component` | 0.13.355 | Matching Home Assistant test harness |
| `bandit[toml]` | 1.9.4 | Runtime Python security analysis |
| `mypy` | 2.3.0 | Type analysis |
| `packaging` | 26.3 | Directly imported dependency-policy parsing |
| `pip-audit` | 2.10.1 | Vulnerability inventory and exact exception enforcement |
| `pip-licenses` | 5.5.5 | Installed graph license inventory |
| `pylint` | 4.0.6 | Complementary static analysis |
| `pytest` | 9.0.3 | Test runner |
| `pytest-asyncio` | 1.4.0 | Async test execution |
| `pytest-cov` | 7.1.0 | Branch coverage |
| `pytest-socket` | 0.8.0 | Deterministic socket blocking |
| `pytest-xdist` | 3.8.0 | Automatic parallel workers |
| `ruff` | 0.16.1 | Sole host formatter/linter |

The resolver bootstrap pins pip 26.2.1, setuptools 84.0.0, pip-tools 7.6.1, build 1.5.0,
click 8.4.2, packaging 26.3, pyproject-hooks 1.2.0, and wheel 0.48.0. It is installed wheel-only
inside the resolver image because a resolver cannot depend on a lock it generates.

`requests` and `voluptuous` remain Home Assistant contracts. `xmltodict` is direct because the
integration imports it, explicitly selects its secure parsing mode, and therefore owns its
version/availability contract. It was already present through `fmi-weather-client`, so promoting it
does not add another installed runtime package. The integration does not declare or import
`defusedxml`. It still appears in the complete development lock only as a dependency of
Home Assistant's `py-serializable` graph; removing that transitive would falsify the reference
environment rather than remove it from the distributed integration.

The selected `xmltodict` release supports Python 3.14, publishes a platform-independent wheel
through PyPI Trusted Publishing, disables entity declarations by default, and has a maintained
security policy for the latest 1.x line. Integration calls also set `disable_entities=True`
explicitly and refuse Expat versions older than 2.7.2. The reference Python 3.14.2 image contains
Expat 2.7.3. External DTD declarations are not resolved because Expat has no external-resource
handler in this parsing path; tests verify both internal/external entity rejection and inert
external DTD behavior.

## Hashes, Source Distributions, And Drift

All three locks use `--generate-hashes`. The dev image installs with `--require-hashes` and runs
`pip check`. Home Assistant's selected graph contains the source-only `mock-open==1.4.0` and
`PyRIC==0.1.6.3`; their source archives are hash-verified and their pure-Python wheels are built
only inside the rootless image build. The host Ruff environment uses both `--require-hashes` and
`--only-binary=:all:`.

`make freeze-check` recompiles without `--upgrade` and compares non-comment lock content. Use
`make refresh-dependencies` for latest compatible versions. Moving stable/prerelease compatibility
does not create another committed environment: it derives unpinned runtime/HA/helper names from
root PEP 621, freezes and recreates a temporary graph inside the resolver container, and exports
ignored per-run evidence under `.artifacts/compatibility/`.

## Vulnerabilities, Licenses, And External References

`make audit` audits the installed dev graph and accepts only the exact package/version/advisory
tuples in `.github/dependency-audit-exceptions.json`. New findings and stale exceptions fail.
`make audit-raw` intentionally remains nonzero while Home Assistant pins the documented vulnerable
cryptography release. The integration-owned xmltodict/FMI/geopy runtime closure has no accepted
exception. `make licenses` prints the installed graph for maintainer review; an unknown or
incompatible license must block the dependency change even though the command is an inventory,
not a separate automated CI gate.

JavaScript actions use full commit SHAs. Python, actionlint, hassfest, and HACS images use immutable
registry digests. Dependabot has one weekly pip entry for root PEP 621/locks and one weekly
GitHub-Actions entry; it does not track a Docker ecosystem.

## Change Checklist

1. Change only the direct PEP 621 owner and synchronize manifest requirements when runtime changes.
2. Run `make refresh-dependencies` or `make lock`; review every changed pin and hash audience.
3. Run `make freeze-check`, build the dev image, and confirm `pip check`.
4. Run format/lint/type/Bandit, full offline coverage, validators, reviewed audit, and licenses.
5. Run stable and prerelease compatibility for HA/runtime dependency changes.
6. Keep the HACS minimum unchanged unless the old floor has a reproduced integration failure.
7. A manifest runtime requirement change is release-bearing: update `.version`, synchronize the
   manifest mirror, and add the matching dated changelog section.

## XML Parser References

- [Python 3.14 XML security guidance](https://docs.python.org/3.14/library/xml.html)
- [`xmltodict` 1.0.4 project metadata and release provenance](https://pypi.org/project/xmltodict/)
- [`xmltodict` security policy](https://github.com/martinblech/xmltodict/security)
