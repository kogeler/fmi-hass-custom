<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Home Assistant Release Maintenance

Use this runbook when Home Assistant publishes a stable release. Normative reference/floor and
moving-channel rules are in
[the compatibility contract](../contracts/COMPATIBILITY_SECURITY.md); dependency ownership is in
[the dependency contract](../contracts/DEPENDENCIES.md); version/publication rules are in
[the CI and release contract](../contracts/CI.md).

## Stable Refresh Procedure

1. Inspect `git status`, `.version`, `hacs.json`, root PEP 621 metadata, manifest requirements,
   audit exceptions, and relevant `TODO.md` items. Keep unrelated work out of the refresh.
2. Confirm the new stable Home Assistant and matching test-helper releases from authoritative
   metadata. Update only their direct PEP 621 selections. If Python requirements changed, review the
   immutable Python image separately. Do not copy versions into runtime code, tests, or `hacs.json`.
3. Run `make lock`, review every changed pin/hash, then run `make dev-build` and
   `make freeze-check`.
4. Run `make audit-raw`, classify every finding, update only exact owner-approved exceptions and
   their removal triggers, then require `make audit` and `make licenses` review.
5. Update only affected maintenance rationale/runbooks and current contract assertions/evidence,
   then apply the release decision below. Complete any `.version`, manifest mirror, and changelog
   changes before verification.
6. Run all cheaper final gates: format, lint, type, Bandit, full offline coverage, network block,
   confinement, validation, Dependency Submission snapshot, bounded live FMI, and
   `make version-check`.
7. Only after the candidate and every preceding gate are complete, run
   `make compatibility-stable` once and `make compatibility-prerelease` once as the final moving
   gates. Reuse their results while code/tests/dependencies/tooling remain unchanged, as required by
   `AGENTS.md`.
8. Do not edit the candidate after those moving gates. Inspect `git status` and `git diff --check`
   only; if inspection requires a correction, apply it and repeat the relevant cheaper gates, then
   repeat a moving gate only when the invalidation rules in `AGENTS.md` require it.

## Release Decision

Treat a reference refresh as maintenance-only when distributed integration/user-facing files, the
HACS installation floor, and manifest runtime requirements are unchanged. Leave `.version` and its
manifest mirror unchanged, put notable maintenance notes under `Unreleased`, and require all normal
gates. The owner may bypass only the CI version-increment check for this explicitly reviewed path;
the existing published Release remains a read-only workflow no-op.

A new integration release is required when distributed/user-facing integration files, the HACS
floor, or an integration-owned runtime requirement changes. Move accumulated notes into a matching
dated version section, increment `.version`, run `make version-sync`, and use the normal trusted
release workflow.

An incremented but still unpublished release train may retain its version for workflow-only
recovery. After publication, unchanged-version work returns to the maintenance-only rule above.

## Interpretation

The dev lock answers which exact graph maintainers tested; the HACS floor answers which Home
Assistant release may install; manifest requirements answer what Home Assistant installs for FMI;
`.version` answers which integration payload is published. A change to one does not silently change
the meaning of another.
