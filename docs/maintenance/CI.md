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

After a workflow has rendered its real check names, require the quality, live FMI, hassfest, HACS,
dependency review, both CodeQL languages, latest stable compatibility, and version-increment jobs.
Do not require informational prerelease compatibility, direct-master dependency submission, or the
PR-body metadata job. Keep pull requests, resolved conversations, blocked force pushes/deletions,
and read-only default Actions token enabled.

Exact check labels are remote state and can be selected only after a real GitHub run. Local
actionlint and policy tests prove repository intent but cannot claim branch protection or remote
HACS/API state.

## Change Checklist

1. Map a workflow change to its `CIR-*` assertion before editing YAML or a helper.
2. Keep write boundaries in separate jobs/workflows and never execute untrusted PR-head code with a
   write token.
3. Add/adjust policy tests for every trigger, permission, pinned action/image, trusted-data path,
   concurrency, or publication change.
4. Run `make ci`; inspect its validation, coverage, confinement, snapshot, and reviewed-audit
   results. Use bounded live or final moving compatibility only when the affected boundary requires
   it.
