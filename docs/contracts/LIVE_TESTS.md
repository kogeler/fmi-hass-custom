<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Live-Test Contract

## Assertions

### `LIV-001` — Real network is marker-isolated from ordinary tests

**Contract:** Only tests marked `live` MAY access FMI. Ordinary pytest entry points MUST deselect
live tests and block sockets; the live Make target MUST run in its explicit online contour while
retaining the Home Assistant test guard outside the narrow live fixture. Every pytest entry point,
including the live target that clears the project `addopts`, MUST disable the `respx` plugin so
that Home Assistant aliases `httpx` before it is imported.
Marked HA HTTP probes MUST disable only the test helper's cross-loop resolver mock using its
provided fixture while retaining production HTTP, DNS, and coordinator behavior.

**Evidence:**

- [`test_every_pytest_entry_point_uses_automatic_xdist_workers`](../../tests/test_dependency_policy.py) — `tests/test_dependency_policy.py::test_every_pytest_entry_point_uses_automatic_xdist_workers`
- [`test_pytest_entry_points_that_clear_addopts_still_disable_respx`](../../tests/test_dependency_policy.py) — `tests/test_dependency_policy.py::test_pytest_entry_points_that_clear_addopts_still_disable_respx`
- [`test_home_assistant_live_entity_and_forecast_contract`](../../tests/test_live_fmi.py) — `tests/test_live_fmi.py::test_home_assistant_live_entity_and_forecast_contract`

### `LIV-002` — Live probes use only fixed public locations

**Contract:** Live requests MUST use public Helsinki place resolution, rounded Kilpisjärvi station-
area coordinates, and public Helsinki Kumpula station `FMISID 101004`. They MUST NOT use owner
coordinates, private station choices, secrets, Home Assistant storage, or captured response
fixtures.
CAP locale probes MAY fetch the fixed Finnish/Swedish feeds using the same public Helsinki point;
the English feed MUST also be exercised through the Home Assistant entity probe.
Offline recognition checks inside these live probes MAY transiently use a vertex from a public
CAP polygon; this MUST NOT cause another network request, coordinate disclosure, or saved payload.

**Evidence:**

- [`test_home_assistant_live_entity_and_forecast_contract`](../../tests/test_live_fmi.py) — `tests/test_live_fmi.py::test_home_assistant_live_entity_and_forecast_contract`
- [`test_dependency_northern_forecast_contract`](../../tests/test_live_fmi.py) — `tests/test_live_fmi.py::test_dependency_northern_forecast_contract`
- [`test_live_warning_locale_uses_production_coordinator`](../../tests/test_live_warnings.py) — `tests/test_live_warnings.py::test_live_warning_locale_uses_production_coordinator`

### `LIV-003` — Global live request volume is hard-bounded

**Contract:** All xdist workers MUST share one file-locked twelve-attempt budget and a two-request
semaphore. Dependency calls MAY retry once only for timeout/transport/server failure; request,
parser, shape, and Home Assistant probe failures MUST NOT retry. Attempt thirteen MUST fail before
network I/O.

**Evidence:**

- [`test_live_budget_is_shared_and_hard_bounded`](../../tests/test_live_contract.py) — `tests/test_live_contract.py::test_live_budget_is_shared_and_hard_bounded`
- [`test_live_budget_limits_parallel_requests`](../../tests/test_live_contract.py) — `tests/test_live_contract.py::test_live_budget_limits_parallel_requests`
- [`test_live_warning_allocation_includes_retries_and_all_locales`](../../tests/test_live_contract.py) — `tests/test_live_contract.py::test_live_warning_allocation_includes_retries_and_all_locales`

### `LIV-004` — Dependency probes detect contract drift without exact weather assertions

**Contract:** Dependency probes MUST require usable model shapes, aware ordered timestamps, broad
physical ranges, and fresh observation data. Probability checks MUST cover all samples on the first
available future Europe/Helsinki local forecast date. They MUST NOT assert exact weather values,
place labels, conditions, or forecast length.

**Evidence:**

- [`test_dependency_northern_forecast_contract`](../../tests/test_live_fmi.py) — `tests/test_live_fmi.py::test_dependency_northern_forecast_contract`
- [`test_home_assistant_live_entity_and_forecast_contract`](../../tests/test_live_fmi.py) — `tests/test_live_fmi.py::test_home_assistant_live_entity_and_forecast_contract`
- [`test_live_probability_contract_requires_aligned_finite_first_future_day_values`](../../tests/test_live_contract.py) — `tests/test_live_contract.py::test_live_probability_contract_requires_aligned_finite_first_future_day_values`

### `LIV-005` — Home Assistant live probe verifies the public presentation path

**Contract:** The Home Assistant probe MUST load main and station weather entities, requested
metric sensors, hourly/daily forecast APIs, native/display units, apparent temperature, hourly PoP,
and local-day daily precipitation consistency through production coordinator/entity code. It MUST
also validate the resolved public point and station model/freshness, current probabilities, and
English warning entities through the same production paths. It MUST remain within five setup calls
including optional fallback and MUST NOT add a test-only provider/parser path. Finnish/Swedish CAP
probes MUST use production warning coordinators without repeating unrelated weather setup.
Nonempty operational publications MUST also demonstrate that every surviving source warning
survives production parsing at its own public polygon boundary, independently of zero matches at
Helsinki, with the original text language expected by `WRN-003` fallback. Each CAP probe MUST report
its public structural counts (entries, operational messages, boundary checks, bytes) in the live
target output, without message text or coordinates.

**Evidence:**

- [`test_home_assistant_live_entity_and_forecast_contract`](../../tests/test_live_fmi.py) — `tests/test_live_fmi.py::test_home_assistant_live_entity_and_forecast_contract`
- [`test_live_ha_metric_contract_requires_apparent_temperature_and_pop`](../../tests/test_live_contract.py) — `tests/test_live_contract.py::test_live_ha_metric_contract_requires_apparent_temperature_and_pop`
- [`test_daily_precipitation_allows_only_independent_display_rounding`](../../tests/test_live_contract.py) — `tests/test_live_contract.py::test_daily_precipitation_allows_only_independent_display_rounding`
- [`test_warning_live_recognition_rejects_silent_parser_loss`](../../tests/test_warning_live_contract.py) — `tests/test_warning_live_contract.py::test_warning_live_recognition_rejects_silent_parser_loss`
- [`test_warning_live_recognition_checks_source_identity_and_allows_language_fallback`](../../tests/test_warning_live_contract.py) — `tests/test_warning_live_contract.py::test_warning_live_recognition_checks_source_identity_and_allows_language_fallback`
- [`test_warning_live_recognition_rejects_incoherent_language`](../../tests/test_warning_live_contract.py) — `tests/test_warning_live_contract.py::test_warning_live_recognition_rejects_incoherent_language`
- [`test_warning_live_recognition_classifies_missing_source_elements`](../../tests/test_warning_live_contract.py) — `tests/test_warning_live_contract.py::test_warning_live_recognition_classifies_missing_source_elements`
- [`test_warning_live_structure_summary_contains_only_counts`](../../tests/test_warning_live_contract.py) — `tests/test_warning_live_contract.py::test_warning_live_structure_summary_contains_only_counts`
- [`test_live_target_reports_cap_structure_after_the_request_counter`](../../tests/test_live_contract.py) — `tests/test_live_contract.py::test_live_target_reports_cap_structure_after_the_request_counter`

### `LIV-006` — Live FMI remains a required isolated CI gate

**Contract:** CI MUST run the exact bounded live suite after offline quality for pull requests and
`master` pushes without repository secrets. An FMI outage MUST remain visible and blocking; it
MUST NOT be hidden by weakening assertions or converting the job to optional.

**Evidence:**

- [`test_ci_preserves_hacs_security_and_compatibility_gates`](../../tests/test_ci_policy.py) — `tests/test_ci_policy.py::test_ci_preserves_hacs_security_and_compatibility_gates`
- [`test_workflow_set_is_minimal_event_driven_and_fully_pinned`](../../tests/test_ci_policy.py) — `tests/test_ci_policy.py::test_workflow_set_is_minimal_event_driven_and_fully_pinned`
