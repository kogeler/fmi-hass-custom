<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Development Environment

Last verified: 2026-08-17.

## Execution Boundary

All project-aware commands except Ruff run in rootless Podman. The host Python is used only to
create `venv-lint/` and execute the exact Ruff version from `requirements-lint.txt`. It is not a
fallback for tests, Home Assistant, dependency tools, validators, or repository helpers.

`containers/toolbox/Containerfile` has two content-addressed stages:

- `lock` carries the exact wheel-only pip-tools bootstrap needed to generate its own locks;
- `dev` installs `requirements-dev.txt` with `--require-hashes`, runs `pip check`, and includes
  ShellCheck.

Project source is never copied into either image and never bind-mounted. `make/container.mk`
streams `git ls-files --cached --others --exclude-standard` as a tar archive into `/work/src` on a
private tmpfs. The image entrypoint refuses to run unless it proves a non-root UID, zero effective
capabilities, `NoNewPrivs=1`, and seccomp mode 2.

Every toolbox run uses a read-only root filesystem, an auto-allocated subordinate user namespace,
private IPC/PID/UTS/cgroup namespaces, dropped capabilities, scrubbed environment, bounded pids,
memory, file descriptors, time, and writable tmpfs only. Networking is disabled by default.
Resolution, audit, HACS, live FMI, compatibility, and outdated-package checks select the explicit
online variant. The ordinary toolbox is bounded to 8 GiB memory/swap, 512 MiB `/tmp`, and 2 GiB
`/work`; the measured Home Assistant resolver needs 16 GiB `/tmp` and 4 GiB `/work` while retaining
the same 8 GiB memory ceiling. Hassfest alone receives a private 64 MiB `/dev/shm` for its internal
multiprocessing semaphores.

The Make orchestration graph is globally serialized, including when a caller supplies `make -j`.
Pytest still uses automatic xdist workers inside its one container; serial Make orchestration avoids
multiplying those worker pools and prevents races on locks, OCI archives, and exported reports.

## Supported Commands

| Task | Command |
|---|---|
| Check host prerequisites and rootless Podman | `make doctor` |
| Build the toolbox | `make dev-build` or `make toolbox-image` |
| Build both toolbox and resolver | `make images` |
| Generate all locks | `make lock` |
| Upgrade and regenerate all locks | `make refresh-dependencies` |
| Reproduce locks without upgrades | `make freeze-check` |
| Format / check formatting | `make format` / `make format-check` |
| Ruff and Pylint | `make lint` |
| Mypy / Bandit | `make type-check` / `make bandit` |
| Python/Bash syntax / ShellCheck | `make syntax` / `make shellcheck` |
| Fast offline tests | `make test-fast` |
| Full offline coverage | `make test-full` |
| Network-block proof | `make test-network-block` |
| Confinement proof | `make confinement-test` |
| HA/actionlint/hassfest validation | `make validate` |
| HACS validation with explicit remote inputs | `make validate-hacs` |
| Reviewed/raw vulnerability checks | `make audit` / `make audit-raw` |
| License / update inventory | `make licenses` / `make outdated` |
| Build all three Dependency Submission manifests | `make dependency-snapshot` |
| Latest stable/prerelease HA | `make compatibility-stable` / `make compatibility-prerelease` |
| Public live FMI probes | `make live` |
| Complete local gate / CI quality contract | `make check` / `make ci` |

`make validator-images` pulls the three immutable external validator digests. Normal validation
then runs actionlint and hassfest offline. HACS necessarily remains online and requires
`INPUT_GITHUB_TOKEN`, `REPOSITORY`, and `REPOSITORY_REF`; it validates that exact remote revision
without receiving the checkout.

`make check` is the complete local gate excluding live FMI, moving compatibility, audit, and
license inventory. It includes the offline dependency snapshot. Its lock-reproduction step uses
the resolver's online contour; ordinary analysis, tests, and validators remain offline. HACS runs
only when its three explicit remote inputs are present and otherwise reports a skip. `make ci` adds
the reviewed dependency audit and is the quality job contract; CI keeps live FMI, HACS, dependency
review, CodeQL, and moving compatibility as separately visible jobs with their own permissions and
failure boundaries.

## Dependency Environments

Direct dependencies have exactly two PEP 621 owners:

- root `pyproject.toml` contains exact integration runtime dependencies plus the `dev` extra;
- `tools/lint/pyproject.toml` contains Ruff alone.

`make lock` runs pip-tools in the resolver container and returns output only after all three
generated root locks succeed:

- `requirements.txt`: integration runtime review/audit graph;
- `requirements-dev.txt`: runtime plus Home Assistant, its test helper, pytest, and analysis tools;
- `requirements-lint.txt`: Ruff only.

Every lock has the standard pip-compile header, exact pins, and SHA-256 hashes. The development
image deliberately permits hash-verified source distributions because Home Assistant's graph
contains `mock-open` and `PyRIC` without wheels; they build only during the rootless image build.
The host Ruff install is wheel-only. Ruff and pip-tools must never enter the development lock.
`make dependency-snapshot` checks these three locks against their PEP 621 owners inside the offline
toolbox and exports the ignored GitHub API manifest fragment to
`.artifacts/dependency-snapshot.json`.

To change a dependency:

1. Edit its exact direct requirement in the owning `pyproject.toml`. Keep root runtime requirements
   identical to `custom_components/fmi/manifest.json`.
2. Run `make refresh-dependencies` for an upgrade, or `make lock` after a direct pin change.
3. Review all three lock diffs and confirm only the intended audiences changed.
4. Run `make freeze-check`, `make dependency-snapshot`, `make test-full`, `make lint`,
   `make type-check`, `make validate`, `make audit`, and `make licenses`.
5. Run both compatibility targets for Home Assistant/runtime dependency changes.

Never edit a generated lock by hand, add a `requirements/` directory or `.in` file, create another
host virtual environment, or pass project package/version arguments directly to `pip install`.

## Parallel Tests And Artifacts

Every maintained pytest command uses `-n auto --dist=worksteal`; xdist derives the worker count
from the CPU resources visible inside the container. `PYTEST_WORKERS=<N>` is available only for
diagnosis. Offline tests retain pytest-socket and container-level `--network=none`.
Coverage configuration and the 95% threshold live only in `pyproject.toml`; `make test-full`
returns XML, Markdown, and total reports through the entrypoint's explicit export allowlist into
ignored `.artifacts/`.

Live tests also use automatic workers. A file-locked counter and two-slot semaphore under the
container's shared `/tmp` preserve the global ten-attempt budget. Compatibility creates disposable
resolver/runner virtual environments only inside the resolver container and derives its unpinned
package names from root PEP 621 metadata.

`make licenses` prints the installed graph's license inventory for maintainer review; it is not an
independent required CI job. Unknown or incompatible licensing must still block a dependency
update during that review.

OCI cache archives under `.artifacts/images/` are keyed by the exact image context. Save is atomic;
load succeeds only if the archive restores the expected content-addressed tag. `make clean` removes
known reports/caches but never the owner `tmp/` directory. `make clean-containers` removes only
containers and images owned by this repository. Failed atomic exports return a valid empty tar
stream without replacing host files, and `make coverage-report` accepts only the complete XML,
Markdown, and total-report set from an actual coverage run.
