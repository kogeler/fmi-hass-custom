<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Weather Warnings Contract

## Assertions

### `WRN-001` — CAP publications are complete snapshots

**Contract:** The warnings parser MUST accept only Atom/CAP containers in their exact namespaces,
validate aware publication/message timestamps, and atomically return a complete snapshot.
Updates and cancellations MUST suppress referenced messages before spatial filtering regardless of
document order. Alert messages MUST NOT carry replacement references. Missing predecessors MAY be
absent; envelope control defects, conflicting duplicates, and reference cycles MUST fail the
snapshot. Unusable mandatory message data MUST fail the snapshot instead of asserting an all-clear
unless the message is provably remote under `WRN-002`. A nonempty feed without any message from the
FMI sender MUST fail as unrecognized. Identifiers MUST remain opaque. Test/non-public messages and
unsupported authorities MUST NOT become FMI warnings.

**Evidence:**

- [`test_warning_references_apply_before_filtering_and_ignore_document_order`](../../tests/test_warnings_client.py) — `tests/test_warnings_client.py::test_warning_references_apply_before_filtering_and_ignore_document_order`
- [`test_warning_snapshot_does_not_require_history_or_an_explicit_cancel`](../../tests/test_warnings_client.py) — `tests/test_warnings_client.py::test_warning_snapshot_does_not_require_history_or_an_explicit_cancel`
- [`test_incomplete_warning_snapshots_never_become_an_all_clear`](../../tests/test_warnings_client.py) — `tests/test_warnings_client.py::test_incomplete_warning_snapshots_never_become_an_all_clear`
- [`test_warning_onset_expiry_and_replacement_update_ha_without_network`](../../tests/test_warning_entities.py) — `tests/test_warning_entities.py::test_warning_onset_expiry_and_replacement_update_ha_without_network`
- [`test_alert_references_cannot_suppress_an_active_warning`](../../tests/test_warnings_client.py) — `tests/test_warnings_client.py::test_alert_references_cannot_suppress_an_active_warning`
- [`test_warning_feed_without_an_fmi_envelope_is_not_an_all_clear`](../../tests/test_warnings_client.py) — `tests/test_warnings_client.py::test_warning_feed_without_an_fmi_envelope_is_not_an_all_clear`
- [`test_warning_non_operational_or_other_authority_messages_are_not_fmi`](../../tests/test_warnings_client.py) — `tests/test_warnings_client.py::test_warning_non_operational_or_other_authority_messages_are_not_fmi`
- [`test_warning_remote_defects_cannot_hide_a_local_warning`](../../tests/test_warnings_client.py) — `tests/test_warnings_client.py::test_warning_remote_defects_cannot_hide_a_local_warning`

### `WRN-002` — Point matching uses inclusive local CAP geometry

**Contract:** Warnings MUST match the config-entry coordinates against the union of their CAP
polygons locally, including edges/vertices within a 1e-9-degree boundary tolerance. A bounding box
MUST NOT substitute for polygon membership. Multiple matching polygons/areas MUST count a message
only once. A message MUST be skipped without content validation when every info block has areas,
every area has polygons and no circle, every polygon parses into finite coordinate pairs, and the
tolerance-expanded vertex bounding box of every polygon excludes the target, because no ring defined
by those vertices can contain it. For every other message, invalid, unclosed, non-finite, unbounded,
or unsupported antimeridian geometry MUST NOT establish absence of warnings, and zero-area,
self-touching, crossing, and overlapping-edge rings MUST fail before polygon membership.
Consecutive duplicate vertices MAY be normalized. Intersection validation MUST sweep along the axis
with fewer candidate segment comparisons, counted exactly before sweeping, and MUST fail the source
as `geometry_too_complex` when that minimum exceeds 1,000,000 per ring. Source geometry MUST NOT be
retained in the public warning model.

**Evidence:**

- [`test_warning_geometry_includes_edges_and_vertices`](../../tests/test_warnings_client.py) — `tests/test_warnings_client.py::test_warning_geometry_includes_edges_and_vertices`
- [`test_warning_non_simple_geometry_fails_before_location_filtering`](../../tests/test_warnings_client.py) — `tests/test_warnings_client.py::test_warning_non_simple_geometry_fails_before_location_filtering`
- [`test_warning_geometry_complexity_is_bounded`](../../tests/test_warnings_client.py) — `tests/test_warnings_client.py::test_warning_geometry_complexity_is_bounded`
- [`test_warning_large_valid_ring_and_exact_xml_boundary`](../../tests/test_warnings_client.py) — `tests/test_warnings_client.py::test_warning_large_valid_ring_and_exact_xml_boundary`
- [`test_warning_numerical_tolerance_is_not_a_search_radius`](../../tests/test_warnings_client.py) — `tests/test_warnings_client.py::test_warning_numerical_tolerance_is_not_a_search_radius`
- [`test_warning_geometry_filters_point_and_unions_areas_without_double_counting`](../../tests/test_warnings_client.py) — `tests/test_warnings_client.py::test_warning_geometry_filters_point_and_unions_areas_without_double_counting`
- [`test_incomplete_warning_snapshots_never_become_an_all_clear`](../../tests/test_warnings_client.py) — `tests/test_warnings_client.py::test_incomplete_warning_snapshots_never_become_an_all_clear`
- [`test_warning_invalid_rings_cannot_establish_absence`](../../tests/test_warnings_client.py) — `tests/test_warnings_client.py::test_warning_invalid_rings_cannot_establish_absence`
- [`test_warning_remote_defects_cannot_hide_a_local_warning`](../../tests/test_warnings_client.py) — `tests/test_warnings_client.py::test_warning_remote_defects_cannot_hide_a_local_warning`
- [`test_warning_geometry_that_cannot_be_bounded_still_fails`](../../tests/test_warnings_client.py) — `tests/test_warnings_client.py::test_warning_geometry_that_cannot_be_bounded_still_fails`
- [`test_warning_far_polygon_in_a_matching_message_is_rejected_by_bbox`](../../tests/test_warnings_client.py) — `tests/test_warnings_client.py::test_warning_far_polygon_in_a_matching_message_is_rejected_by_bbox`
- [`test_warning_dense_valid_ring_uses_the_cheaper_sweep_axis`](../../tests/test_warnings_client.py) — `tests/test_warnings_client.py::test_warning_dense_valid_ring_uses_the_cheaper_sweep_axis`
- [`test_warning_sweep_cost_matches_an_exhaustive_count`](../../tests/test_warnings_client.py) — `tests/test_warnings_client.py::test_warning_sweep_cost_matches_an_exhaustive_count`
- [`test_warning_geometry_budget_reports_its_reason`](../../tests/test_warnings_client.py) — `tests/test_warnings_client.py::test_warning_geometry_budget_reports_its_reason`

### `WRN-003` — Warning text preserves coherent official languages

**Contract:** Warning text MUST use one coherent Finnish, Swedish, or English CAP info block,
preferring the selected language and then English, Finnish, Swedish. Actual language MUST remain
explicit. Unknown event codes or severity MAY remain visible without fabricated text or color.
Conflicting language blocks MUST fail the snapshot; missing optional instructions MUST remain
missing. Consistency MUST include urgency and certainty as well as event, severity, interval and
local point membership. Raw XML, geometry, and config identity MUST NOT become public warning attributes.

**Evidence:**

- [`test_warning_language_selection_is_coherent`](../../tests/test_warnings_client.py) — `tests/test_warnings_client.py::test_warning_language_selection_is_coherent`
- [`test_warning_language_classifications_must_agree`](../../tests/test_warnings_client.py) — `tests/test_warnings_client.py::test_warning_language_classifications_must_agree`
- [`test_warning_missing_locale_falls_back_without_discarding_new_event`](../../tests/test_warnings_client.py) — `tests/test_warnings_client.py::test_warning_missing_locale_falls_back_without_discarding_new_event`
- [`test_warning_duplicate_republication_and_unknown_severity_remain_visible`](../../tests/test_warnings_client.py) — `tests/test_warnings_client.py::test_warning_duplicate_republication_and_unknown_severity_remain_visible`
- [`test_warning_original_languages_and_ui_translations_load`](../../tests/test_warning_entities.py) — `tests/test_warning_entities.py::test_warning_original_languages_and_ui_translations_load`

### `WRN-004` — Warning time boundaries are local and freshness is explicit

**Contract:** Active warnings MUST satisfy `onset <= now < expires`; future warnings MUST remain
separate. Local onset/expiry callbacks MUST update Home Assistant entities without HTTP or postponing
network polling. A snapshot MUST become unavailable after 15 minutes without successful retrieval,
logging that stale transition once. A `timeout`, `transport`, or `http_server` retrieval failure
MUST keep a held snapshot and its entities available until that deadline, while recording the
classified reason. Any other failure, or one with no held snapshot, MUST clear it immediately.
A later valid retrieval MUST reset the reason. For 15 minutes after the last accepted retrieval,
an older publication MUST NOT replace or restore warnings: a held snapshot MUST remain unchanged,
including its retrieval time, and without one the source MUST fail as `publication_rollback`;
afterwards the newest retrieved valid publication MUST be accepted.
Shutdown MUST remove local callbacks and the managed polling schedule. Callbacks MUST project actual
execution time rather than the scheduled timestamp; obsolete callbacks and in-flight results
completed after shutdown MUST NOT revive state or timers and MUST NOT be reported as failures.
Freshness MUST use successful retrieval time, not publication age; an unchanged HTTP 200
publication MAY refresh it.

**Evidence:**

- [`test_warning_time_boundaries_notify_without_fetching`](../../tests/test_warnings_coordinator.py) — `tests/test_warnings_coordinator.py::test_warning_time_boundaries_notify_without_fetching`
- [`test_warning_delayed_and_obsolete_callbacks_use_current_time`](../../tests/test_warnings_coordinator.py) — `tests/test_warnings_coordinator.py::test_warning_delayed_and_obsolete_callbacks_use_current_time`
- [`test_warning_inflight_refresh_cannot_accept_after_shutdown`](../../tests/test_warnings_coordinator.py) — `tests/test_warnings_coordinator.py::test_warning_inflight_refresh_cannot_accept_after_shutdown`
- [`test_warning_mixed_severity_sorting_and_repeated_publication`](../../tests/test_warnings_coordinator.py) — `tests/test_warnings_coordinator.py::test_warning_mixed_severity_sorting_and_repeated_publication`
- [`test_warning_delayed_boundaries_and_inflight_unload_in_ha`](../../tests/test_warning_entities.py) — `tests/test_warning_entities.py::test_warning_delayed_boundaries_and_inflight_unload_in_ha`
- [`test_warning_failure_clears_recovers_and_rejects_publication_rollback`](../../tests/test_warnings_coordinator.py) — `tests/test_warnings_coordinator.py::test_warning_failure_clears_recovers_and_rejects_publication_rollback`
- [`test_warning_older_publication_cannot_flap_or_stick`](../../tests/test_warnings_coordinator.py) — `tests/test_warnings_coordinator.py::test_warning_older_publication_cannot_flap_or_stick`
- [`test_warning_transient_failure_holds_only_a_fresh_snapshot`](../../tests/test_warnings_coordinator.py) — `tests/test_warnings_coordinator.py::test_warning_transient_failure_holds_only_a_fresh_snapshot`
- [`test_warning_transient_failures_hold_entities_until_the_freshness_deadline`](../../tests/test_warning_entities.py) — `tests/test_warning_entities.py::test_warning_transient_failures_hold_entities_until_the_freshness_deadline`
- [`test_every_classified_warning_failure_reason_is_exposed`](../../tests/test_warnings_coordinator.py) — `tests/test_warnings_coordinator.py::test_every_classified_warning_failure_reason_is_exposed`
- [`test_warning_unchanged_publication_keeps_the_projection_equal`](../../tests/test_warnings_coordinator.py) — `tests/test_warnings_coordinator.py::test_warning_unchanged_publication_keeps_the_projection_equal`
- [`test_warning_onset_expiry_and_replacement_update_ha_without_network`](../../tests/test_warning_entities.py) — `tests/test_warning_entities.py::test_warning_onset_expiry_and_replacement_update_ha_without_network`
