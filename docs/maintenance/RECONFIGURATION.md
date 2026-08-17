<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Location Reconfiguration and Identity

Last verified against current code: 2026-08-17.

## User behavior

An existing FMI entry can be moved from its Home Assistant integration menu by choosing
**Reconfigure**, then either:

- select a point with Home Assistant's standard location map, whose marker starts at the entry's
  stored point rather than the current Home zone; or
- send a city or place name to FMI, review FMI's resolved point on the same map, and confirm or
  adjust the marker.

The flow:

1. validates the selector mapping as finite WGS84 latitude and longitude;
2. rejects coordinates already used by another FMI entry;
3. asks FMI for current weather at the proposed location;
4. changes nothing when FMI validation fails;
5. updates the coordinates and resolved-place title only after validation succeeds;
6. reloads only the affected loaded entry through its existing update listener.

Entity IDs and unique IDs are retained, including customized entity IDs used by automations and dashboards. Device and entity display context updates to the newly resolved FMI place after reload.

Dynamic tracking of Home zone coordinates is intentionally not implemented. It would add a
separate subscription and migration lifecycle without being necessary for safe location
reconfiguration. Users can run Reconfigure and select the new point when their location changes.

## Identity model

Config-entry version 2 separates three concepts:

- `entity_identity` is immutable and owns device/entity unique IDs;
- latitude and longitude are mutable data-source coordinates;
- the config-entry title and device name are mutable resolved-place labels.

Fresh entries receive a random coordinate-independent identity. A v0.6.2/version-1 entry stores its original `latitude:longitude` value as `entity_identity`, preserving every existing weather, sensor, and device identifier. Its config-entry unique ID moves to `fmi:<entry_id>` unless that value is already occupied; a collision safely retains the old config unique ID without changing entity identity.

Reconfiguration never changes `entity_identity` or the config-entry unique ID. Duplicate detection therefore compares current coordinates rather than stable IDs.

Acceptance tests confirm that exact unsuffixed legacy sensor defaults migrate in place when safe,
while ambiguous automatically suffixed IDs, customized IDs, and occupied targets are preserved.
Reconfiguration does not guess whether a suffixed ID was generated or customized. The complete
rules are in `MIGRATIONS.md`.

## Failure and privacy rules

- FMI client/server errors produce a translated connection error and leave the entry unchanged.
- A place lookup with no matching forecast data stays on the translated search form. The search
  result never changes the entry until its map point passes final coordinate validation.
- Unexpected validation failures produce a translated generic error and are logged without coordinates.
- The flow uses the same asynchronous, contract-tested FMI adapter as runtime setup.
- Place search text and exact coordinates are not placed in validation log messages or persisted
  as flow-mode metadata.

## Authoritative references

- Home Assistant, "Integrations should have a reconfigure flow": <https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/reconfiguration-flow/> (accessed 2026-08-17)
- Home Assistant, "Config flow": <https://developers.home-assistant.io/docs/core/integration/config_flow/> (accessed 2026-08-17)
