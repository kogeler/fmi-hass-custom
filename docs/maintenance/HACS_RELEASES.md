<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# HACS Repository And Release Maintenance

Normative HACS layout, release version, metadata synchronization, workflow gate, and publication
requirements are owned by [the CI and release contract](../contracts/CI.md), especially `CIR-005`,
`CIR-006`, and `CIR-008`.

## Release Preparation

1. Read the current release only from `.version` and verify the manifest is its generated mirror.
2. Decide whether the change is release-bearing under `HA_RELEASE_MAINTENANCE.md`.
3. For a release-bearing change, increment `.version`, run `make version-sync`, and add one matching
   dated changelog section whose entries follow the classes below.
4. Run `make version-check` and `make release-notes`; inspect the generated notes and full-changelog
   link.
5. Complete all local, live, dependency, security, and final moving-compatibility gates before the
   owner pushes.
6. Do not create a tag or Release manually. Verify the trusted direct-`master` workflow and its
   exact resulting publication.

## Changelog Classes

The changelog section becomes the published Release body, so classify each entry by its effect on
an installed integration rather than by the files it touches. Use only the classes that have
entries, in this order:

- `User-facing features`: new or changed behavior a user can see or use, such as entities, states,
  attributes, forecasts, configuration, options, or dashboard guidance.
- `Fixed`: corrected behavior that users could observe as wrong.
- `Runtime operation`: no visible UI or feature change, but the installed integration runs
  differently or is newly verified to keep running — Home Assistant platform compatibility,
  runtime dependency behavior, FMI request cadence, timeouts, availability, recovery, or resource
  use. State whether runtime code changed or the existing code was verified unchanged.
- `Security`: vulnerability, privacy, or disclosure changes. State whether the installed
  integration or only the development and test environment is affected.
- `Development and maintenance`: repository, test, CI, lock, toolchain, documentation, and
  type-only changes with no effect on a running installation, including shipped files whose
  runtime behavior is unchanged.

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
