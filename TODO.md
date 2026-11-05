<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Maintenance TODO

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
