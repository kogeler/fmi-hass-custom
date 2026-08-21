<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Time And Missing-Data Maintenance

Normative sun-symbol, timezone, invalid-value, and Best-time requirements are owned exclusively by
[the time and missing-data contract](../contracts/TIME_AND_MISSING_DATA.md). Daily forecast
calendar rules are owned by [the forecast-semantics contract](../contracts/FORECAST_SEMANTICS.md).

## Design Rationale

Home Assistant's configured timezone is the only reliable calendar context for entities; the host
timezone is not a user contract. Polar sun events may be incomplete, so the selected clear-symbol
fallback is deterministic rather than an inferred astronomical claim.

Best time is a transparent convenience ordering under stored user limits. It is intentionally not
a medical, heat, lightning, or activity-safety score. The exact candidate set, hard gates, ordering,
and result states live only in `TIM-003` through `TIM-007` so future changes cannot silently diverge
between code and prose.

## Change Checklist

1. Update the affected `TIM-*` assertion and its evidence together.
2. Test aware/naive/missing timestamps, current-day exhaustion, calendar boundaries, and stale-state
   clearing.
3. Test every hard-gate boundary and every ordering tie independently when changing Best time.
4. Preserve stored option keys/values and registry state unless an explicit migration is proven.
5. Run `make test-full`, `make type-check`, and `make validate`.
