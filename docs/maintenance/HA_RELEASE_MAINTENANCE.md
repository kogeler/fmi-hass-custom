<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Home Assistant Release Maintenance

Last verified: 2026-08-08.

## Purpose And Boundaries

Use this runbook when Home Assistant publishes a new stable release. Its purpose is to refresh the
reproducible development/test graph, prove integration behavior, review transitive risk, and decide
whether users need a new FMI integration release.

Keep these four version contracts separate:

| Contract | Owner | Meaning |
|---|---|---|
| HACS installation floor | `hacs.json` `homeassistant` | Oldest Home Assistant release HACS may install this integration on |
| Reference test environment | `requirements-direct.txt` and generated `requirements.txt` | Exact graph used by local development and required CI |
| Integration runtime dependencies | `custom_components/fmi/manifest.json` `requirements` | Packages Home Assistant installs for FMI users |
| FMI integration release | `.version` and generated manifest `version` | Published tag and GitHub/HACS integration version |

A new Home Assistant stable release normally changes only the reference test environment. That
change alone is not a user-facing FMI release and is not evidence that the HACS floor must move.

## Stable Refresh Procedure

1. Inspect `git status` and read the current `.version`, `hacs.json`, `requirements-direct.txt`,
   manifest requirements, dependency-audit exceptions, and relevant `TODO.md` items. Do not mix
   unrelated work into the refresh.
2. Confirm the new stable Home Assistant release and matching
   `pytest-homeassistant-custom-component` release from authoritative project metadata. Run
   `make compatibility-stable` before changing the committed graph; its recreated environment and
   complete test run are the first compatibility signal.
3. Update only the Home Assistant/helper selections in `requirements-direct.txt`. If Home Assistant
   changes its required Python runtime, separately review and update the immutable Python image
   digest. Do not copy selected versions into tests, runtime code, image names, or `hacs.json`.
4. Run `make lock`, review every direct and transitive change in `requirements.txt`, then run
   `make dev-build`. The image build must complete with a clean `pip check`.
5. Run `make audit-raw` and classify every finding. Do not override a Home Assistant transitive pin.
   Remove fixed exceptions, add only owner-approved exact package/version/advisory exceptions, and
   record any accepted upstream block and removal trigger in `TODO.md`. `make audit` must pass.
6. Run the complete verification set: `make format-check`, `make lint`, `make type-check`,
   `make test-full`, `make test-network-block`, `make validate`, `make licenses`, and `make live`.
   Run `make compatibility-stable` again for the final graph. Run
   `make compatibility-prerelease` as an informational signal; absence or breakage of an upstream
   prerelease does not block the stable refresh unless it exposes a current contract failure.
7. Update the current inventory and only the maintenance contracts actually reverified, including
   `DEPENDENCIES.md`, `DEVELOPMENT.md`, `COMPATIBILITY_SECURITY.md`, relevant behavior documents,
   `TODO.md`, and `CHANGELOG.md`. A verification date means the stated command or behavior was
   actually checked against the new reference graph.
8. Apply the release decision below. Finish with `make version-check` and `git diff --check`, then
   confirm that the diff contains no unexplained change.

## Release Decision

Treat the refresh as **maintenance-only** when all of these remain unchanged:

- distributed integration code and other user-facing files under `custom_components/fmi/`;
- the `homeassistant` installation floor in `hacs.json`;
- the integration-owned `requirements` list in `custom_components/fmi/manifest.json`.

For a maintenance-only refresh:

- leave `.version` and the manifest `version` mirror unchanged;
- place notable maintenance, compatibility, and security notes under the top `## Unreleased`
  section of `CHANGELOG.md`;
- commit the refreshed reference requirements, generated full freeze, audit policy, and maintenance
  documentation, but do not create a tag or GitHub Release;
- require every functional, validation, live, compatibility-stable, dependency, and security check
  to pass normally.

The current **Version increment** workflow deliberately rejects an unchanged `.version`. For this
owner-approved maintenance-only path, the owner manually bypasses only that required check when
merging. Afterward, the standalone **Version increment** workflow and the version job inside the
**Release** workflow fail on the resulting `master` push; the release publish job is skipped. These
expected failures are not permission to bypass any other gate and must never be used when the
release conditions below apply.

A new FMI integration release is required when any of these changes:

- integration code or another HACS-installed user-facing file;
- the HACS Home Assistant installation floor;
- an integration-owned manifest runtime requirement.

For a release-bearing refresh, move the accumulated `Unreleased` entries into a dated
`## X.Y.Z - YYYY-MM-DD` section, increment `.version`, run `make version-sync`, and pass the normal
version-increment workflow. The trusted `master` release workflow then repeats all gates before it
may publish the tag and GitHub Release.

## Interpretation

The complete root freeze answers: "Which exact environment did maintainers test?" The HACS floor
answers: "What is the oldest Home Assistant release allowed to install this integration?" The
manifest requirements answer: "Which additional packages does the integration ask Home Assistant
to install for a user?" None of those questions, by itself, changes the FMI integration version.

When the new reference graph passes without a distributed integration change, the useful result is
repository evidence and earlier detection of upstream dependency risk. Publishing an identical FMI
payload would add no upgrade for users, so the evidence remains under `Unreleased` until a real
integration release is needed.
