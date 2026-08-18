<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Continuous Integration And Release Gates

Last verified locally: 2026-08-17.

## Workflow Topology

The repository maintains exactly three workflows:

| Workflow | Trigger | Purpose | Write permission |
|---|---|---|---|
| `ci.yml` | PR, `master` push, manual, reusable | Quality, security, live, validation, compatibility, version gates, and the trusted dependency snapshot | CodeQL gets `security-events: write`; direct-`master` dependency submission gets `contents: write` |
| `pr-body.yml` | PR open/reopen/source update | Synchronize the managed PR body block from bounded source-changelog data | `pull-requests: write` only |
| `release.yml` | `master` push | Skip an existing exact release or reuse CI and publish a new exact-version release | `contents: write` only in `publish` |

No workflow is scheduled. Every external action uses a full commit SHA with a reviewed version
comment. Executable images use immutable digests. Jobs use `ubuntu-26.04`; `.github/actionlint.yaml`
teaches actionlint 1.7.12 that official label until its embedded list catches up. Checkout
credentials are never persisted.

## Reusable CI Jobs

`ci.yml` contains these separately visible boundaries:

- **Confined quality and offline tests** sets up host Python only for hash-locked Ruff, verifies
  rootless Podman, restores content-addressed toolbox/resolver OCI archives, and runs `make ci`.
  Coverage is written only to `$GITHUB_STEP_SUMMARY`; the job has no PR write token.
- **Bounded live FMI** depends on quality and runs `make live` online without repository secrets.
- **Home Assistant and HACS validation** depends on quality, supplies the read-only GitHub token and
  exact head repository/SHA to HACS, and runs the Make validator contract. Actionlint/hassfest use a
  tar snapshot, not a checkout bind mount; HACS fetches the exact remote revision itself.
- **Dependency review** uses the native dependency-diff action for same-repository pull requests.
  Fork pull requests use the exact reviewed `make audit` fallback in the toolbox because GitHub's
  dependency-review API does not expose their dependency diff to this workflow.
- **Submit dependency graph** exists only on a direct `CI` push to `master`, depends on quality,
  builds an offline snapshot of all three hash locks through `make dependency-snapshot`, and sends
  it with GitHub's Dependency Submission API. It is skipped for PR, manual, and reusable Release
  invocations and is not a pull-request status gate.
- **CodeQL** runs `security-extended` for both Python and GitHub Actions. Only its matrix job can
  upload security events. Its explicit SARIF categories retain the historical
  `.github/workflows/codeql.yml:analyze/language:*` identities after workflow consolidation, so
  pull requests remain comparable with the `master` alert baseline; the category is an opaque
  analysis identity and does not require the former workflow file to exist.
- **Latest Home Assistant stable** resolves, freezes, recreates, checks, and tests a moving stable
  graph in the resolver container. It is blocking.
- **Latest Home Assistant prerelease** performs the same work for a newer prerelease and is
  informational. No available newer prerelease is an explicit successful skip; a real failure is
  visible through job-level `continue-on-error`.
- **Version increment** checks out the exact base and head, reads the base version as data, and
  executes the repository version helper inside the toolbox.

All project pytest paths reached by these jobs use `-n auto --dist=worksteal`, with xdist deriving
the automatic worker count from the CPUs visible to its container. The quality job's Make contract
includes lock reproduction, format/lint/type/Bandit/ShellCheck, offline coverage, network and
confinement proofs, version synchronization, actionlint/hassfest, reviewed audit, and dependency
policy/snapshot checks. License inventory remains an explicit maintainer dependency-review command
rather than a CI job. HACS, live FMI, and moving compatibility remain separate because they have
distinct network/failure boundaries.

Toolbox and resolver OCI archives are cached independently by OS, architecture, and exact context
hash. Restore verifies the expected tag. Save uses a temporary archive and rename. External
validator images are pulled only by immutable digest and are not placed in a shared writable
dependency cache.

## Trust Boundaries

Ordinary PR jobs use `pull_request`, read-only contents, no repository secrets, and no write token.
Their source is untrusted but runs only through the confined/read-only paths above.

The dependency-submission job is the only `ci.yml` job with `contents: write`. Its three-part
condition requires a `push`, `refs/heads/master`, and the direct workflow name `CI`; a reusable
invocation inherits the caller name and therefore cannot enter this boundary. Checkout credentials
are not persisted. The snapshot helper runs without network access inside the confined toolbox,
receives no token, validates every exact pin, requires its SHA-256 lock hashes, and returns only
JSON. The pinned GitHub API action revalidates the expected three-manifest shape before submitting
it with the job-scoped standard `GITHUB_TOKEN`; no PAT or repository secret is used.

`pr-body.yml` is the sole `pull_request_target` exception. It checks out the trusted default
branch, reads only the exact head SHA's `CHANGELOG.md` through the GitHub contents API, bounds that
file to 1 MB, and treats it as inert UTF-8 data. Only trusted `.github/scripts/pr_body.py` executes
in a digest-pinned minimal Python job container. The workflow re-reads the current PR body before
updating and refuses a race. It never checks out head code, installs head dependencies, interpolates
head data into shell, or receives repository-content write permission.

`release.yml` first reads `.version` from the exact pushed SHA and validates any existing Release
and lightweight tag using read-only API access. A matching published version is a successful no-op.
For a new version, the workflow calls the same `ci.yml` from that pushed commit. Only after every
reusable job succeeds does `publish` receive `contents: write`, generate release notes via the
toolbox, and create the exact-version tag and Release. It refuses conflicting tags, targets, names,
notes, draft state, or prerelease state and never rewrites an existing conflict.

## Recommended `master` Protection

After the new workflow has run once, select the actual GitHub-rendered names corresponding to:

- `CI / Confined quality and offline tests`
- `CI / Bounded live FMI`
- `CI / Home Assistant and HACS validation`
- `CI / Dependency review`
- `CI / CodeQL (actions)`
- `CI / CodeQL (python)`
- `CI / Latest Home Assistant stable`
- `CI / Version increment`

Do not require `CI / Latest Home Assistant prerelease`, `CI / Submit dependency graph`, or the
PR-body metadata job. The submission job is deliberately absent from PR runs. Keep pull requests,
resolved conversations, blocked force pushes/deletions, and read-only default Actions token
enabled; the workflow grants its one write permission at job scope. Dependency graph, Dependabot
alerts, and security updates remain owner-controlled repository settings.

Exact check labels exist only after a real GitHub run. Local actionlint, policy tests, and Make
verification cannot claim that remote branch rules or HACS API access have been applied.

## Maintainer Verification

For a release PR and its `master` push:

1. Confirm every expected CI job ran on the exact head SHA and stable compatibility was blocking.
2. Confirm live FMI followed quality and used no secrets.
3. Confirm HACS reported the exact source repository/ref and no validator received a checkout bind.
4. Confirm CodeQL produced both language results and only direct-master dependency submission gained
   the documented CI contents-write permission.
5. Confirm `CI / Submit dependency graph` accepted `requirements.txt`, `requirements-dev.txt`, and
   `requirements-lint.txt`, then confirm those source locations appear in Dependency graph.
6. Confirm the Release run reused CI before its publish job and did not submit a duplicate snapshot.
7. Confirm the tag, Release name/target, notes, `.version`, manifest mirror, and dated changelog
   section agree.
8. Confirm the pip and GitHub-Actions Dependabot entries recognize their new manifests/locks.
