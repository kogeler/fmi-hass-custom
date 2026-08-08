<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Config And Registry Migrations

Last verified: 2026-08-08 against Home Assistant 2026.8.1 and the local v0.6.2 tag.

## Supported source state

The migration accepts version-1 config entries created by v0.6.2. The synthetic acceptance fixture in `tests/fixtures/fmi/registry_v062.json` represents:

- coordinate-based config unique IDs such as `60.17_24.94`;
- the original data/options/minor-version shape;
- device identifiers such as `(fmi, 60.17:24.94)`;
- weather unique IDs based on coordinates;
- sensor unique IDs based on coordinates, configured client name, and sensor type;
- first-entry generated IDs such as `sensor.temperature`;
- later automatically suffixed IDs such as `sensor.temperature_2`;
- user-customized sensor and daily-weather IDs;
- two entries, occupied targets, and identical resolved place names.

Unknown future config-entry versions are rejected without mutation. A version-2 entry is already migrated and a repeated migration is a no-op.

## Config identity

Version 2 adds immutable `entity_identity` while leaving latitude and longitude mutable. For a legacy entry, `entity_identity` is the exact original `latitude:longitude` coordinator identifier, so existing device and entity unique IDs continue to resolve.

The config-entry unique ID becomes `fmi:<entry_id>`. If another entry already owns that target, migration completes while retaining the legacy config unique ID. It never overwrites the other entry. Data, options, title, minor version, entity registry, and device registry are otherwise unchanged by the config migration itself.

## Entity and device registries

Home Assistant reconciles existing entities by their unchanged platform and unique ID. The integration never deletes or recreates a legacy registry record during migration.

| Legacy state | Result |
|---|---|
| Exact first-entry sensor default, for example `sensor.temperature` | Renamed in place to the resolved location target when that target is free |
| Exact default with an occupied location target | Preserved unchanged |
| User-customized entity ID | Preserved unchanged |
| Automatically suffixed ID such as `sensor.temperature_2` | Preserved unchanged |
| Weather, lightning, and sea-level ID | Preserved unchanged because v0.6.2 already generated location-based IDs |
| Entity/device unique ID and internal registry ID | Always preserved |

The entity registry does not retain provenance that can reliably distinguish a suffix automatically allocated by Home Assistant from the same suffix later selected by a user. Guessing would break automations in one of those histories. Suffixed IDs therefore remain intentionally unchanged. They still acquire the correct location device association during setup.

Legacy location devices are reused through their coordinate identifier and updated in place with the current resolved place name. Two entries remain distinct when FMI resolves both to the same place text because their immutable device/entity identifiers differ.

## Optional daily weather entity

The legacy daily weather entity is intentionally retained. It is redundant with the main entity's current daily forecast service, but removing or disabling its registry record would break customized dashboards and entity references without a safe replacement mechanism.

When `daily_mode` is disabled, the registry record remains and Home Assistant exposes its restored state as unavailable. Re-enabling the option attaches the same internal registry ID, unique ID, and customized entity ID. No migration silently deletes or renames it.

## Reconfiguration after migration

After migration, reconfiguration may change coordinates, config-entry title, and device display name. It does not change `entity_identity`, config unique ID, registry IDs, entity unique IDs, or entity IDs. Existing location-derived IDs therefore remain stable even when the resolved place changes, including customized IDs and the optional daily entity.

Duplicate-coordinate checks compare current coordinates both before and after migration. Stable internal identity never permits two entries to converge on the same configured location.

## Verification

`tests/test_migrations.py` materializes the serialized fixture through current Home Assistant config-entry, entity-registry, device-registry, setup, reload, state, options, and reconfigure APIs. It verifies config-only migration, combined setup, repeated migration/reload, future-version refusal, custom and ambiguous IDs, target collisions, same-name multi-entry isolation, daily disable/re-enable, and post-migration coordinate changes.

The fixture is synthetic, uses rounded public city coordinates, and contains no captured FMI payload or owner location.
