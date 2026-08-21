<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Development Environment

The normative Make/toolbox/lock/confinement boundary is owned by
[the dependency contract](../contracts/DEPENDENCIES.md), especially `DEP-003` through `DEP-005`.
Workflow use of that environment is owned by [the CI contract](../contracts/CI.md). `AGENTS.md` is
the canonical command policy for agents.

## Supported Commands

| Task | Command |
|---|---|
| Check host prerequisites and rootless Podman | `make doctor` |
| Build the toolbox | `make dev-build` or `make toolbox-image` |
| Inspect locked FMI/Home Assistant package contracts | `make reference-contracts` |
| Build toolbox and resolver | `make images` |
| Generate/reproduce locks | `make lock` / `make freeze-check` |
| Upgrade direct/transitive selections | `make refresh-dependencies` |
| Format / formatting check | `make format` / `make format-check` |
| Ruff and Pylint | `make lint` |
| Mypy | `make type-check` |
| Bandit / syntax / ShellCheck | `make bandit` / `make syntax` / `make shellcheck` |
| Fast/full offline tests | `make test-fast` / `make test-full` |
| Prove socket blocking / confinement | `make test-network-block` / `make confinement-test` |
| Validators | `make validator-images`, then `make validate` |
| Dependency audit/licenses/snapshot | `make audit` / `make licenses` / `make dependency-snapshot` |
| Stable/prerelease compatibility | `make compatibility-stable` / `make compatibility-prerelease` |
| Public live FMI | `make live` |
| Complete local/CI graph | `make check` / `make ci` |

## Working Procedure

Use the smallest supported Make target while iterating. `make validate` expects the immutable
validator images prepared by `make validator-images`. `make check` is the complete repository gate
graph excluding live FMI, moving compatibility, reviewed audit, and license inventory, and assumes
those validator images already exist. `make ci` prepares the validator images, runs `make check`,
and adds the reviewed online audit. HACS runs locally only when its explicit remote
repository/token/ref inputs exist.

All pytest targets use automatic xdist workers. Set `PYTEST_WORKERS=<N>` only for diagnosis. Do not
run competing Make graphs against shared locks, image archives, or exported artifacts.

Use `make lock` for reproduction and `make refresh-dependencies` for an intentional upgrade. Review
the generated files; do not edit them. Moving compatibility creates disposable environments and is
subject to the final-only protocol in `AGENTS.md`.

Coverage and Dependency Submission outputs under `.artifacts/` are derived ignored evidence.
Remove local generated caches with `make clean` when necessary; do not commit them.
