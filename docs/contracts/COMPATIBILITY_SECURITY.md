<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Compatibility, Security, And Privacy Contract

## Assertions

### `CSP-001` — Reference compatibility and installation floor are independent

**Contract:** Root PEP 621 metadata and its hashed dev lock MUST own the exact Home Assistant/Python
reference graph; `hacs.json` MUST independently own the installation floor. Tests/runtime MUST NOT
copy mutable reference versions, and the HACS floor MUST NOT rise without a reproduced integration
incompatibility and regression evidence.

**Evidence:**

- [`test_pep621_owns_every_direct_python_dependency`](../../tests/test_dependency_policy.py) — `tests/test_dependency_policy.py::test_pep621_owns_every_direct_python_dependency`
- [`test_current_facing_docs_use_the_latest_release_instead_of_version_literals`](../../tests/test_distribution.py) — `tests/test_distribution.py::test_current_facing_docs_use_the_latest_release_instead_of_version_literals`
- [`test_hacs_repository_metadata_and_brand`](../../tests/test_distribution.py) — `tests/test_distribution.py::test_hacs_repository_metadata_and_brand`

### `CSP-002` — Moving stable blocks and prerelease informs

**Contract:** CI MUST resolve, freeze, recreate, check, and test latest stable Home Assistant as a
blocking job. A genuinely newer prerelease MAY be informational; absence of one MUST be an explicit
successful skip, while a recreated prerelease MUST still match its requested channel. Each moving
environment MUST test with the `pytest-homeassistant` release whose version equals the selected Home
Assistant version.

**Evidence:**

- [`test_ci_preserves_hacs_security_and_compatibility_gates`](../../tests/test_ci_policy.py) — `tests/test_ci_policy.py::test_ci_preserves_hacs_security_and_compatibility_gates`
- [`test_missing_prerelease_is_an_informational_skip`](../../tests/test_compatibility_helper.py) — `tests/test_compatibility_helper.py::test_missing_prerelease_is_an_informational_skip`
- [`test_recreated_prerelease_must_still_match_the_channel`](../../tests/test_compatibility_helper.py) — `tests/test_compatibility_helper.py::test_recreated_prerelease_must_still_match_the_channel`
- [`test_test_helper_is_pinned_to_the_selected_home_assistant`](../../tests/test_compatibility_helper.py) — `tests/test_compatibility_helper.py::test_test_helper_is_pinned_to_the_selected_home_assistant`
- [`test_mismatched_test_helper_is_fatal`](../../tests/test_compatibility_helper.py) — `tests/test_compatibility_helper.py::test_mismatched_test_helper_is_fatal`

### `CSP-003` — Logs exclude private external data

**Contract:** The integration MUST NOT configure the process-wide root logger. Logs MAY contain
source names, transitions, HTTP status classes, exception class names, and the name and configured
value of an expired request timeout, but MUST NOT contain configured coordinates,
coordinate-derived identity, place-search text, raw response/payload, or arbitrary external
exception text. The upstream-client privacy filter MUST remain scoped and idempotent.

**Evidence:**

- [`test_importing_constants_does_not_configure_root_logging`](../../tests/test_runtime_audit.py) — `tests/test_runtime_audit.py::test_importing_constants_does_not_configure_root_logging`
- [`test_external_error_details_do_not_include_payload_or_coordinates`](../../tests/test_compatibility_security.py) — `tests/test_compatibility_security.py::test_external_error_details_do_not_include_payload_or_coordinates`
- [`test_place_flow_does_not_log_query_or_malformed_result`](../../tests/test_compatibility_security.py) — `tests/test_compatibility_security.py::test_place_flow_does_not_log_query_or_malformed_result`
- [`test_upstream_privacy_filter_is_scoped_and_idempotent`](../../tests/test_compatibility_security.py) — `tests/test_compatibility_security.py::test_upstream_privacy_filter_is_scoped_and_idempotent`
- [`test_warning_failure_clears_recovers_and_rejects_publication_rollback`](../../tests/test_warnings_coordinator.py) — `tests/test_warnings_coordinator.py::test_warning_failure_clears_recovers_and_rejects_publication_rollback`
- [`test_warning_unexpected_failure_clears_state_and_names_only_the_class`](../../tests/test_warnings_coordinator.py) — `tests/test_warnings_coordinator.py::test_warning_unexpected_failure_clears_state_and_names_only_the_class`
- [`test_warning_initial_failure_is_optional_and_primary_failure_is_not`](../../tests/test_warning_entities.py) — `tests/test_warning_entities.py::test_warning_initial_failure_is_optional_and_primary_failure_is_not`
- [`test_warning_timeout_logs_name_the_expired_limit`](../../tests/test_warnings_coordinator.py) — `tests/test_warnings_coordinator.py::test_warning_timeout_logs_name_the_expired_limit`
- [`test_optional_transport_failure_is_classified`](../../tests/test_auxiliary_payloads.py) — `tests/test_auxiliary_payloads.py::test_optional_transport_failure_is_classified`

### `CSP-004` — Diagnostics expose only sanitized health metadata

**Contract:** Downloadable diagnostics MUST expose only sanitized configuration/options, config
version, polling cadence, coordinator success, and source availability. They MUST NOT expose exact
coordinates, the configured display name, the observation station ID, place/weather values,
entry/entity/legacy identity, or external payloads; exported
availability mappings MUST NOT mutate coordinator state.
Warning diagnostics MUST expose health/cadence only, without message counts, text, or area labels.
Warnings MAY additionally expose a bounded classified failure reason (or null after recovery) and
the last accepted retrieval time, without arbitrary external exception text.

**Evidence:**

- [`test_diagnostics_redact_location_and_stable_identity`](../../tests/test_compatibility_security.py) — `tests/test_compatibility_security.py::test_diagnostics_redact_location_and_stable_identity`
- [`test_source_availability_snapshot_cannot_mutate_coordinator_state`](../../tests/test_compatibility_security.py) — `tests/test_compatibility_security.py::test_source_availability_snapshot_cannot_mutate_coordinator_state`
- [`test_warning_entries_filter_independently_and_diagnostics_are_health_only`](../../tests/test_warning_entities.py) — `tests/test_warning_entities.py::test_warning_entries_filter_independently_and_diagnostics_are_health_only`
- [`test_warning_failure_reasons_are_bounded_and_private`](../../tests/test_warnings_coordinator.py) — `tests/test_warnings_coordinator.py::test_warning_failure_reasons_are_bounded_and_private`
- [`test_every_classified_warning_failure_reason_is_exposed`](../../tests/test_warnings_coordinator.py) — `tests/test_warnings_coordinator.py::test_every_classified_warning_failure_reason_is_exposed`
- [`test_warning_public_entities_follow_independent_source_and_recover`](../../tests/test_warning_entities.py) — `tests/test_warning_entities.py::test_warning_public_entities_follow_independent_source_and_recover`

### `CSP-005` — External FMI XML is bounded and entity-disabled

**Contract:** All integration-owned FMI XML parsing MUST reject Expat older than 2.7.2, enforce a
2 MiB input ceiling (16 MiB for the CAP warning feed and its embedded CAP), disable/reject internal
and external entity declarations, and never resolve an external resource. A bare external DTD MAY
remain inert. Malformed/empty XML and unexpected parser shapes MUST be classified rather than
passed into runtime state.

**Evidence:**

- [`test_entity_declarations_are_rejected`](../../tests/test_xml_parser.py) — `tests/test_xml_parser.py::test_entity_declarations_are_rejected`
- [`test_external_dtd_is_not_resolved`](../../tests/test_xml_parser.py) — `tests/test_xml_parser.py::test_external_dtd_is_not_resolved`
- [`test_xml_payload_byte_size_is_bounded`](../../tests/test_xml_parser.py) — `tests/test_xml_parser.py::test_xml_payload_byte_size_is_bounded`
- [`test_unsupported_expat_runtime_is_rejected`](../../tests/test_xml_parser.py) — `tests/test_xml_parser.py::test_unsupported_expat_runtime_is_rejected`
- [`test_warning_feed_ceiling_is_separate_from_the_shared_xml_limit`](../../tests/test_warnings_client.py) — `tests/test_warnings_client.py::test_warning_feed_ceiling_is_separate_from_the_shared_xml_limit`
- [`test_warning_large_valid_ring_and_exact_xml_boundary`](../../tests/test_warnings_client.py) — `tests/test_warnings_client.py::test_warning_large_valid_ring_and_exact_xml_boundary`
- [`test_warning_storm_sized_publication_stays_within_bounded_resources`](../../tests/test_warnings_client.py) — `tests/test_warnings_client.py::test_warning_storm_sized_publication_stays_within_bounded_resources`

### `CSP-006` — User state and transient external disclosure are explicit

**Contract:** FMI MAY receive transient place-search text or configured coordinates required for
the selected FMI request. Search text MUST NOT persist in config/logs/diagnostics. Entity state MAY
expose the configured place and weather factors to the Home Assistant user, but MUST NOT expose raw
external payloads, strike coordinates, immutable identity, or an opaque Best-time score.
Validated official localized warning fields MAY be presented according to `SNS-007`, without raw
CAP, source polygons, or configured coordinates in the warning representation.

**Evidence:**

- [`test_place_adapter_returns_only_validated_location_fields`](../../tests/test_fmi_contract.py) — `tests/test_fmi_contract.py::test_place_adapter_returns_only_validated_location_fields`
- [`test_best_time_selected_state_preserves_and_extends_attributes`](../../tests/test_lifecycle.py) — `tests/test_lifecycle.py::test_best_time_selected_state_preserves_and_extends_attributes`
- [`test_public_entity_and_forecast_contracts`](../../tests/test_lifecycle.py) — `tests/test_lifecycle.py::test_public_entity_and_forecast_contracts`
- [`test_warning_public_entities_follow_independent_source_and_recover`](../../tests/test_warning_entities.py) — `tests/test_warning_entities.py::test_warning_public_entities_follow_independent_source_and_recover`

### `CSP-007` — Stored test data is synthetic and sanitized

**Contract:** Offline fixtures MUST remain bounded synthetic data and MUST NOT contain captured
owner coordinates, private Home Assistant storage, or raw FMI responses. Live tests MUST NOT store
response weather values as artifacts.

**Evidence:**

- [`test_fixture_corpus_is_small_synthetic_and_sanitized`](../../tests/test_fmi_contract.py) — `tests/test_fmi_contract.py::test_fixture_corpus_is_small_synthetic_and_sanitized`
- [`test_public_support_contract_is_usable_and_privacy_safe`](../../tests/test_distribution.py) — `tests/test_distribution.py::test_public_support_contract_is_usable_and_privacy_safe`
