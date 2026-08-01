<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# HACS Repository And Releases

Last verified: 2026-08-01.

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

## Change And Release Contract

Every pull request to `master`, including documentation and Dependabot changes, must:

1. Increase `.version` above the exact target commit's version.
2. Run `make version-sync` so the committed manifest mirror matches.
3. Add a non-empty `## X.Y.Z - YYYY-MM-DD` section to `CHANGELOG.md`.
4. Pass the dedicated **Version increment** workflow as well as normal CI/validation.

The first `.version` release compares against the legacy manifest version `0.6.2`. Later releases
compare against the base tree's `.version`. Two checkouts are used so the version helper does not
depend on Git being installed in the supported Python container.

On every push to `master`, `.github/workflows/release.yml` repeats the version comparison, then
requires the reusable CI and Home Assistant/HACS validation workflows. Only after they succeed
does its final job receive `contents: write` and call full-SHA-pinned `actions/github-script`.
The action creates both:

- a lightweight tag named exactly like `.version`, for example `1.0.0`;
- a published GitHub Release with the same title and tag.

The release body contains only the matching version section from `CHANGELOG.md`, followed by a
tag-stable link to the complete changelog. A rerun accepts an existing release only when its tag,
target commit, title, notes, and published state already match exactly; conflicts fail without
moving the tag or rewriting the release.

HACS uses the tag name of the latest published GitHub Release as the remote version and offers
recent releases to users. A tag without a published Release is not sufficient for this behavior.

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
