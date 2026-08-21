<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Dependency Contract

## Assertions

### `DEP-001` — PEP 621 owns every direct Python dependency

**Contract:** Root `pyproject.toml` MUST own exact integration runtime dependencies and the complete
direct dev set; `tools/lint/pyproject.toml` MUST own Ruff alone. Manifest requirements MUST exactly
mirror root runtime dependencies. No other direct Python dependency manifest MAY be maintained.

**Evidence:**

- [`test_pep621_owns_every_direct_python_dependency`](../../tests/test_dependency_policy.py) — `tests/test_dependency_policy.py::test_pep621_owns_every_direct_python_dependency`

### `DEP-002` — Exactly three generated hash locks exist

**Contract:** `requirements.txt`, `requirements-dev.txt`, and `requirements-lint.txt` MUST be the
only generated locks, MUST contain exact pins with SHA-256 hashes, and MUST preserve their runtime,
development, and Ruff audiences. They MUST NOT be hand-edited or replaced by `.in` files or a
`requirements/` hierarchy.

**Evidence:**

- [`test_exactly_three_generated_hash_locks_are_split_by_audience`](../../tests/test_dependency_policy.py) — `tests/test_dependency_policy.py::test_exactly_three_generated_hash_locks_are_split_by_audience`
- [`test_snapshot_rejects_hashless_pin`](../../tests/test_dependency_snapshot.py) — `tests/test_dependency_snapshot.py::test_snapshot_rejects_hashless_pin`

### `DEP-003` — Resolver bootstrap is the sole inline install exception

**Contract:** The toolbox resolver stage MAY contain only the exact wheel-only bootstrap required
to generate its locks. The dev image MUST install the hashed dev lock and run `pip check`; no other
container/workflow/script MAY introduce an inline Python install set.

**Evidence:**

- [`test_resolver_bootstrap_is_the_only_inline_install_set`](../../tests/test_dependency_policy.py) — `tests/test_dependency_policy.py::test_resolver_bootstrap_is_the_only_inline_install_set`

### `DEP-004` — Project tooling runs only through confined Make targets

**Contract:** Project-aware Python, Home Assistant, validation, dependency, and container work MUST
run through the supported Make surface. Source MUST be tar-streamed into private tmpfs without a
checkout/virtualenv/socket bind; project containers MUST use the documented rootless, read-only,
capability-dropped, bounded, offline-by-default confinement. Ruff MAY use only its separate hashed
wheel-only host environment.

**Evidence:**

- [`test_toolbox_policy_streams_source_and_enforces_confinement`](../../tests/test_dependency_policy.py) — `tests/test_dependency_policy.py::test_toolbox_policy_streams_source_and_enforces_confinement`
- [`test_make_target_surface_has_no_legacy_or_duplicate_execution_path`](../../tests/test_dependency_policy.py) — `tests/test_dependency_policy.py::test_make_target_surface_has_no_legacy_or_duplicate_execution_path`
- [`test_copied_distribution_imports_from_empty_config`](../../tests/test_distribution.py) — `tests/test_distribution.py::test_copied_distribution_imports_from_empty_config`

### `DEP-005` — Pytest parallelism is automatic and globally bounded by Make

**Contract:** Every pytest entry point MUST use `-n auto --dist=worksteal`; a serial default or
special serial suite MUST NOT exist. Make target orchestration MUST remain globally serialized so
separate containers and artifact writers do not race.

**Evidence:**

- [`test_every_pytest_entry_point_uses_automatic_xdist_workers`](../../tests/test_dependency_policy.py) — `tests/test_dependency_policy.py::test_every_pytest_entry_point_uses_automatic_xdist_workers`
- [`test_make_target_surface_has_no_legacy_or_duplicate_execution_path`](../../tests/test_dependency_policy.py) — `tests/test_dependency_policy.py::test_make_target_surface_has_no_legacy_or_duplicate_execution_path`

### `DEP-006` — Vulnerability exceptions are exact and self-expiring

**Contract:** Reviewed audit MUST accept only exact package/version/advisory tuples. A new finding,
stale exception, or exception for another version MUST fail; the integration-owned runtime closure
MUST NOT gain an accepted exception silently.

**Evidence:**

- [`test_accepts_only_exact_reviewed_findings`](../../tests/test_dependency_audit.py) — `tests/test_dependency_audit.py::test_accepts_only_exact_reviewed_findings`
- [`test_rejects_unexpected_vulnerability`](../../tests/test_dependency_audit.py) — `tests/test_dependency_audit.py::test_rejects_unexpected_vulnerability`
- [`test_rejects_stale_exception`](../../tests/test_dependency_audit.py) — `tests/test_dependency_audit.py::test_rejects_stale_exception`
- [`test_rejects_exception_for_another_package_version`](../../tests/test_dependency_audit.py) — `tests/test_dependency_audit.py::test_rejects_exception_for_another_package_version`

### `DEP-007` — Dependency submission derives all lock graphs offline

**Contract:** The snapshot generator MUST parse exactly the three hash locks, cross-check direct
ownership against PEP 621, reject unknown/hashless/missing content, and emit runtime/development
scope without network or credentials. Generated snapshot JSON MUST remain ignored evidence.

**Evidence:**

- [`test_snapshot_contains_all_three_exact_lock_graphs`](../../tests/test_dependency_snapshot.py) — `tests/test_dependency_snapshot.py::test_snapshot_contains_all_three_exact_lock_graphs`
- [`test_snapshot_rejects_unrecognized_lock_content`](../../tests/test_dependency_snapshot.py) — `tests/test_dependency_snapshot.py::test_snapshot_rejects_unrecognized_lock_content`
- [`test_snapshot_rejects_missing_direct_dependency`](../../tests/test_dependency_snapshot.py) — `tests/test_dependency_snapshot.py::test_snapshot_rejects_missing_direct_dependency`
