<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Reconfiguration Contract

## Assertions

### `RCF-001` — Fresh identity is independent from mutable location

**Contract:** A fresh entry MUST receive random coordinate-independent `entity_identity`.
Coordinates, config title, and device display name MAY change; `entity_identity`, config unique ID,
entity/device unique IDs, registry IDs, and customized entity IDs MUST remain unchanged.

**Evidence:**

- [`test_user_flow_creates_coordinate_independent_identity`](../../tests/test_config_flow.py) — `tests/test_config_flow.py::test_user_flow_creates_coordinate_independent_identity`
- [`test_reconfigure_updates_only_mutable_location`](../../tests/test_config_flow.py) — `tests/test_config_flow.py::test_reconfigure_updates_only_mutable_location`
- [`test_reconfigure_after_migration_preserves_all_registry_identity`](../../tests/test_migrations.py) — `tests/test_migrations.py::test_reconfigure_after_migration_preserves_all_registry_identity`

### `RCF-002` — Location validation is atomic

**Contract:** Reconfiguration MUST accept only finite WGS84 coordinates, reject a location already
used by another entry, validate the proposed point through FMI, and write coordinates/title only
after successful validation. Cancellation, client/server failure, malformed response, or unexpected
failure MUST leave the entry unchanged.

**Evidence:**

- [`test_reconfigure_rejects_invalid_map_locations`](../../tests/test_config_flow.py) — `tests/test_config_flow.py::test_reconfigure_rejects_invalid_map_locations`
- [`test_reconfigure_validation_failure_preserves_entry`](../../tests/test_config_flow.py) — `tests/test_config_flow.py::test_reconfigure_validation_failure_preserves_entry`
- [`test_reconfigure_unexpected_response_preserves_entry`](../../tests/test_config_flow.py) — `tests/test_config_flow.py::test_reconfigure_unexpected_response_preserves_entry`
- [`test_reconfigure_cancellation_preserves_entry`](../../tests/test_config_flow.py) — `tests/test_config_flow.py::test_reconfigure_cancellation_preserves_entry`

### `RCF-003` — Duplicate checks are race-safe

**Contract:** User and reconfigure flows MUST check duplicate current coordinates before external
validation and MUST recheck immediately before persistence. Concurrent confirmations for the same
point MUST create at most one entry; different points MUST remain independent.

**Evidence:**

- [`test_user_flow_rechecks_duplicate_after_validation`](../../tests/test_config_flow.py) — `tests/test_config_flow.py::test_user_flow_rechecks_duplicate_after_validation`
- [`test_reconfigure_rechecks_duplicate_after_validation`](../../tests/test_config_flow.py) — `tests/test_config_flow.py::test_reconfigure_rechecks_duplicate_after_validation`
- [`test_concurrent_place_confirmations_create_only_one_entry`](../../tests/test_config_flow.py) — `tests/test_config_flow.py::test_concurrent_place_confirmations_create_only_one_entry`

### `RCF-004` — Place search is transient until map confirmation

**Contract:** FMI place search MUST return only validated place/coordinate data into transient flow
state. Search failure, retry, abandonment, or cancellation MUST NOT write the config entry; only
final map confirmation MAY enter the normal coordinate validation/persistence path.

**Evidence:**

- [`test_user_place_search_confirms_or_adjusts_on_map`](../../tests/test_config_flow.py) — `tests/test_config_flow.py::test_user_place_search_confirms_or_adjusts_on_map`
- [`test_place_confirmation_failure_keeps_transient_form_without_entry`](../../tests/test_config_flow.py) — `tests/test_config_flow.py::test_place_confirmation_failure_keeps_transient_form_without_entry`
- [`test_abandoned_place_confirmation_can_restart_without_stale_state`](../../tests/test_config_flow.py) — `tests/test_config_flow.py::test_abandoned_place_confirmation_can_restart_without_stale_state`

### `RCF-005` — A loaded move reloads only its owning entry

**Contract:** Successful reconfiguration of a loaded entry MUST use its existing update listener to
reload only that entry. Other loaded entries MUST retain coordinators and state; the moved entry
MUST retain customized entity identity and load data for the new place.

**Evidence:**

- [`test_loaded_reconfigure_preserves_custom_entity_and_loads_new_place`](../../tests/test_config_flow.py) — `tests/test_config_flow.py::test_loaded_reconfigure_preserves_custom_entity_and_loads_new_place`
- [`test_loaded_place_reconfigure_reloads_only_selected_entry`](../../tests/test_config_flow.py) — `tests/test_config_flow.py::test_loaded_place_reconfigure_reloads_only_selected_entry`
