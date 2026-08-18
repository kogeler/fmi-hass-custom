<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Maintenance TODO

## Resolve vulnerable Home Assistant-pinned cryptography

- Status: `BLOCKED_UPSTREAM`; temporary risk accepted by the repository owner on 2026-08-08 and
  rechecked on 2026-08-16.
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

After an upstream fix, update the Home Assistant/helper pair, regenerate the three hash locks, and
require `make audit-raw`, `make audit`, the full offline suite, and `make validate` to pass before
removing this item. The raw audit intentionally remains nonzero while the upstream pin is
vulnerable; the policy audit passes only for the exact accepted finding set.

Evidence rechecked 2026-08-16: [PKCS#7 advisory](https://osv.dev/vulnerability/PYSEC-2026-3552),
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

## Distinguish no lightning from an unavailable lightning source

- Status: `RESEARCH_REQUIRED`; tracked in
  [issue #4](https://github.com/kogeler/fmi-hass-custom/issues/4).
- A valid FMI response containing no lightning currently becomes an empty list. The optional-source
  coordinator then applies `bool` to that list and records the lightning source as unavailable, while
  `FMILightningStrikesSensor` stores a `None` native value. The base sensor availability rule therefore
  exposes `unavailable` both when FMI failed and when FMI successfully reported no strikes.
- These cases have different meanings and must remain distinguishable: a transport, parsing, or unsafe
  payload failure is unavailable data; a successful empty result is available data stating that there
  are no qualifying strikes inside the configured radius and age window.
- The fix must not retain the last strike after either an empty response or a source failure. It must
  preserve the existing config entry, entity registry record, unique ID, customized entity ID, and
  automation compatibility as far as the corrected state semantics allow.

Research and design before implementation:

1. Review current Home Assistant guidance and established integrations for event-like sensors with a
   valid empty state. Decide whether the existing entity should expose a translated textual state, a
   numeric strike count, or another HA-native representation. Do not use the literal string `None` as
   an accidental API or introduce a device/state class that does not match the data.
2. Model the three source states explicitly: `None` for a failed/unusable source, an empty collection
   for a successful response with no strikes, and a non-empty collection for valid strike groups.
   Availability should follow source validity instead of Python collection truthiness.
3. Evaluate compatibility consequences of changing the native value. Prefer an additive attribute or
   a separate entity if changing the existing location-valued state would unnecessarily break existing
   templates and automations. Preserve the current observation attribute schema for non-empty results.
4. Define localized frontend text and stable machine-readable semantics for the empty state. Verify how
   the state is recorded, restored, displayed, and consumed by automations after restart and reload.
5. Add offline coordinator and Home Assistant entity tests for startup and all transitions:
   empty to strikes, strikes to empty, empty to failure, strikes to failure, and recovery from failure
   to either empty or strikes. Assert that stale strike attributes are cleared and unrelated weather,
   observation, and sea-level entities remain available.
6. Update `docs/maintenance/OPTIONAL_SOURCES.md`, `AVAILABILITY.md`, and `SENSORS.md` once the chosen
   contract is implemented.

Acceptance requires a valid empty FMI lightning response to produce an available, unambiguous state;
real source failures must still produce `unavailable`, and tests must prove recovery without reloading
the config entry.

## Provide local lightning direction without unreliable storm prediction

- Status: `RESEARCH_REQUIRED`; tracked in
  [issue #5](https://github.com/kogeler/fmi-hass-custom/issues/5).
- The useful, bounded part of the request is a direction from the configured integration location to a
  lightning strike, such as north-east or south. This can be calculated locally from coordinates already
  held by the integration and needs no additional disclosure to Nominatim or another service.
- The separate request to estimate a storm's projected closest distance from forecast wind direction is
  not accepted as technically valid without further evidence. A surface wind forecast is not a measured
  storm-cell motion vector, and isolated lightning observations do not by themselves identify or track a
  storm. A misleading closest-approach value could be interpreted as safety information.

Research and design before implementation:

1. Define the direction precisely as the initial geographic bearing from the configured location to the
   strike, not the direction from which a storm is assumed to travel. Choose and document an eight- or
   sixteen-sector compass mapping, boundary behavior, localization, and a representation for coincident
   coordinates where bearing is undefined.
2. Validate the bearing calculation across the antimeridian, near the poles, on sector boundaries, and
   for invalid or non-finite coordinates. Prefer a small audited local calculation over a new runtime
   dependency or network request.
3. Decide whether direction supplements the existing location, becomes the fallback when reverse
   geocoding is unavailable, or replaces reverse-geocoded place names. Consider this together with the
   separate public-Nominatim replacement TODO; a local direction must continue to work with Nominatim
   completely disabled.
4. Preserve compatibility by assessing the current native location value and `OBSERVATIONS` attribute
   consumers. Prefer additive stable attributes such as direction and numeric bearing before changing
   the native value. Apply the same schema consistently to the newest strike and historical groups.
5. Investigate authoritative FMI products for actual storm-cell tracking or motion vectors. If FMI does
   not provide a documented and sufficiently fresh source, explicitly reject projected closest distance
   rather than approximating it from ordinary wind. If a suitable source exists, design it as a separate
   opt-in feature with uncertainty, freshness, failure, request-budget, and no-safety-guarantee contracts.
6. Add deterministic geometry tests, Home Assistant state/attribute tests, translation coverage, and
   privacy tests proving the local direction calculation performs no I/O. Update
   `docs/maintenance/OPTIONAL_SOURCES.md`, `SENSORS.md`, and `COMPATIBILITY_SECURITY.md` for the final
   design.

Acceptance for the bounded direction feature requires deterministic localized direction, no extra
network traffic, preserved registry identity, and documented behavior at geographic edge cases. A
storm-projection feature remains out of scope unless authoritative motion data and defensible semantics
are established first.
