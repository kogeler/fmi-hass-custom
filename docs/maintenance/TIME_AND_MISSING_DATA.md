<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Time and Missing-Data Policy

## Sun Events and Weather Symbols

FMI symbol `1` means clear conditions. When Home Assistant supplies both timezone-aware sunrise and sunset values in chronological order, the integration reports `clear-night` at or outside those boundaries and `sunny` between them.

At high latitudes, either event may be absent during midnight sun or polar night. In that case the integration cannot infer night safely and returns FMI's daytime `sunny` meaning. It uses the same deterministic fallback for a single missing event, a timezone-naive event, or an inconsistent event order. No synthetic fallback is applied to other FMI symbols.

Unknown, non-integral, malformed, NaN, and infinite symbol codes produce no Home Assistant condition (`None`) instead of an invented condition or an exception. Integral numeric strings are accepted because external payload types are normalized at the integration boundary.

This policy defines deterministic behavior for incomplete polar sun events and extends it to malformed or inconsistent event data.

## Calendar and Timestamp Rules

- Home Assistant's configured local timezone is authoritative; integration code does not use the host timezone.
- Best-condition candidates must have timezone-aware timestamps on exactly the current Home Assistant local date. Full date equality replaces the former day-of-month arithmetic, so month, year, and leap boundaries cannot include the next day accidentally.
- Forecast samples with missing or timezone-naive timestamps are ignored. Hourly timestamps exposed to Home Assistant remain timezone-aware UTC ISO strings.
- Daily forecasts continue to group by complete Home Assistant local dates and expose each local midnight as a UTC ISO timestamp. Tests cover month/year boundaries, leap day, and both Europe/Helsinki DST transitions.

## Incomplete FMI Values

The current stable FMI client models values as numeric wrappers, but the integration treats the external boundary defensively:

- finite numbers and numeric strings are normalized to `float`;
- booleans, malformed strings, `None`, NaN, and infinities become unavailable;
- missing forecast fields become `None` without aborting the remaining sample;
- empty forecast collections return empty hourly/daily lists;
- best-condition selection skips incomplete candidates and retains a timezone-aware current timestamp when one is valid.

## Optional-Source Time Rules

Lightning and sea-level request windows use Home Assistant's aware UTC clock. Lightning payload
timestamps must be aware, no later than the current refresh time, and no older than the configured
inclusive maximum age. Sea-level timestamps must be aware and are normalized to UTC before
sorting and exposure. Malformed or naive optional-source timestamps make only the owning record or
source unavailable; they never fall back to host-local time. See `OPTIONAL_SOURCES.md`.
