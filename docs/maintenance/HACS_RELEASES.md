<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# HACS Repository And Release Maintenance

Normative HACS layout, release version, metadata synchronization, workflow gate, and publication
requirements are owned by [the CI and release contract](../contracts/CI.md), especially `CIR-005`,
`CIR-006`, and `CIR-008`.

## Release Preparation

1. Read the current release only from `.version` and verify the manifest is its generated mirror.
2. Decide whether the change is release-bearing under `HA_RELEASE_MAINTENANCE.md`.
3. For a release-bearing change, increment `.version`, run `make version-sync`, and add one matching
   dated changelog section with user-facing notes.
4. Run `make version-check` and `make release-notes`; inspect the generated notes and full-changelog
   link.
5. Complete all local, live, dependency, security, and final moving-compatibility gates before the
   owner pushes.
6. Do not create a tag or Release manually. Verify the trusted direct-`master` workflow and its
   exact resulting publication.

## Remote Repository Settings

The owner reviews remote settings before release because they are not stored in the checkout:

- repository remains public with issues enabled and appropriate Home Assistant/HACS topics;
- `master` protection uses the required checks from `CI.md`;
- Actions default token remains read-only;
- only the dedicated dependency-submission and final release jobs receive contents-write;
- the separately visible HACS job validates the exact head repository/ref.

A release-branch push cannot publish. HACS consumes the latest published GitHub Release/tag rather
than treating the moving hidden default branch as an ordinary downloadable version.

## References

- [HACS repository and version rules](https://www.hacs.xyz/docs/publish/start/)
- [HACS integration layout and releases](https://www.hacs.xyz/docs/publish/integration/)
- [Home Assistant custom integration layout](https://developers.home-assistant.io/docs/creating_integration_file_structure/)
- [GitHub release API](https://docs.github.com/en/rest/releases/releases#create-a-release)
- [GitHub workflow-token behavior](https://docs.github.com/en/actions/concepts/security/github_token)
