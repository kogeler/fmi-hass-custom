<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Live-Test Contract

## Assertions

### `LIV-001` — Real network is marker-isolated from ordinary tests

**Contract:** Only tests marked `live` MAY access FMI. Ordinary pytest entry points MUST deselect
live tests and block sockets; the live Make target MUST run in its explicit online contour while
retaining the Home Assistant test guard outside the narrow live fixture.

**Evidence:**

- [`test_every_pytest_entry_point_uses_automatic_xdist_workers`](../../tests/test_dependency_policy.py) — `tests/test_dependency_policy.py::test_every_pytest_entry_point_uses_automatic_xdist_workers`
- [`test_dependency_place_resolution_contract`](../../tests/test_live_fmi.py) — `tests/test_live_fmi.py::test_dependency_place_resolution_contract`
- [`test_home_assistant_live_entity_and_forecast_contract`](../../tests/test_live_fmi.py) — `tests/test_live_fmi.py::test_home_assistant_live_entity_and_forecast_contract`

### `LIV-002` — Live probes use only fixed public locations

**Contract:** Live requests MUST use public Helsinki place resolution, rounded Kilpisjärvi station-
area coordinates, and public Helsinki Kumpula station `FMISID 101004`. They MUST NOT use owner
coordinates, private station choices, secrets, Home Assistant storage, or captured response
fixtures.

**Evidence:**

- [`test_dependency_place_resolution_contract`](../../tests/test_live_fmi.py) — `tests/test_live_fmi.py::test_dependency_place_resolution_contract`
- [`test_dependency_northern_forecast_contract`](../../tests/test_live_fmi.py) — `tests/test_live_fmi.py::test_dependency_northern_forecast_contract`
- [`test_dependency_observation_contract`](../../tests/test_live_fmi.py) — `tests/test_live_fmi.py::test_dependency_observation_contract`

### `LIV-003` — Global live request volume is hard-bounded

**Contract:** All xdist workers MUST share one file-locked twelve-attempt budget and a two-request
semaphore. Dependency calls MAY retry once only for timeout/transport/server failure; request,
parser, shape, and Home Assistant probe failures MUST NOT retry. Attempt thirteen MUST fail before
network I/O.

**Evidence:**

- [`test_live_budget_is_shared_and_hard_bounded`](../../tests/test_live_contract.py) — `tests/test_live_contract.py::test_live_budget_is_shared_and_hard_bounded`
- [`test_live_budget_limits_parallel_requests`](../../tests/test_live_contract.py) — `tests/test_live_contract.py::test_live_budget_limits_parallel_requests`

### `LIV-004` — Dependency probes detect contract drift without exact weather assertions

**Contract:** Dependency probes MUST require usable model shapes, aware ordered timestamps, broad
physical ranges, and fresh observation data. Probability checks MUST cover all samples on the first
available future Europe/Helsinki local forecast date. They MUST NOT assert exact weather values,
place labels, conditions, or forecast length.

**Evidence:**

- [`test_dependency_northern_forecast_contract`](../../tests/test_live_fmi.py) — `tests/test_live_fmi.py::test_dependency_northern_forecast_contract`
- [`test_dependency_observation_contract`](../../tests/test_live_fmi.py) — `tests/test_live_fmi.py::test_dependency_observation_contract`
- [`test_live_probability_contract_requires_aligned_finite_first_future_day_values`](../../tests/test_live_contract.py) — `tests/test_live_contract.py::test_live_probability_contract_requires_aligned_finite_first_future_day_values`

### `LIV-005` — Home Assistant live probe verifies the public presentation path

**Contract:** The Home Assistant probe MUST load main and station weather entities, requested
metric sensors, hourly/daily forecast APIs, native/display units, apparent temperature, hourly PoP,
and local-day daily precipitation consistency through production coordinator/entity code. It MUST
remain within four setup calls and MUST NOT add a test-only provider/parser path.

**Evidence:**

- [`test_home_assistant_live_entity_and_forecast_contract`](../../tests/test_live_fmi.py) — `tests/test_live_fmi.py::test_home_assistant_live_entity_and_forecast_contract`
- [`test_live_ha_metric_contract_requires_apparent_temperature_and_pop`](../../tests/test_live_contract.py) — `tests/test_live_contract.py::test_live_ha_metric_contract_requires_apparent_temperature_and_pop`
- [`test_daily_precipitation_allows_only_independent_display_rounding`](../../tests/test_live_contract.py) — `tests/test_live_contract.py::test_daily_precipitation_allows_only_independent_display_rounding`

### `LIV-006` — Live FMI remains a required isolated CI gate

**Contract:** CI MUST run the exact bounded live suite after offline quality for pull requests and
`master` pushes without repository secrets. An FMI outage MUST remain visible and blocking; it
MUST NOT be hidden by weakening assertions or converting the job to optional.

**Evidence:**

- [`test_ci_preserves_hacs_security_and_compatibility_gates`](../../tests/test_ci_policy.py) — `tests/test_ci_policy.py::test_ci_preserves_hacs_security_and_compatibility_gates`
- [`test_workflow_set_is_minimal_event_driven_and_fully_pinned`](../../tests/test_ci_policy.py) — `tests/test_ci_policy.py::test_workflow_set_is_minimal_event_driven_and_fully_pinned`
