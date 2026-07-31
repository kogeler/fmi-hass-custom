<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Location Reconfiguration and Identity

Last verified: 2026-07-31

## User behavior

An existing FMI entry can be moved from its Home Assistant integration menu by choosing **Reconfigure** and entering a new latitude and longitude.

The flow:

1. applies Home Assistant's latitude and longitude validation;
2. rejects coordinates already used by another FMI entry;
3. asks FMI for current weather at the proposed location;
4. changes nothing when FMI validation fails;
5. updates the coordinates and resolved-place title only after validation succeeds;
6. reloads only the affected loaded entry through its existing update listener.

Entity IDs and unique IDs are retained, including customized entity IDs used by automations and dashboards. Device and entity display context updates to the newly resolved FMI place after reload.

Dynamic tracking of Home zone coordinates is intentionally not implemented. It would add a separate subscription and migration lifecycle without being necessary for safe location reconfiguration. Users can run Reconfigure when their location changes.

## Identity model

Config-entry version 2 separates three concepts:

- `entity_identity` is immutable and owns device/entity unique IDs;
- latitude and longitude are mutable data-source coordinates;
- the config-entry title and device name are mutable resolved-place labels.

Fresh entries receive a random coordinate-independent identity. A v0.6.2/version-1 entry stores its original `latitude:longitude` value as `entity_identity`, preserving every existing weather, sensor, and device identifier. Its config-entry unique ID moves to `fmi:<entry_id>` unless that value is already occupied; a collision safely retains the old config unique ID without changing entity identity.

Reconfiguration never changes `entity_identity` or the config-entry unique ID. Duplicate detection therefore compares current coordinates rather than stable IDs.

Ambiguous automatically suffixed legacy entity IDs and complex multi-entry registry histories remain assigned to S11. Reconfiguration does not guess whether those IDs were generated or customized.

## Failure and privacy rules

- FMI client/server errors produce a translated connection error and leave the entry unchanged.
- Unexpected validation failures produce a translated generic error and are logged without coordinates.
- The flow uses the same asynchronous, contract-tested FMI adapter as runtime setup.
- Exact coordinates are not placed in validation log messages.

## Authoritative references

- Home Assistant, "Integrations should have a reconfigure flow": <https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/reconfiguration-flow/> (accessed 2026-07-31)
- Home Assistant, "Config flow": <https://developers.home-assistant.io/docs/core/integration/config_flow/> (accessed 2026-07-31)
- Location selection and editing requirement, verified 2026-07-31.
