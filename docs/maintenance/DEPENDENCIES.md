<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Dependency Ownership And Review

Normative manifest ownership, lock, resolver, confinement, audit, and Dependency Submission
requirements are owned exclusively by [the dependency contract](../contracts/DEPENDENCIES.md).
Workflow permissions and publication boundaries are in [the CI contract](../contracts/CI.md).

The authoritative direct selections live only in root `pyproject.toml` and
`tools/lint/pyproject.toml`; the integration manifest is a synchronized runtime mirror and the
three generated locks record resolved selections. Do not copy that mutable inventory into
documentation.

## Dependency Change Procedure

1. Change only the owning PEP 621 project manifest; synchronize integration runtime requirements
   into `custom_components/fmi/manifest.json` when applicable. Decide any HACS-floor and release
   metadata change before final verification.
2. Run `make refresh-dependencies` or `make lock` and review every changed direct/transitive pin,
   hash, source distribution, and audience.
3. Run `make dev-build` and `make freeze-check`; the image build includes `pip check`.
4. Run `make dependency-snapshot` and inspect all three generated manifest counts/scopes.
5. Run `make audit-raw`, classify every finding, update only owner-approved exact exceptions and
   their `TODO.md` removal trigger, then require `make audit` to pass.
6. Run `make licenses`; unknown or incompatible licensing blocks the update even though this is a
   maintainer-reviewed inventory rather than a separate CI job.
7. Run format/lint/type/Bandit, full offline coverage, validators, network/confinement proofs,
   version checks, and live FMI if the runtime boundary changed.
8. Run moving stable/prerelease compatibility once, last, only after the candidate and every
   cheaper required gate are complete, as required by `AGENTS.md`.
9. After either moving target runs, do not change code, tests, dependency/release metadata, locks,
   or compatibility tooling; a required change invalidates the affected evidence under the
   protocol in `AGENTS.md`.

## Resolver Notes

Some Home Assistant transitive packages may publish source archives only. Their hashes and locally
built wheels are reviewed as part of the generated dev graph; removing a transitive package from
the lock would falsify the reference environment. The resolver bootstrap is intentionally small
because it cannot depend on the lock it generates; `DEP-003` is its complete normative boundary.

## References

- [Python XML security guidance](https://docs.python.org/3.14/library/xml.html)
- [`xmltodict` project metadata](https://pypi.org/project/xmltodict/)
- [`xmltodict` security policy](https://github.com/martinblech/xmltodict/security)
