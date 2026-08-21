<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Continuous Integration And Release Contract

## Assertions

### `CIR-001` — Workflow topology is minimal, event-driven, and immutable

**Contract:** The repository MUST contain only the reviewed CI, dependency-submission, PR-body, and
release workflows; none MAY use a schedule. External actions MUST use full commit SHAs and
executable images MUST use immutable digests. Checkout credentials MUST NOT persist.

**Evidence:**

- [`test_workflow_set_is_minimal_event_driven_and_fully_pinned`](../../tests/test_ci_policy.py) — `tests/test_ci_policy.py::test_workflow_set_is_minimal_event_driven_and_fully_pinned`

### `CIR-002` — Quality and networked gates have separate failure boundaries

**Contract:** The aggregate quality job MUST run through `make ci`, which acquires immutable
validator images, executes the complete repository check graph, and enforces the reviewed online
dependency audit. Bounded live FMI, hassfest, HACS, dependency review, CodeQL, stable
compatibility, prerelease compatibility, and version checks MUST remain separately visible jobs.
Stable compatibility MUST block; prerelease MUST remain informational.

**Evidence:**

- [`test_ci_uses_make_rootless_podman_and_independent_image_caches`](../../tests/test_ci_policy.py) — `tests/test_ci_policy.py::test_ci_uses_make_rootless_podman_and_independent_image_caches`
- [`test_ci_preserves_hacs_security_and_compatibility_gates`](../../tests/test_ci_policy.py) — `tests/test_ci_policy.py::test_ci_preserves_hacs_security_and_compatibility_gates`

### `CIR-003` — CI write permissions are job-scoped and minimal

**Contract:** Reusable CI MUST request read-only contents and MUST NOT request `contents: write`.
Only the CodeQL matrix MAY receive `security-events: write`; dependency submission and final
release publication MAY receive `contents: write` only in their dedicated jobs.

**Evidence:**

- [`test_ci_write_permissions_are_confined_to_codeql`](../../tests/test_ci_policy.py) — `tests/test_ci_policy.py::test_ci_write_permissions_are_confined_to_codeql`
- [`test_dependency_submission_has_a_separate_trusted_write_boundary`](../../tests/test_ci_policy.py) — `tests/test_ci_policy.py::test_dependency_submission_has_a_separate_trusted_write_boundary`
- [`test_release_reuses_ci_and_writes_only_in_publish_job`](../../tests/test_ci_policy.py) — `tests/test_ci_policy.py::test_release_reuses_ci_and_writes_only_in_publish_job`

### `CIR-004` — PR-body automation never executes pull-request code

**Contract:** `pr-body.yml` MUST be the sole `pull_request_target` workflow. It MUST execute trusted
default-branch code, treat bounded head `CHANGELOG.md` content as inert data, recheck update races,
and MUST NOT check out/execute head code or receive repository-content write permission.

**Evidence:**

- [`test_pr_body_is_the_only_pull_request_target_write_boundary`](../../tests/test_ci_policy.py) — `tests/test_ci_policy.py::test_pr_body_is_the_only_pull_request_target_write_boundary`
- [`test_workflow_never_checks_out_or_executes_head_code`](../../tests/test_pr_body.py) — `tests/test_pr_body.py::test_workflow_never_checks_out_or_executes_head_code`
- [`test_rejects_body_above_github_limit`](../../tests/test_pr_body.py) — `tests/test_pr_body.py::test_rejects_body_above_github_limit`

### `CIR-005` — Release version has one human-maintained owner

**Contract:** `.version` MUST be canonical `X.Y.Z` and is the only human-maintained release version;
manifest version MUST be its synchronized mirror. A release-bearing candidate MUST have a greater
version than its exact base and a matching non-empty dated changelog section. A same-version
workflow-only recovery MAY instead compare against the latest published stable version only while
that candidate version has no Release, and MUST still be greater than the published version.

**Evidence:**

- [`test_rejects_noncanonical_versions`](../../tests/test_release_version.py) — `tests/test_release_version.py::test_rejects_noncanonical_versions`
- [`test_requires_manifest_to_match_version`](../../tests/test_release_version.py) — `tests/test_release_version.py::test_requires_manifest_to_match_version`
- [`test_requires_matching_nonempty_changelog_section`](../../tests/test_release_version.py) — `tests/test_release_version.py::test_requires_matching_nonempty_changelog_section`
- [`test_requires_strict_version_increment`](../../tests/test_release_version.py) — `tests/test_release_version.py::test_requires_strict_version_increment`
- [`test_version_job_compares_exact_base_and_head_through_make`](../../tests/test_ci_policy.py) — `tests/test_ci_policy.py::test_version_job_compares_exact_base_and_head_through_make`

### `CIR-006` — Publication reuses exact gated state and never rewrites conflict

**Contract:** A version-incrementing direct `master` push MUST pass reusable CI before its sole
write-enabled publish job creates an exact lightweight tag and published stable Release. Matching
existing publication MUST be a read-only no-op; conflicting tag/target/title/notes/state MUST fail
without moving or rewriting it. Release notes MUST use only the matching changelog section and a
tag-stable full-changelog link.

**Evidence:**

- [`test_release_reuses_ci_and_writes_only_in_publish_job`](../../tests/test_ci_policy.py) — `tests/test_ci_policy.py::test_release_reuses_ci_and_writes_only_in_publish_job`
- [`test_release_notes_use_only_matching_section_and_full_link`](../../tests/test_release_version.py) — `tests/test_release_version.py::test_release_notes_use_only_matching_section_and_full_link`
- [`test_repository_metadata_is_release_ready`](../../tests/test_release_version.py) — `tests/test_release_version.py::test_repository_metadata_is_release_ready`

### `CIR-007` — Dependency submission is a direct-master-only write boundary

**Contract:** Dependency submission MUST trigger only on direct `master` push, generate three
validated manifests offline without a token, and submit them with only its job-scoped standard
`GITHUB_TOKEN`. PR, manual, and reusable release invocation MUST NOT enter this boundary.

**Evidence:**

- [`test_dependency_submission_has_a_separate_trusted_write_boundary`](../../tests/test_ci_policy.py) — `tests/test_ci_policy.py::test_dependency_submission_has_a_separate_trusted_write_boundary`
- [`test_snapshot_contains_all_three_exact_lock_graphs`](../../tests/test_dependency_snapshot.py) — `tests/test_dependency_snapshot.py::test_snapshot_contains_all_three_exact_lock_graphs`

### `CIR-008` — HACS distribution metadata and payload layout remain stable

**Contract:** HACS metadata MUST retain the reviewed repository name/country, hidden default
branch, rendered README, current installation floor, and standard `custom_components/fmi` payload.
Only a published GitHub Release tag MAY represent an offered integration version; distributed code
MUST import from a clean copied integration tree.

**Evidence:**

- [`test_hacs_repository_metadata_and_brand`](../../tests/test_distribution.py) — `tests/test_distribution.py::test_hacs_repository_metadata_and_brand`
- [`test_standard_custom_component_layout`](../../tests/test_layout.py) — `tests/test_layout.py::test_standard_custom_component_layout`
- [`test_copied_distribution_imports_from_empty_config`](../../tests/test_distribution.py) — `tests/test_distribution.py::test_copied_distribution_imports_from_empty_config`

### `CIR-009` — OCI caches are independent, atomic, and verified

**Contract:** Toolbox and resolver OCI archives MUST use separate OS-, architecture-, and
content-addressed cache keys. Saving MUST publish an archive only after a successful temporary
write, and loading MUST verify the expected content-derived image tag. Immutable external
validator images MUST NOT enter those writable caches.

**Evidence:**

- [`test_ci_uses_make_rootless_podman_and_independent_image_caches`](../../tests/test_ci_policy.py) — `tests/test_ci_policy.py::test_ci_uses_make_rootless_podman_and_independent_image_caches`
- [`test_image_archives_are_content_addressed_atomic_and_verified`](../../tests/test_dependency_policy.py) — `tests/test_dependency_policy.py::test_image_archives_are_content_addressed_atomic_and_verified`
- [`test_workflow_set_is_minimal_event_driven_and_fully_pinned`](../../tests/test_ci_policy.py) — `tests/test_ci_policy.py::test_workflow_set_is_minimal_event_driven_and_fully_pinned`
