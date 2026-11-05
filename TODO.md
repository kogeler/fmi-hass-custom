<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Maintenance TODO

## Submit the integration to the default catalog

- Status: `IN_PROGRESS`; updated 2026-11-05.
- Context: Home Assistant 2026.11 builds HACS in as the Marketplace. The default catalog is still
  [`hacs/default`](https://github.com/hacs/default), and both HACS and the Marketplace read it. Its
  review runs the current HACS action (including the `license` and `integration_categories` checks),
  hassfest from the moving `latest` image, and a check against the domains of the next Core release.
- Done in the repository: Marketplace installation guidance, the **FMI Weather** display name, the
  manifest integration category, current validator images, and the Home Assistant 2026.11
  reference.
- Interim state: Home Assistant publishes the `pytest-homeassistant` test helper with each release,
  but only its 2026.11 betas were on PyPI when the reference moved. The reference therefore pins
  the newest 2026.11 beta of both packages. When the matching stable helper is published, pin both
  to that stable release, regenerate the locks, and rerun the gates. The blocking stable
  compatibility job fails until that helper exists.
- Remaining work:
  1. Publish the release through the normal workflow and confirm that its `HACS validation` log
     reports every current check passed without `ignore` or warnings, and that `Hassfest` passed.
  2. The owner installs that release as a custom repository through **Settings > Marketplace** on
     Home Assistant 2026.11, both as a fresh install and as an upgrade taken over from HACS, and
     runs the release smoke checks: setup by map and by place, reload, forecasts and sensors,
     optional sources, reconfiguration with preserved entity IDs, and diagnostics privacy. The
     catalog pull request waits for this result.
  3. Recheck that `fmi` is not a Core domain in `https://next.home-assistant.io/integrations.json`,
     that the repository is not already listed or removed in `hacs/default`, and that no other
     catalog repository uses the `fmi` domain.
  4. Prepare the `hacs/default` pull request from a personal fork: one alphabetically sorted
     `"kogeler/fmi-hass-custom"` entry in `integration`, and the template completed with links to
     that release and to its successful `HACS validation` and `Hassfest` jobs. Only the owner submits
     it; do not request reviews.
  5. After the merge and the next catalog data update, verify that the repository can be found and
     installed from the Marketplace, then make catalog search the primary installation path in
     `docs/USER_GUIDE.md` and remove this item.

## Restore current pip and pip-tools in the resolver bootstrap

- Status: `BLOCKED_UPSTREAM`; workaround applied by the repository owner's decision on 2026-10-14.
  Marker: `TODO(pip-tools-json-hashes)` in `containers/toolbox/Containerfile`.
- Defect: pip-tools 7.6.1 and 7.6.2 derive the JSON API base from `https://pypi.org/simple` as
  `https://pypi.org/`, so `_get_project()` requests `https://pypi.org/<name>/json`, receives 404,
  and silently returns no PyPI digests. `_get_req_hashes()` then downloads and hashes every release
  file. Measured on 2026-10-14: the dev lock fetched 3,674 files (4.80 GiB), spending about 5 of 6
  minutes on hashing; `make freeze-check` paid the same cost. Generated locks were byte-identical,
  so correctness was unaffected.
- Workaround: the resolver stage pins pip-tools 7.6.0, the last release that uses pip's
  `PackageIndex.pypi_url` (`https://pypi.org/pypi/<name>/json`). It calls
  `make_requirement_preparer()` without the keyword-only `allow_editables` argument required since
  pip 26.2, so pip is held at 26.1.2. This affects only `make lock`, `make refresh-dependencies`,
  and `make freeze-check`; the toolbox environment and moving compatibility virtual environments
  are unaffected.
- Accepted residual risk: pip 26.1.2 still has
  [CVE-2026-13346](https://osv.dev/vulnerability/GHSA-qwm4-qh6w-59xr), fixed in pip 26.2, which
  requires a malicious package index. The confined resolver uses only the default PyPI index.
  CVE-2026-8643 is already fixed in 26.1.2.
- Check for a fix: inspect the newest pip-tools release on [PyPI](https://pypi.org/project/pip-tools/)
  and its [changelog](https://github.com/jazzband/pip-tools/releases). In
  `piptools/repositories/pypi.py`, `_get_project()` must request `https://pypi.org/pypi/<name>/json`
  for the default index. No upstream issue was found on 2026-10-14; search the
  [issue tracker](https://github.com/jazzband/pip-tools/issues) for `_get_true_base_from_index_url`.
- Removal: pin the fixed pip-tools with the newest compatible pip, run
  `make lock LOCK_UPGRADE='-v -v'`, and confirm that the log contains no `Hashing <file>` lines for
  PyPI packages and that the lock content is unchanged. Then run `make freeze-check` and the
  dependency-policy tests, remove the Containerfile marker and this item. The 16 GiB resolver
  `/tmp` in `make/container.mk` was sized for the download path; re-measure before reducing it.
