<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Optional Sources Contract

## Assertions

### `OPT-001` — Optional HTTP is shared, bounded, and non-retrying

**Contract:** Lightning and sea-level requests MUST use Home Assistant's shared async session with
2-second connect, 3-second read, and 5-second total timeouts and a 2 MiB response ceiling. A
coordinator update MUST NOT retry an optional request; status, transport, timeout, empty, and
oversized responses MUST be classified without disabling primary weather.

**Evidence:**

- [`test_optional_http_uses_ha_session_bounded_timeout_and_executor`](../../tests/test_auxiliary_payloads.py) — `tests/test_auxiliary_payloads.py::test_optional_http_uses_ha_session_bounded_timeout_and_executor`
- [`test_optional_response_size_is_bounded`](../../tests/test_auxiliary_payloads.py) — `tests/test_auxiliary_payloads.py::test_optional_response_size_is_bounded`
- [`test_optional_transport_failure_is_classified`](../../tests/test_auxiliary_payloads.py) — `tests/test_auxiliary_payloads.py::test_optional_transport_failure_is_classified`

### `OPT-002` — Lightning freshness is configurable and inclusive

**Contract:** `lightning_max_age_minutes` MUST accept 1 through 1440 with a lazy-compatible default
of 1440. The configured age MUST set the query start and inclusive retention cutoff; future,
missing, malformed, non-finite, millisecond-scale, or older timestamps MUST be discarded.

**Evidence:**

- [`test_options_flow_defaults_and_stores_lightning_max_age`](../../tests/test_config_flow.py) — `tests/test_config_flow.py::test_options_flow_defaults_and_stores_lightning_max_age`
- [`test_lightning_max_age_boundary_is_inclusive`](../../tests/test_auxiliary_payloads.py) — `tests/test_auxiliary_payloads.py::test_lightning_max_age_boundary_is_inclusive`
- [`test_lightning_request_uses_configured_max_age`](../../tests/test_auxiliary_payloads.py) — `tests/test_auxiliary_payloads.py::test_lightning_request_uses_configured_max_age`

### `OPT-003` — Lightning radius and geometry are local and deterministic

**Contract:** Distance/bearing MUST be calculated locally relative to the owning entry. The
configured radius MUST be enforced as an inclusive circle on unrounded distance after bbox
prefiltering. Invalid/non-convergent rows MUST be discarded independently; at most five nearest
groups MUST be retained and then presented newest first.

**Evidence:**

- [`test_lightning_circular_radius_is_inclusive`](../../tests/test_auxiliary_payloads.py) — `tests/test_auxiliary_payloads.py::test_lightning_circular_radius_is_inclusive`
- [`test_lightning_retains_five_nearest_then_presents_newest_first`](../../tests/test_auxiliary_payloads.py) — `tests/test_auxiliary_payloads.py::test_lightning_retains_five_nearest_then_presents_newest_first`
- [`test_lightning_geometry_matches_frozen_reference_vectors`](../../tests/test_lightning_geometry.py) — `tests/test_lightning_geometry.py::test_lightning_geometry_matches_frozen_reference_vectors`

### `OPT-004` — Lightning direction has exact public semantics

**Contract:** Bearing MUST normalize to `[0, 360)` and map through half-open 45-degree sectors to
the eight compass directions. Coincident coordinates MUST expose `here` with no bearing. Direction
MUST describe only point-to-strike observation and MUST NOT claim storm motion, arrival, or safety.

**Evidence:**

- [`test_direction_sector_boundaries_are_half_open`](../../tests/test_lightning_geometry.py) — `tests/test_lightning_geometry.py::test_direction_sector_boundaries_are_half_open`
- [`test_coincident_lightning_has_no_invented_bearing`](../../tests/test_lightning_geometry.py) — `tests/test_lightning_geometry.py::test_coincident_lightning_has_no_invented_bearing`
- [`test_direction_rejects_non_finite_or_non_numeric_values`](../../tests/test_lightning_geometry.py) — `tests/test_lightning_geometry.py::test_direction_rejects_non_finite_or_non_numeric_values`

### `OPT-005` — Optional XML rows fail at the narrowest safe boundary

**Contract:** Lightning position/value arrays MUST have equal length or reject the response;
individual malformed rows MAY be dropped independently. Sea-level state MUST require a finite
numeric value and aware supported timestamp; malformed/empty sea-level data MUST clear only that
source. All stored optional timestamps MUST be aware UTC datetimes.

**Evidence:**

- [`test_lightning_unequal_arrays_are_rejected`](../../tests/test_auxiliary_payloads.py) — `tests/test_auxiliary_payloads.py::test_lightning_unequal_arrays_are_rejected`
- [`test_lightning_malformed_rows_are_dropped`](../../tests/test_auxiliary_payloads.py) — `tests/test_auxiliary_payloads.py::test_lightning_malformed_rows_are_dropped`
- [`test_sea_level_rejects_invalid_values`](../../tests/test_auxiliary_payloads.py) — `tests/test_auxiliary_payloads.py::test_sea_level_rejects_invalid_values`

### `OPT-006` — Raw optional coordinates never cross the presentation boundary

**Contract:** Lightning MAY send the configured bounding box and sea level MAY send configured
coordinates to FMI, but raw strike coordinates MUST remain transient parser inputs and MUST NOT
appear in entity state/attributes or be sent to another provider.

**Evidence:**

- [`test_public_entity_and_forecast_contracts`](../../tests/test_lifecycle.py) — `tests/test_lifecycle.py::test_public_entity_and_forecast_contracts`
- [`test_two_loaded_entries_calculate_one_strike_from_their_own_coordinates`](../../tests/test_lifecycle.py) — `tests/test_lifecycle.py::test_two_loaded_entries_calculate_one_strike_from_their_own_coordinates`
- [`test_lightning_geometry_failure_log_omits_strike_coordinates`](../../tests/test_auxiliary_payloads.py) — `tests/test_auxiliary_payloads.py::test_lightning_geometry_failure_log_omits_strike_coordinates`
