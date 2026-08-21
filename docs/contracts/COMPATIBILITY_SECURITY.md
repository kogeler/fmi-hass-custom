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
successful skip, while a recreated prerelease MUST still match its requested channel.

**Evidence:**

- [`test_ci_preserves_hacs_security_and_compatibility_gates`](../../tests/test_ci_policy.py) — `tests/test_ci_policy.py::test_ci_preserves_hacs_security_and_compatibility_gates`
- [`test_missing_prerelease_is_an_informational_skip`](../../tests/test_compatibility_helper.py) — `tests/test_compatibility_helper.py::test_missing_prerelease_is_an_informational_skip`
- [`test_recreated_prerelease_must_still_match_the_channel`](../../tests/test_compatibility_helper.py) — `tests/test_compatibility_helper.py::test_recreated_prerelease_must_still_match_the_channel`

### `CSP-003` — Logs exclude private external data

**Contract:** The integration MUST NOT configure the process-wide root logger. Logs MAY contain
source names, transitions, HTTP status classes, and exception class names, but MUST NOT contain
configured coordinates, coordinate-derived identity, place-search text, raw response/payload, or
arbitrary external exception text. The upstream-client privacy filter MUST remain scoped and
idempotent.

**Evidence:**

- [`test_importing_constants_does_not_configure_root_logging`](../../tests/test_runtime_audit.py) — `tests/test_runtime_audit.py::test_importing_constants_does_not_configure_root_logging`
- [`test_external_error_details_do_not_include_payload_or_coordinates`](../../tests/test_compatibility_security.py) — `tests/test_compatibility_security.py::test_external_error_details_do_not_include_payload_or_coordinates`
- [`test_place_flow_does_not_log_query_or_malformed_result`](../../tests/test_compatibility_security.py) — `tests/test_compatibility_security.py::test_place_flow_does_not_log_query_or_malformed_result`
- [`test_upstream_privacy_filter_is_scoped_and_idempotent`](../../tests/test_compatibility_security.py) — `tests/test_compatibility_security.py::test_upstream_privacy_filter_is_scoped_and_idempotent`

### `CSP-004` — Diagnostics expose only sanitized health metadata

**Contract:** Downloadable diagnostics MUST expose only sanitized configuration/options, config
version, polling cadence, coordinator success, and source availability. They MUST NOT expose exact
coordinates, place/weather values, entry/entity/legacy identity, or external payloads; exported
availability mappings MUST NOT mutate coordinator state.

**Evidence:**

- [`test_diagnostics_redact_location_and_stable_identity`](../../tests/test_compatibility_security.py) — `tests/test_compatibility_security.py::test_diagnostics_redact_location_and_stable_identity`
- [`test_source_availability_snapshot_cannot_mutate_coordinator_state`](../../tests/test_compatibility_security.py) — `tests/test_compatibility_security.py::test_source_availability_snapshot_cannot_mutate_coordinator_state`

### `CSP-005` — External FMI XML is bounded and entity-disabled

**Contract:** All integration-owned FMI XML parsing MUST reject Expat older than 2.7.2, enforce a
2 MiB input ceiling, disable/reject internal and external entity declarations, and never resolve an
external resource. A bare external DTD MAY remain inert. Malformed/empty XML and unexpected parser
shapes MUST be classified rather than passed into runtime state.

**Evidence:**

- [`test_entity_declarations_are_rejected`](../../tests/test_xml_parser.py) — `tests/test_xml_parser.py::test_entity_declarations_are_rejected`
- [`test_external_dtd_is_not_resolved`](../../tests/test_xml_parser.py) — `tests/test_xml_parser.py::test_external_dtd_is_not_resolved`
- [`test_xml_payload_byte_size_is_bounded`](../../tests/test_xml_parser.py) — `tests/test_xml_parser.py::test_xml_payload_byte_size_is_bounded`
- [`test_unsupported_expat_runtime_is_rejected`](../../tests/test_xml_parser.py) — `tests/test_xml_parser.py::test_unsupported_expat_runtime_is_rejected`

### `CSP-006` — User state and transient external disclosure are explicit

**Contract:** FMI MAY receive transient place-search text or configured coordinates required for
the selected FMI request. Search text MUST NOT persist in config/logs/diagnostics. Entity state MAY
expose the configured place and weather factors to the Home Assistant user, but MUST NOT expose raw
external payloads, strike coordinates, immutable identity, or an opaque Best-time score.

**Evidence:**

- [`test_place_adapter_returns_only_validated_location_fields`](../../tests/test_fmi_contract.py) — `tests/test_fmi_contract.py::test_place_adapter_returns_only_validated_location_fields`
- [`test_best_time_selected_state_preserves_and_extends_attributes`](../../tests/test_lifecycle.py) — `tests/test_lifecycle.py::test_best_time_selected_state_preserves_and_extends_attributes`
- [`test_public_entity_and_forecast_contracts`](../../tests/test_lifecycle.py) — `tests/test_lifecycle.py::test_public_entity_and_forecast_contracts`

### `CSP-007` — Stored test data is synthetic and sanitized

**Contract:** Offline fixtures MUST remain bounded synthetic data and MUST NOT contain captured
owner coordinates, private Home Assistant storage, or raw FMI responses. Live tests MUST NOT store
response weather values as artifacts.

**Evidence:**

- [`test_fixture_corpus_is_small_synthetic_and_sanitized`](../../tests/test_fmi_contract.py) — `tests/test_fmi_contract.py::test_fixture_corpus_is_small_synthetic_and_sanitized`
- [`test_public_support_contract_is_usable_and_privacy_safe`](../../tests/test_distribution.py) — `tests/test_distribution.py::test_public_support_contract_is_usable_and_privacy_safe`
