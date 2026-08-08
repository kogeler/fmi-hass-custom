<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Maintenance TODO

## Resolve vulnerable Home Assistant-pinned cryptography

- Status: `BLOCKED_UPSTREAM`; temporary risk accepted by the repository owner on 2026-08-08.
- Home Assistant 2026.8.1 requires `cryptography==48.0.1` exactly. The raw audit reports
  `PYSEC-2026-3552`, `PYSEC-2026-3553`, and `PYSEC-2026-3554`; fixing the complete set requires
  cryptography 50.0.0.
- The FMI integration does not import or declare cryptography. Its manifest dependency closure
  remains clean; the package enters the complete development/test environment through Home
  Assistant Core.
- Do not override Home Assistant's exact pin locally. It conflicts with Home Assistant and
  pyOpenSSL constraints, makes `pip check` fail, and tests an unsupported environment.
- The owner-approved private-testing exception is exact by package, version, and advisory ID in
  `.github/dependency-audit-exceptions.json`. New findings, changed affected versions, and stale
  exceptions remain blocking.
- The earlier Pillow/PyJWT exceptions are removed because Home Assistant now selects Pillow 12.3.0
  and PyJWT 2.13.0, which pass the current raw audit.

After an upstream fix, update the Home Assistant/helper pair, regenerate the complete freeze, and
require `make audit-raw`, `make audit`, the full offline suite, and `make validate` to pass before
removing this item. The raw audit intentionally remains nonzero while the upstream pin is
vulnerable; the policy audit passes only for the exact accepted finding set.

Evidence rechecked 2026-08-08: [PKCS#7 advisory](https://osv.dev/vulnerability/PYSEC-2026-3552),
[certificate path-building advisory](https://osv.dev/vulnerability/PYSEC-2026-3553),
[name-constraints advisory](https://osv.dev/vulnerability/PYSEC-2026-3554), Home Assistant 2026.8.1
package metadata, and the open [Home Assistant cryptography 50.0.0 update](https://github.com/home-assistant/core/pull/178496).

## Replace public Nominatim before broader distribution

- Status: `ACCEPTED_PRIVATE_TESTING`; reviewed 2026-08-01.
- Optional lightning enrichment sends public FMI strike coordinates, not configured home coordinates, to OSMF's public Nominatim service. It is cached, single-threaded, attributed, identified by User-Agent, limited to one lookup per update, and globally limited to 4 requests/minute.
- OSMF discourages periodic app traffic at scale and requires applications to be able to switch services. The current owner-only test deployment is deliberately small, but the implementation is not a foundation for an assumed public user base.

Before broader distribution, choose and verify one of these outcomes:

1. Remove reverse-geocoded address enrichment and retain a local/public FMI-data fallback.
2. Use an owner-controlled Nominatim instance or proxy.
3. Add a provider boundary that can be switched without an integration release and remains opt-in.

Evidence: [OSMF Nominatim usage policy](https://operations.osmfoundation.org/policies/nominatim/) and `docs/maintenance/COMPATIBILITY_SECURITY.md`.

## Implement user-friendly FMI location selection

- Status: `PLANNED`.
- Execute the independent [P02 implementation plan](plans/P02/PLAN.md), with its verified baseline
  and session reports stored alongside the plan under `plans/P02/`.
- Replace visible latitude/longitude entry in initial setup and reconfiguration with two normal
  paths: a Home-defaulted Home Assistant map selector, and FMI place-name search followed by map
  confirmation.
- Preserve the existing stored coordinate shape, immutable identity, registry records, customized
  entity IDs, duplicate-location checks, lifecycle behavior, and coordinate privacy.
- Country/city catalogs, observation-station selection, third-party forward geocoding, automatic
  Home zone tracking, and a separate manual coordinate form are outside P02.

Close this item only after every P02 session and requirement is `DONE`, the complete verification
matrix passes, current documentation matches the implemented behavior, and the final P02 report is
saved in the self-contained `plans/P02/` plan directory.
