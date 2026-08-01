<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Development Environment

## Decision

All local commands that depend on the supported Python or Home Assistant version run in rootless Podman. The host currently provides Python 3.13.5, while Home Assistant 2026.7.4 requires Python 3.14.2 or newer, so host execution is not a valid fallback.

`Containerfile.dev` pins the multi-architecture digest for the official Python 3.14.2 slim image. `requirements-direct.txt` is the reviewed human-maintained dependency source. Root `requirements.txt` is generated from a clean `lock` stage with `python -m pip freeze`, then installed with `--no-deps` in the development image. This is one coherent supported stable HA development/test environment; it does not contain a second beta or compatibility environment.

`requirements-bootstrap.txt` is the separate exact bootstrap freeze used to upgrade pip before any other installation. Normal `pip freeze` omits pip, so keeping this one-package environment separate makes the bootstrap version reviewable without embedding it in Containerfiles or workflows. Every maintained `pip install` consumes a requirements or generated constraint file; package names and versions are not passed directly by CI, Make, container recipes, or CI helpers.

The committed supported freeze uses `pytest-homeassistant-custom-component==0.13.348`, which maps exactly to Home Assistant 2026.7.4. Newer helper releases target Home Assistant prereleases and are intentionally excluded from that stable lock; the dynamic compatibility targets discover and test them without changing the supported environment.

## Commands

| Task | Command |
|---|---|
| Regenerate the complete freeze | `make lock` |
| Resolve/test latest stable HA | `make compatibility-stable` |
| Resolve/test latest prerelease HA | `make compatibility-prerelease` |
| Audit dependencies with reviewed exceptions | `make audit` |
| Show the raw vulnerability inventory | `make audit-raw` |
| Build/sync the development image | `make dev-build` |
| Format | `make format` |
| Check formatting | `make format-check` |
| Lint | `make lint` |
| Type check | `make type-check` |
| Fast offline tests | `make test-fast` |
| Fast offline tests with two worker processes | `make test-fast PYTEST_WORKERS=2` |
| Full offline tests with coverage | `make test-full` |
| Full offline tests with two worker processes | `make test-full PYTEST_WORKERS=2` |
| Prove unexpected network access fails | `make test-network-block` |
| Local layout and hassfest validation | `make validate` |
| Opt-in live tests | `make live` |
| Audit known dependency vulnerabilities | `make audit` |
| Print the resolved license inventory | `make licenses` |
| Report outdated packages | `make outdated` |

Build, lock, and compatibility commands may access package registries. Formatting, linting, typing, ordinary tests, and local validation run with Podman's `--network=none`; pytest also uses `pytest-socket`. `make live` additionally accesses FMI directly.

## Dependency Update Process

The repository has three dependency-file roles:

- `requirements-direct.txt` contains reviewed exact direct selections for the supported stable
  development/test environment. Root `requirements.txt` is its generated complete transitive
  `pip freeze`.
- `requirements-bootstrap.txt` is the separate exact pip bootstrap environment. It has no
  third-party transitive packages in the selected Python image.
- `requirements-compatibility-homeassistant.txt` and
  `requirements-compatibility-direct.txt` are deliberately unpinned resolver inputs for moving
  drift checks. Each run generates a separate ignored
  `requirements-compatibility-*-resolved.txt` full freeze and recreates it before testing.

To update a direct supported dependency:

1. Verify the current stable release and its constraints from the authoritative project/package
   metadata.
2. Edit only the selected direct version in `requirements-direct.txt` (and the integration
   manifest when it is an integration-owned runtime requirement).
3. Run `make lock`. The clean Podman lock stage installs the bootstrap file and direct input, then
   replaces root `requirements.txt` with its complete `pip freeze`.
4. Review the direct change and every transitive lock change, run `make dev-build`, `pip check`
   through the image build, the full offline gates, audits, and the manual stable/prerelease
   compatibility targets.

To refresh only transitives, leave `requirements-direct.txt` unchanged and run `make lock` in the
clean resolver stage. Review why every transitive moved and run the same verification. Never edit
root `requirements.txt` by hand. To update pip itself, change only
`requirements-bootstrap.txt`, verify its clean environment with `pip freeze --all`, then rebuild
both lock and development images; do not place a pip version in a command.

The compatibility inputs normally remain unpinned. Their generated freezes are per-run evidence,
not committed support promises; use the workflow/Make logs to diagnose a newly selected package
before deciding whether the supported direct set and committed root freeze should be upgraded.

Ordinary tests support isolated `pytest-xdist` worker processes through `PYTEST_WORKERS`, for example `2`, `4`, or `auto`; `0` keeps the single-process default. Processes are used instead of threads because Home Assistant tests create per-test event loops and exercise process-global integration state. On the S07 suite, warm-container measurements were 8.871 seconds for `-n 0`, 13.199 seconds for `-n 2`, and 13.586 seconds for `-n 4`, so forcing parallelism would currently slow the suite down. Keep workers opt-in and benchmark again as the suite grows. The live suite and deliberate network-block probe remain sequential.

`make audit` checks the complete Home Assistant development/test graph and intentionally remains nonzero while the owner-approved Pillow/PyJWT exception in root `TODO.md` is open. Do not add audit ignores or override Home Assistant's exact package pins to make it green. The separately resolved integration-declared dependency closure had no known vulnerabilities in S03; details and evidence are in `docs/maintenance/DEPENDENCIES.md`.

The HACS validator checks a GitHub ref through the GitHub API and requires the read-only workflow
token; it cannot validate an uncommitted local working tree anonymously. CI invokes its reviewed
container digest directly rather than using the action's mutable nested image tag. Hassfest and
actionlint validate the mounted local tree and are both part of `make validate`.

## Formatting and linting

Ruff is the sole flake8-style linter and the repository formatter. Its configured rule families are `E`, `F`, `I`, `UP`, `B`, and `ASYNC`: core correctness/style, import ordering, Python upgrades, bugbear checks, and async correctness. `make lint` runs Ruff first and then Pylint as a complementary static analysis pass; Pylint does not duplicate the removed legacy toolchain.

## Layout

S01 moved the integration to `custom_components/fmi/`. Although HACS permits root content with `content_in_root: true`, current hassfest rejected the old checkout because the domain did not match the directory name. The standard layout passes the files to Home Assistant's normal custom-integration loader and avoids test-only import shims.

## Podman storage warning

This host reports that its configured `overlay` driver is overridden by the existing `vfs` storage database. Commands still run rootless with `runc`. S01 does not delete or reset the user's Podman storage to suppress this warning.
