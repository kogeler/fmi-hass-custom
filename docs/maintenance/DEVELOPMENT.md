<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Development Environment

## Decision

All local commands that depend on the supported Python or Home Assistant version run in rootless Podman. The host currently provides Python 3.13.5, while Home Assistant 2026.7.4 requires Python 3.14.2 or newer, so host execution is not a valid fallback.

`Containerfile.dev` pins the multi-architecture digest for the official Python 3.14.2 slim image. `requirements-direct.txt` is the reviewed human-maintained dependency source. Root `requirements.txt` is generated from a clean `lock` stage with `python -m pip freeze`, then installed with `--no-deps` in the development image. This makes the resolver input and the complete installed graph reviewable separately.

Both container stages and the test workflow upgrade the base image's bootstrap installer to `pip==26.2` before installing dependencies. Normal `pip freeze` output omits this bootstrap package.

The current test helper is `pytest-homeassistant-custom-component==0.13.348`, which maps exactly to Home Assistant 2026.7.4. Versions 0.13.349 and 0.13.350 target Home Assistant 2026.8 prereleases and are intentionally excluded from the stable environment.

## Commands

| Task | Command |
|---|---|
| Regenerate the complete freeze | `make lock` |
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

Build and lock commands may access package registries. Formatting, linting, typing, ordinary tests, and local validation run with Podman's `--network=none`; pytest also uses `pytest-socket`. `make live` is the only test target with container networking and will have no selected tests until S12.

Ordinary tests support isolated `pytest-xdist` worker processes through `PYTEST_WORKERS`, for example `2`, `4`, or `auto`; `0` keeps the single-process default. Processes are used instead of threads because Home Assistant tests create per-test event loops and exercise process-global integration state. On the S07 suite, warm-container measurements were 8.871 seconds for `-n 0`, 13.199 seconds for `-n 2`, and 13.586 seconds for `-n 4`, so forcing parallelism would currently slow the suite down. Keep workers opt-in and benchmark again as the suite grows. The live suite and deliberate network-block probe remain sequential.

`make audit` checks the complete Home Assistant development/test graph and intentionally remains nonzero while the owner-approved Pillow/PyJWT exception in root `TODO.md` is open. Do not add audit ignores or override Home Assistant's exact package pins to make it green. The separately resolved integration-declared dependency closure had no known vulnerabilities in S03; details and evidence are in `docs/maintenance/DEPENDENCIES.md`.

The official HACS action validates a GitHub ref through the GitHub API and requires `GITHUB_TOKEN`; it cannot validate an uncommitted local working tree anonymously. It is included in the PR workflow and is not emulated or bypassed locally. Hassfest does validate the mounted local tree and is part of `make validate`.

## Formatting and linting

Ruff is the sole flake8-style linter and the repository formatter. Its configured rule families are `E`, `F`, `I`, `UP`, `B`, and `ASYNC`: core correctness/style, import ordering, Python upgrades, bugbear checks, and async correctness. `make lint` runs Ruff first and then Pylint as a complementary static analysis pass; Pylint does not duplicate the removed legacy toolchain.

## Layout

S01 moved the integration to `custom_components/fmi/`. Although HACS permits root content with `content_in_root: true`, current hassfest rejected the old checkout because the domain did not match the directory name. The standard layout passes the files to Home Assistant's normal custom-integration loader and avoids test-only import shims.

## Podman storage warning

This host reports that its configured `overlay` driver is overridden by the existing `vfs` storage database. Commands still run rootless with `runc`. S01 does not delete or reset the user's Podman storage to suppress this warning.
