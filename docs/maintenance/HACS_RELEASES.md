<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# HACS Repository And Releases

Last verified: 2026-08-17.

## What HACS Installs

This is a standard single-integration repository:

```text
custom_components/
  fmi/
    __init__.py
    manifest.json
    brand/icon.png
    ...runtime modules and translations...
hacs.json
README.md
```

HACS recognizes `custom_components/fmi/` as the integration directory and installs it as
`<Home Assistant config>/custom_components/fmi/`. Root `hacs.json` supplies the HACS display
name, country, and minimum supported Home Assistant release. It intentionally does not set
`content_in_root`, `zip_release`, or `filename`: the repository already uses the native layout,
and a normal GitHub source archive contains everything HACS needs.

The repository can be added in HACS as a custom repository with category **Integration** and
repository URL `https://github.com/kogeler/fmi-hass-custom`. Inclusion in HACS's default catalog
is a different, optional process; a custom repository does not require default-catalog approval.

## Home Assistant Minimum

The `homeassistant` value in `hacs.json` is an installation floor, not the current development or
test target. Preserve it during routine Home Assistant, test-helper, and dependency-lock updates.
A successful test run against a newer Home Assistant release proves compatibility with that tested
environment; it does not prove that the previous minimum stopped working.

Raise the floor only after reproducing a real incompatibility at the existing minimum, such as an
integration API or Python runtime contract that the integration must use and the older release does
not provide. Document the broken behavior, regression coverage, user impact, and release change.
Do not raise it merely to mirror the newest stable release or the versions selected in root
`pyproject.toml`.

Tests and runtime code must not assert concrete Home Assistant, test-helper, or HACS-minimum version
numbers. Offline and Home Assistant tests establish functional compatibility; the HACS validator
checks the metadata contract. Exact development/test selections belong in root PEP 621 and the
generated `requirements-dev.txt` graph, while `hacs.json` remains the single declaration of the
installation floor.

## Version Source

Root `.version` is the only human-maintained project version. It must contain one stable SemVer
value in exact `X.Y.Z` form, with no `v` prefix or prerelease suffix.

Some consumers require committed version mirrors. `custom_components/fmi/manifest.json` is such a
generated mirror, not a second source of truth. Run:

```bash
make version-sync
make version-check
```

The first command copies `.version` into the manifest. The second proves that `.version`, the
manifest, and the matching `CHANGELOG.md` section agree. CI executes the same Python helper from
`.github/scripts/version.py`.

Do not copy the current numeric project version into `README.md`, `docs/USER_GUIDE.md`,
`AGENTS.md`, installation commands, or similar current-facing prose. Those documents link to the
[latest published GitHub Release](https://github.com/kogeler/fmi-hass-custom/releases/latest),
which is authoritative for users. Concrete project versions belong only in `.version`, its
generated manifest mirror, dated changelog history, Git tags/releases, and tests or historical
records that explicitly exercise a version contract.

## Change And Release Contract

Every dated release section that contains a new user-facing capability must begin with a
`### User-facing features` subsection. This first block is reserved for behavior that a user can
directly discover, enable, configure, or use, and it describes the benefit before implementation
details. Examples include a new setup path, a new option or entity, or a new way to interact with
an existing entry. CI changes, dependency updates, refactors, test infrastructure, and maintainer
documentation do not belong in this block.

The remaining entries follow under the conventional `Added`, `Changed`, `Fixed`, and `Security`
subsections as applicable. Fixes that restore an existing contract remain under `Fixed` unless they
also deliver a distinct new capability. Do not add an empty user-facing subsection or manufacture a
feature for a maintenance-only release. This ordering matters because the matching changelog section
is reused verbatim for the pull-request managed block and the published GitHub Release notes.

A release-bearing pull request to `master` must:

1. Increase `.version` above the exact target commit's version.
2. Run `make version-sync` so the committed manifest mirror matches.
3. Add a non-empty `## X.Y.Z - YYYY-MM-DD` section to `CHANGELOG.md`, with any user-facing
   capabilities in the first `### User-facing features` subsection.
4. Pass the **Version increment** job and every other required job in reusable CI.

A Home Assistant reference-only refresh is the narrow exception. When integration code and other
HACS-installed user-facing files, the `hacs.json` installation floor, and manifest runtime
requirements are all unchanged, follow `HA_RELEASE_MAINTENANCE.md`: retain `.version` and the
manifest version mirror, put notable notes under `Unreleased`, and do not publish an identical
integration payload. The owner manually bypasses only the expected version-increment failure; all
other gates remain mandatory.

The first `.version` release compares against the legacy manifest version `0.6.2`. Later releases
compare against the base tree's `.version`. Two checkouts are used so the version helper does not
depend on Git being installed in the supported Python container.

On every push to `master`, `.github/workflows/release.yml` first reads `.version` from the exact
pushed SHA and looks up its GitHub Release using full-SHA-pinned `actions/github-script` with
read-only contents permission. If that version already has a correctly named published stable
release and its exact lightweight tag still points to the release's recorded target commit, all
remaining release-workflow jobs are skipped successfully. Missing, moved, annotated, or conflicting
tags fail the release-state job. If no release exists, the workflow requires reusable CI, which
contains version, Home Assistant/HACS validation, live, security, and compatibility jobs. Only
after they succeed does its final job receive `contents: write`.
The action creates both:

- a lightweight tag named exactly like `.version`, in `X.Y.Z` form;
- a published GitHub Release with the same title and tag.

The release body contains only the matching version section from `CHANGELOG.md`, followed by a
tag-stable link to the complete changelog. The publication action refuses an existing conflicting
tag, target commit, title, notes, or published state without moving the tag or rewriting the
release. Later maintenance pushes use the earlier read-only release-state check and do not rewrite
an already published release or its notes.

HACS uses the tag name of the latest published GitHub Release as the remote version and offers
recent releases to users. A tag without a published Release is not sufficient for this behavior.
An unchanged-version maintenance PR still fails the CI version job, which the owner explicitly
bypasses under the narrow maintenance policy. Its release workflow succeeds after the
existing-release check and does not run version, CI, validation, or publication; its `Unreleased`
notes remain for the next release-bearing change.

## Remote Repository Settings

The owner must retain these GitHub settings because they are not stored in the checkout:

- the repository remains public, with issues enabled;
- the description states that this is an FMI weather integration for Home Assistant;
- repository topics include `home-assistant`, `hacs`, and `integration`;
- `master` protection uses the required checks listed in `docs/maintenance/CI.md`;
- Actions' default token permission remains read-only; the workflow grants write only to the
  release publication job.

Before each release, verify these remote settings and the HACS validation job instead of assuming
that checkout-local metadata is sufficient. A push to a release branch runs its pull-request checks
but does not publish; only the version-incrementing `master` push activates the trusted release
workflow.

## Authoritative References

- HACS general repository and version rules: <https://www.hacs.xyz/docs/publish/start/>
- HACS integration layout and release behavior: <https://www.hacs.xyz/docs/publish/integration/>
- Home Assistant custom integration layout and brand directory:
  <https://developers.home-assistant.io/docs/creating_integration_file_structure/>
- GitHub release API and permission model:
  <https://docs.github.com/en/rest/releases/releases#create-a-release>
- GitHub workflow token behavior: <https://docs.github.com/en/actions/concepts/security/github_token>
