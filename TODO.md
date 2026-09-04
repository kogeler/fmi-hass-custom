<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Maintenance TODO

## Resolve vulnerable Home Assistant-pinned cryptography

- Status: `BLOCKED_UPSTREAM`; temporary risk accepted by the repository owner on 2026-08-08 and
  rechecked on 2026-09-04.
- Home Assistant 2026.9.0 requires `cryptography==48.0.1` exactly. The raw audit reports
  `PYSEC-2026-3552`, `PYSEC-2026-3553`, and `PYSEC-2026-3554`; fixing the complete set requires
  cryptography 50.0.0.
- The FMI integration does not import or declare cryptography. Its manifest dependency closure
  remains clean; the package enters the complete development/test environment through Home
  Assistant Core.
- Do not override Home Assistant's exact pin locally. It conflicts with Home Assistant and
  pyOpenSSL constraints, makes `pip check` fail, and tests an unsupported environment.
- The owner-approved development/test exception is exact by package, version, and advisory ID in
  `.github/dependency-audit-exceptions.json`. New findings, changed affected versions, and stale
  exceptions remain blocking.
- The earlier Pillow/PyJWT exceptions are removed because Home Assistant now selects Pillow 12.3.0
  and PyJWT 2.13.0, which pass the current raw audit.

After an upstream fix, update the Home Assistant/helper pair, regenerate the three hash locks, and
require `make audit-raw`, `make audit`, the full offline suite, and `make validate` to pass before
removing this item. The raw audit intentionally remains nonzero while the upstream pin is
vulnerable; the policy audit passes only for the exact accepted finding set.

Evidence rechecked 2026-09-04: [PKCS#7 advisory](https://osv.dev/vulnerability/PYSEC-2026-3552),
[certificate path-building advisory](https://osv.dev/vulnerability/PYSEC-2026-3553),
[name-constraints advisory](https://osv.dev/vulnerability/PYSEC-2026-3554), Home Assistant 2026.9.0
package metadata, and the tracked [Home Assistant cryptography 50.0.0 update](https://github.com/home-assistant/core/pull/178496).
