<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Continuous Integration And Release-Gate Maintenance

Normative workflow topology, job isolation, permissions, versioning, dependency submission, HACS
layout, and publication requirements are owned exclusively by
[the CI and release contract](../contracts/CI.md). Live-job requirements are in
[the live-test contract](../contracts/LIVE_TESTS.md).

## Maintainer Verification

For a release PR and its `master` push:

1. Confirm every expected CI job ran on the exact head SHA and stable compatibility was blocking.
2. Confirm live FMI followed quality and used no secrets.
3. Confirm separately visible HACS and hassfest jobs passed and no validator received a checkout
   bind.
4. Confirm CodeQL produced both language results and reusable CI requested no contents-write
   permission.
5. Confirm Dependency Submission accepted all three source locks and their runtime/development
   scopes appear in Dependency graph.
6. Confirm Release reused read-only CI before publish and did not submit a duplicate snapshot.
7. Confirm tag, Release name/target/notes, `.version`, manifest mirror, and changelog agree.
8. Confirm pip and GitHub-Actions Dependabot entries recognize their owned manifests.

## Recommended `master` Protection

Require only the `meta` check from the GitHub Actions app, as defined by `CIR-010`. Renaming,
adding, or removing other CI jobs then needs no ruleset change; add a new job to the `needs` list of
`meta` instead. Do not require direct-master dependency submission or the PR-body metadata job.
Keep pull requests, resolved conversations, blocked force pushes/deletions, signed commits, and the
read-only default Actions token enabled.

A required check is satisfied only after a real GitHub run reports it, so switch a ruleset to a new
check name only after that name has reported on the target pull request. Local actionlint and policy
tests prove repository intent but cannot claim branch protection or remote HACS/API state.

## Change Checklist

1. Map a workflow change to its `CIR-*` assertion before editing YAML or a helper.
2. Keep write boundaries in separate jobs/workflows and never execute untrusted PR-head code with a
   write token.
3. Add/adjust policy tests for every trigger, permission, pinned action/image, trusted-data path,
   concurrency, or publication change.
4. Run `make ci`; inspect its validation, coverage, confinement, snapshot, and reviewed-audit
   results. Use bounded live or final moving compatibility only when the affected boundary requires
   it.
