<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Maintenance TODO

## Replace vulnerable Home Assistant-pinned packages

- Status: `BLOCKED_UPSTREAM`; temporary risk accepted by the repository owner on 2026-07-31.
- Home Assistant 2026.7.4 requires `pillow==12.2.0` and `PyJWT==2.12.1` exactly. Current High-severity advisories are fixed in Pillow 12.3.0 and PyJWT 2.13.0.
- The FMI integration does not import or declare either package. Its manifest dependency closure passes `pip-audit`; the affected packages enter the development/test environment through Home Assistant Core.
- Do not override Home Assistant's exact pins locally. Doing so makes `pip check` fail and tests an environment that Home Assistant does not support.

Close this item when a stable Home Assistant release and its matching `pytest-homeassistant-custom-component` release select fixed versions:

1. Update the Home Assistant/helper pair in `requirements-direct.txt`.
2. Run `make lock` and `make dev-build`.
3. Run `make audit-raw`; after it reports no findings, remove the matching entries from `.github/dependency-audit-exceptions.json`.
4. Run `make audit`, the full offline suite, and `make validate`, then remove the temporary exception from `docs/maintenance/DEPENDENCIES.md`. The policy audit intentionally fails when an exception becomes stale.

Evidence rechecked 2026-08-01: [Pillow advisory](https://osv.dev/vulnerability/PYSEC-2026-2253), [PyJWT advisory](https://osv.dev/vulnerability/PYSEC-2026-179), and Home Assistant 2026.7.4/2026.8.0b3 package metadata. The beta pins the fixed releases, but stable does not yet.

## Replace public Nominatim before broader distribution

- Status: `ACCEPTED_PRIVATE_TESTING`; reviewed 2026-08-01.
- Optional lightning enrichment sends public FMI strike coordinates, not configured home coordinates, to OSMF's public Nominatim service. It is cached, single-threaded, attributed, identified by User-Agent, limited to one lookup per update, and globally limited to 4 requests/minute.
- OSMF discourages periodic app traffic at scale and requires applications to be able to switch services. The current owner-only test deployment is deliberately small, but the implementation is not a foundation for an assumed public user base.

Before broader distribution, choose and verify one of these outcomes:

1. Remove reverse-geocoded address enrichment and retain a local/public FMI-data fallback.
2. Use an owner-controlled Nominatim instance or proxy.
3. Add a provider boundary that can be switched without an integration release and remains opt-in.

Evidence: [OSMF Nominatim usage policy](https://operations.osmfoundation.org/policies/nominatim/) and `docs/maintenance/COMPATIBILITY_SECURITY.md`.
