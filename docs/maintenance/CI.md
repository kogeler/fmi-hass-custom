<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Continuous Integration And Release Gates

Last verified: 2026-08-01.

## Workflow Topology

| Workflow | Trigger | Purpose | Effective write permission |
|---|---|---|---|
| `pr-body.yml` | PR open/reopen/source update | Synchronize a managed PR-body block from the source branch's latest changelog section | `pull-requests: write` only |
| `version.yml` | Pull requests; `master` pushes; manual | Require `.version` to increase relative to the exact base tree and validate manifest/changelog synchronization | None |
| `ci.yml` | Pull requests; `master` pushes; manual; reusable from release | Formatting, Ruff/Pylint, mypy, frozen dependency check, offline HA suite, distribution smoke, 95% coverage, then bounded live FMI probes | None |
| `validate.yml` | Pull requests; `master` pushes; manual; reusable from release | Version/layout smoke, actionlint, digest-pinned hassfest, and digest-pinned HACS validation | None |
| `dependency-review.yml` | Pull requests | Use native dependency diff for independent repositories or exact-exception frozen audit for forks | None |
| `codeql.yml` | Pull requests; `master` pushes; manual | Security-extended CodeQL for Python and GitHub Actions workflow languages | `security-events: write` only for results |
| `release.yml` | Push to `master` | Re-run version, CI, and validation gates; publish exact-version tag/release | `contents: write` only in final publish job |
| `compatibility.yml` | Pull requests; `master` pushes; manual | Independently resolve, freeze, recreate, and test the latest stable and latest available prerelease HA graphs | None |

Quality, version, validation, dependency-review, and CodeQL workflows use `pull_request`; they
receive neither repository secrets nor a write token. Checkout credentials are not persisted.
Required jobs install the complete committed supported graph with `--no-deps` and run `pip check`.
The event-driven and manually triggered compatibility jobs instead detect resolver drift: neither
workflow job contains an HA, test-helper, FMI-client, geopy, or pip version. Stable compatibility
fails its workflow and is a recommended required PR check. Prerelease compatibility uses job-level
`continue-on-error` so an upstream beta can report a visible failure without blocking the
supported stable release contract.

The CI job keeps the ordinary coverage suite deterministic and socket-blocked, then runs the four
bounded `live` probes as a separate final step with no secrets. CI, validation, CodeQL,
compatibility, and version workflows all run directly for pull requests and `master` pushes and
can be dispatched manually from a selected branch. On every `master` push, `release.yml` also
invokes the same reusable CI and validation definitions and independently repeats the version
check, so publication waits for gates tied to that exact Release run. This deliberate repetition is
required because GitHub Actions cannot express `needs` across independent workflow runs. An FMI
service/network outage now blocks merge and release by owner decision. No file under
`.github/workflows/` may declare a `schedule` trigger.

The manual version check compares the selected branch with `master` by default and permits an
explicit base branch or commit. On a `master` push it compares the pushed commit with
`github.event.before`, matching the release gate. Dependency review stays PR-only. GitHub's
dependency-diff API returns `403` for fork repositories, so `dependency-review.yml` calls the
native action only when `github.event.repository.fork` is false. On this fork it installs the
committed full freeze and runs `.github/scripts/dependency_audit.py`; the helper permits only the
exact package/version/advisory tuples in `.github/dependency-audit-exceptions.json`, fails on a new
finding, and also fails when an exception becomes stale. PR-body synchronization remains tied to
trusted PR metadata events, and release publication remains tied exclusively to a
version-incrementing `master` push.

`pr-body.yml` is the single isolated `pull_request_target` exception because fork PR tokens on the
ordinary event cannot update their PR body. It receives no secrets and only `contents: read` plus
`pull-requests: write`. It checks out the trusted default branch without a head ref, reads only the
exact head SHA's `CHANGELOG.md` through SHA-pinned `actions/github-script`, and treats that file as
bounded inert UTF-8 data. Only the trusted default-branch `.github/scripts/pr_body.py` executes;
the workflow never checks out head code, installs head dependencies, interpolates head content
into a shell command, or writes repository contents/cache.

The helper copies the source changelog's first `##` section, so normal development PRs use
`Unreleased` while release branches use their dated version section. Hidden markers delimit the
generated block. Manual text outside the block is retained, and the block refreshes on PR open,
reopen, and source updates. Invalid/empty sections, ambiguous markers, and bodies above the GitHub
limit fail visibly instead of erasing the existing body. The workflow also re-reads the current PR
before writing and refuses to overwrite a manual edit made while synchronization was running.

No dependency cache is written. The pinned container layers and small frozen install already keep
the jobs bounded, while avoiding a writable cache shared between untrusted pull requests and
trusted release jobs.

## Dynamic Compatibility Resolution

`compatibility.yml` has two independent jobs. `Latest Home Assistant stable` resolves the newest
non-prerelease HA first, temporarily constrains that exact resolver result, and selects the newest
test helper and integration dependencies compatible with it. `Latest Home Assistant prerelease`
selects the newest published HA prerelease independently of the helper's possibly lagging exact HA
metadata. It permits only that single helper-to-HA metadata mismatch; every other `pip check`
failure remains fatal, and the test suite must pass.

Both jobs use `.github/scripts/compatibility.py`. The helper installs only from requirement or
constraint files. It resolves in a temporary venv, writes the complete transitive result using
`pip freeze` to `requirements-compatibility-*-resolved.txt`, creates a second empty venv, installs
the generated freeze with `--no-deps`, verifies the requested release channel and dependency
metadata, and runs pytest only in that recreated environment. Generated drift freezes are ignored
locally because their purpose is to describe that single run, not to replace the committed
supported lock.

## Immutable Dependencies

All external JavaScript actions use full commit SHAs. All executable containers use registry
digests. Hassfest and HACS are invoked directly from reviewed image digests, removing the mutable
nested image tags found in S14. Actionlint uses its multi-architecture release digest. Dependabot
tracks both Python inputs and GitHub Actions references; grouped PRs are limited to non-major
updates.

Every repository-authored CI helper is Python under `.github/scripts/`. GitHub API orchestration is
the single exception to Python-only helper logic: inline bodies of the native, SHA-pinned
`actions/github-script` use its pre-authenticated Octokit client for release publication and PR
metadata. Workflows contain no `curl`, `gh api`, or repository-authored GitHub HTTP client.

## Recommended `master` Protection

Configure a branch ruleset for `master` with pull requests required, force pushes/deletions
blocked, conversations resolved, and these checks required:

- `Version increment / Version increment`
- `CI / Quality, offline, and live tests`
- `Home Assistant and HACS validation / Layout and metadata`
- `Home Assistant and HACS validation / Workflow syntax`
- `Home Assistant and HACS validation / Hassfest`
- `Home Assistant and HACS validation / HACS`
- `Dependency review / Dependency review`
- `CodeQL / Analyze (actions)`
- `CodeQL / Analyze (python)`
- `Compatibility / Latest Home Assistant stable`

GitHub exposes exact check labels only after each new workflow has run once. If the UI renders a
slightly different qualified label, select the run whose workflow/job names match the list above.
Do not require `Compatibility / Latest Home Assistant prerelease`: it is an early-warning signal
for an unsupported moving target. Live FMI is part of the required CI job and must not be split
into an optional workflow.
Do not make PR-body synchronization a required merge check; its write permission and metadata-only
purpose are deliberately separate from code quality gates.

The post-push release version check deliberately fails direct or multi-commit pushes that do not
increase `.version`, but a failed post-push workflow cannot remove a commit already accepted by
GitHub. Required PR checks and branch protection are therefore the preventive control.

## First Pull-Request Evidence

PR #1 at `ff00b62eeb94875a7729e585a00e9c6f94da2027` exercised every new pull-request
workflow on 2026-08-01. CI including live FMI, both compatibility jobs, both CodeQL analysis jobs,
layout, workflow syntax, and hassfest passed. The run exposed four real integration/repository
gaps: the first-release helper assumed the post-migration manifest path, GitHub dependency review
does not support forks, a legacy debug script logged precise coordinate-derived data, and HACS
required Issues plus repository topics. The code gaps received regression fixes. Issues and topics
`home-assistant`, `hacs`, and `integration` were configured with the owner-authorized `gh` session;
rerunning only the failed HACS job then passed. The remaining corrected jobs require a new owner
commit/push before remote confirmation.

## Owner Verification

After S16 is complete and the finished release branch is merged/pushed to `master`:

1. Confirm every standalone branch check appears for both the release PR and `master` push, and
   record the exact required-check labels.
2. Confirm the `master` Release run passes its parallel version, CI/live, and validation gates
   before the publish job starts.
3. Confirm tag/Release `1.0.0` points to the finished release commit and release notes match the
   `CHANGELOG.md` section plus full-changelog link.
4. Add this repository to HACS as a custom Integration and verify `1.0.0` installs to
   `<config>/custom_components/fmi/`.
5. Confirm `Compatibility` ran on the release PR and `master` push, then run it manually from a
   custom branch once; verify both jobs identify the then-current stable/prerelease, create and
   reinstall their separate full freezes, and use no secrets.
6. Confirm the bounded live step ran after offline coverage on both the release PR and `master` run.
7. Enable the recommended branch ruleset and keep the repository Actions default token read-only.
8. Open or update a later test PR and confirm its managed body block matches the first changelog
   section from that PR's exact source SHA while any manual text remains unchanged.

The initial PR workflows and HACS repository settings are verified as described above. Branch
protection, Actions token defaults, the post-fix PR rerun, and the published Release remain owner
verification steps.

Do not merge or push the partial S15 state to `master`: S16 still owns the user guide, final report,
README restructuring, and final clean verification for the same `1.0.0` release. S15 and S16 may
remain separate commits on the release branch because the gate compares the completed branch with
the older version on `master`.

The `1.0.0` PR itself cannot use `pr-body.yml` if the workflow is not already present in `master`:
GitHub loads `pull_request_target` workflows only from the default branch. This is a one-time
bootstrap limitation; PR-body synchronization becomes active after the finished release reaches
`master`.

## Authoritative References

- Reusable workflows: <https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows>
- Workflow token and fork behavior: <https://docs.github.com/en/actions/concepts/security/github_token>
- Secure pull-request triggers:
  <https://docs.github.com/en/actions/reference/security/securely-using-pull_request_target>
- Repository contents API used to read the exact head changelog:
  <https://docs.github.com/en/rest/repos/contents>
- Pull request API used to update only the PR body:
  <https://docs.github.com/en/rest/pulls/pulls#update-a-pull-request>
- CodeQL GitHub Actions queries:
  <https://docs.github.com/en/code-security/reference/code-scanning/codeql/codeql-queries/actions-built-in-queries>
- GitHub dependency review API and its fork limitation:
  <https://docs.github.com/en/rest/dependency-graph/dependency-review>
- Dependabot configuration:
  <https://docs.github.com/en/code-security/dependabot/dependabot-version-updates/configuration-options-for-the-dependabot.yml-file>
