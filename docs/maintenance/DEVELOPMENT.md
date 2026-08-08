<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Development Environment

## Reference Environment

All local commands that depend on the selected Python or Home Assistant version run in rootless
Podman. The Home Assistant 2026.8.1 reference uses Python 3.14.2; the host interpreter is never a
fallback even when its version happens to match.

`Containerfile.dev` pins the multi-architecture digest for the official Python 3.14.2 slim image. `requirements-direct.txt` is the reviewed human-maintained dependency source. Root `requirements.txt` is generated from a clean `lock` stage with `python -m pip freeze`, then installed with `--no-deps` in the development image. This is one coherent stable HA development/test reference; it does not contain a second beta or compatibility environment and does not define the HACS installation floor.

`requirements-bootstrap.txt` is the separate exact bootstrap freeze used to upgrade pip before any other installation. Normal `pip freeze` omits pip, so keeping this one-package environment separate makes the bootstrap version reviewable without embedding it in Containerfiles or workflows. Every maintained `pip install` consumes a requirements or generated constraint file; package names and versions are not passed directly by CI, Make, container recipes, or CI helpers.

The committed reference freeze uses `pytest-homeassistant-custom-component==0.13.355`, which maps exactly to Home Assistant 2026.8.1. Newer helper releases target Home Assistant prereleases and are intentionally excluded from that stable lock; the dynamic compatibility targets discover and test them without changing the reference environment.

Concrete Home Assistant and helper versions are dependency inputs and lock inventory, not test
assertions or runtime conditions. The suite establishes compatibility by exercising behavior.
`hacs.json` separately declares the oldest installable Home Assistant release and is not updated
during a routine reference-lock refresh; raise it only for a reproduced interface or runtime
incompatibility as defined in `HACS_RELEASES.md`.

Local lock/development images use stable `localhost/fmi-hass-custom-*:local` names. Image names and
the `.cache/podman-dev.stamp` path deliberately do not duplicate the Home Assistant version. The
stamp depends on the Containerfile, Makefile, bootstrap file, and complete freeze, so a normal
dependency update invalidates and rebuilds the environment automatically. `LOCAL_IMAGE_PREFIX`,
`LOCK_IMAGE`, `DEV_IMAGE`, and `DEV_STAMP` remain overridable Make variables for parallel or custom
local setups.

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

For a new Home Assistant stable release, follow the complete discovery, lock, audit, verification,
and release-decision procedure in `HA_RELEASE_MAINTENANCE.md`. The rules below describe the generic
dependency mechanics used by that runbook and by non-HA dependency updates.

The repository has three dependency-file roles:

- `requirements-direct.txt` contains reviewed exact direct selections for the reference stable
  development/test environment. Root `requirements.txt` is its generated complete transitive
  `pip freeze`.
- `requirements-bootstrap.txt` is the separate exact pip bootstrap environment. It has no
  third-party transitive packages in the selected Python image.
- `requirements-compatibility-homeassistant.txt` and
  `requirements-compatibility-direct.txt` are deliberately unpinned resolver inputs for moving
  drift checks. Each run generates a separate ignored
  `requirements-compatibility-*-resolved.txt` full freeze and recreates it before testing.

To update a direct reference dependency:

1. Verify the current stable release and its constraints from the authoritative project/package
   metadata.
2. Edit only the selected direct version in `requirements-direct.txt` (and the integration
   manifest when it is an integration-owned runtime requirement).
3. Run `make lock`. The clean Podman lock stage installs the bootstrap file and direct input, then
   replaces root `requirements.txt` with its complete `pip freeze`.
4. Review the direct change and every transitive lock change, run `make dev-build`, `pip check`
   through the image build, the full offline gates, audits, and the manual stable/prerelease
   compatibility targets.

Do not copy the newly selected Home Assistant or helper version into tests, runtime code, image
names, or `hacs.json`. The dependency files already record the exact graph. The HACS minimum changes
only when functional evidence shows that the existing floor can no longer run the integration.

No Makefile image tag or stamp name changes during a Home Assistant dependency update. If the new
Home Assistant release requires a different Python version, review and update the pinned
`PYTHON_IMAGE` digest separately before regenerating the freeze.

To refresh only transitives, leave `requirements-direct.txt` unchanged and run `make lock` in the
clean resolver stage. Review why every transitive moved and run the same verification. Never edit
root `requirements.txt` by hand. To update pip itself, change only
`requirements-bootstrap.txt`, verify its clean environment with `pip freeze --all`, then rebuild
both lock and development images; do not place a pip version in a command.

The compatibility inputs normally remain unpinned. Their generated freezes are per-run evidence,
not committed support promises; use the workflow/Make logs to diagnose a newly selected package
before deciding whether the supported direct set and committed root freeze should be upgraded.

Ordinary tests support isolated `pytest-xdist` worker processes through `PYTEST_WORKERS`, for
example `2`, `4`, or `auto`; `0` keeps the single-process default. Processes are used instead of
threads because Home Assistant tests create per-test event loops and exercise process-global
integration state. The 2026-07-31 warm-container benchmark measured 8.871 seconds for `-n 0`,
13.199 seconds for `-n 2`, and 13.586 seconds for `-n 4`, so forcing parallelism would currently
slow the suite down. Keep workers opt-in and benchmark again as the suite grows. The live suite and
deliberate network-block probe remain sequential.

`make audit` checks the complete Home Assistant development/test graph against exact reviewed
package/version/advisory exceptions and passes only when that inventory matches. It also fails when
an exception becomes stale. Home Assistant 2026.8.1 currently pins a vulnerable cryptography
release; root `TODO.md` records the owner-approved exact temporary exception and upstream removal
trigger. `make audit-raw` intentionally remains nonzero until upstream fixes the pin. Do not add
broad audit ignores or override Home Assistant's exact package pins to make it green. The separately
resolved integration-declared dependency closure has no accepted vulnerability exception; details
are in `DEPENDENCIES.md`.

The HACS validator checks a GitHub ref through the GitHub API and requires the read-only workflow
token; it cannot validate an uncommitted local working tree anonymously. CI invokes its reviewed
container digest directly rather than using the action's mutable nested image tag. Hassfest and
actionlint validate the mounted local tree and are both part of `make validate`.

## Formatting and linting

Ruff is the sole flake8-style linter and the repository formatter. Its configured rule families are `E`, `F`, `I`, `UP`, `B`, and `ASYNC`: core correctness/style, import ordering, Python upgrades, bugbear checks, and async correctness. `make lint` runs Ruff first and then Pylint as a complementary static analysis pass; Pylint does not duplicate the removed legacy toolchain.

## Layout

The distributed integration lives in `custom_components/fmi/`. Do not move runtime modules back to
the repository root or re-enable HACS `content_in_root`: the standard layout is required by the
current hassfest validation and Home Assistant custom-integration loader, and it avoids test-only
import shims.
