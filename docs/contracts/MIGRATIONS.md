<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Migration Contract

## Assertions

### `MIG-001` — Config migration is versioned, neutral, and idempotent

**Contract:** Version-1 entries from v0.6.2 MUST migrate to version 2; version-2 entries MUST be a
no-op on repeated migration. Unknown future versions MUST be rejected without mutating config,
options, title, entity registry, or device registry.

**Evidence:**

- [`test_config_migration_is_registry_neutral_and_idempotent`](../../tests/test_migrations.py) — `tests/test_migrations.py::test_config_migration_is_registry_neutral_and_idempotent`
- [`test_future_config_version_is_rejected_without_mutation`](../../tests/test_migrations.py) — `tests/test_migrations.py::test_future_config_version_is_rejected_without_mutation`

### `MIG-002` — Legacy identity remains the entity/device identity

**Contract:** Migration MUST store the original `latitude:longitude` coordinator identifier as
immutable `entity_identity`, preserving existing device/entity unique IDs. The config-entry unique
ID SHOULD become `fmi:<entry_id>`; if occupied, migration MUST retain the legacy config unique ID
and MUST NOT overwrite the other entry.

**Evidence:**

- [`test_v062_migration_preserves_legacy_entity_identity`](../../tests/test_config_flow.py) — `tests/test_config_flow.py::test_v062_migration_preserves_legacy_entity_identity`
- [`test_v062_migration_collision_keeps_safe_legacy_config_id`](../../tests/test_config_flow.py) — `tests/test_config_flow.py::test_v062_migration_collision_keeps_safe_legacy_config_id`
- [`test_duplicate_coordinate_policy_is_stable_across_migration`](../../tests/test_migrations.py) — `tests/test_migrations.py::test_duplicate_coordinate_policy_is_stable_across_migration`

### `MIG-003` — Registry records are preserved and renamed only when unambiguous

**Contract:** Migration/setup MUST NOT delete or recreate a legacy entity-registry record. An exact
known unsuffixed v0.6.2 generated sensor ID MAY be renamed in place only when its location-aware
target is free. Customized IDs, occupied targets, and ambiguous suffixed IDs MUST remain literal;
internal registry IDs and unique IDs MUST remain unchanged.

**Evidence:**

- [`test_exact_legacy_generated_entity_id_is_migrated`](../../tests/test_sensor_entities.py) — `tests/test_sensor_entities.py::test_exact_legacy_generated_entity_id_is_migrated`
- [`test_user_customized_entity_id_is_preserved`](../../tests/test_sensor_entities.py) — `tests/test_sensor_entities.py::test_user_customized_entity_id_is_preserved`
- [`test_ambiguous_suffix_is_preserved_for_same_place_multi_entry_history`](../../tests/test_migrations.py) — `tests/test_migrations.py::test_ambiguous_suffix_is_preserved_for_same_place_multi_entry_history`
- [`test_legacy_entity_id_migration_skips_target_collision`](../../tests/test_sensor_entities.py) — `tests/test_sensor_entities.py::test_legacy_entity_id_migration_skips_target_collision`

### `MIG-004` — Additive entities use the existing registry path

**Contract:** New sensor descriptions MUST attach through the established unique-ID/device
construction and MUST NOT introduce a parallel migration path. Setup/reload MUST add missing
descriptions once while preserving customized IDs and user-disabled registry state.

**Evidence:**

- [`test_combined_setup_preserves_registry_history_and_is_idempotent`](../../tests/test_migrations.py) — `tests/test_migrations.py::test_combined_setup_preserves_registry_history_and_is_idempotent`
- [`test_current_registry_customization_and_disabled_state_survive_reload`](../../tests/test_migrations.py) — `tests/test_migrations.py::test_current_registry_customization_and_disabled_state_survive_reload`

### `MIG-005` — Legacy optional entities survive option changes

**Contract:** The legacy daily weather entity and an existing lightning entity MUST retain internal
registry ID, unique ID, customized entity ID, enabled/disabled state, config entry, and location
device. Disabling an option MUST NOT delete its registry record; re-enabling MUST restore the same
record without reviving stale attributes.

**Evidence:**

- [`test_legacy_daily_entity_survives_disable_and_reenable`](../../tests/test_migrations.py) — `tests/test_migrations.py::test_legacy_daily_entity_survives_disable_and_reenable`
- [`test_options_reload_adds_and_removes_optional_entities_once`](../../tests/test_lifecycle.py) — `tests/test_lifecycle.py::test_options_reload_adds_and_removes_optional_entities_once`
- [`test_combined_setup_preserves_registry_history_and_is_idempotent`](../../tests/test_migrations.py) — `tests/test_migrations.py::test_combined_setup_preserves_registry_history_and_is_idempotent`
