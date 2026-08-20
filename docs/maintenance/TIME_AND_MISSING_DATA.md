<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Time and Missing-Data Policy

Last verified against current code: 2026-08-20.

## Sun Events and Weather Symbols

FMI symbol `1` means clear conditions. When Home Assistant supplies both timezone-aware sunrise and sunset values in chronological order, the integration reports `clear-night` at or outside those boundaries and `sunny` between them.

At high latitudes, either event may be absent during midnight sun or polar night. In that case the integration cannot infer night safely and returns FMI's daytime `sunny` meaning. It uses the same deterministic fallback for a single missing event, a timezone-naive event, or an inconsistent event order. No synthetic fallback is applied to other FMI symbols.

Unknown, non-integral, malformed, NaN, and infinite symbol codes produce no Home Assistant condition (`None`) instead of an invented condition or an exception. Integral numeric strings are accepted because external payload types are normalized at the integration boundary.

This policy defines deterministic behavior for incomplete polar sun events and extends it to malformed or inconsistent event data.

## Calendar and Timestamp Rules

- Home Assistant's configured local timezone is authoritative; integration code does not use the host timezone.
- Best-time candidates must have timezone-aware timestamps on exactly the current Home Assistant
  local date and must not precede the current Home Assistant time. Full date equality prevents
  month, year, leap, or DST boundaries from admitting another local day.
- Forecast samples with missing or timezone-naive timestamps are ignored. Hourly timestamps exposed to Home Assistant remain timezone-aware UTC ISO strings.
- Daily forecasts continue to group by complete Home Assistant local dates and expose each local midnight as a UTC ISO timestamp. Tests cover month/year boundaries, leap day, and both Europe/Helsinki DST transitions.

## Incomplete FMI Values

The current stable FMI client models values as numeric wrappers, but the integration treats the external boundary defensively:

- finite numbers and numeric strings are normalized to `float`;
- booleans, malformed strings, `None`, NaN, and infinities become unavailable;
- missing forecast fields become `None` without aborting the remaining sample;
- empty forecast collections return empty hourly/daily lists;
- best-time selection skips incomplete candidates and never substitutes current observations,
  current time, or a value outside configured limits.

## Best Time Of Day

The sensor selects from the coordinator's configured-interval forecast series. Every evaluated
candidate requires a finite symbol, air temperature, feels-like temperature, humidity, sustained
wind, preceding-hour precipitation, PoP, and thunderstorm probability. PoP and thunder probability
must also be within 0–100. The existing accepted-symbol list and persisted humidity, wind, and
precipitation limits are inclusive hard gates. Persisted temperature limits apply to feels-like
temperature; their option keys and stored values are unchanged.

For every eligible remaining hour, the sensor minimizes this exact tuple:

```text
(
  thunderstorm probability,
  distance from the configured feels-like midpoint,
  precipitation probability,
  preceding-hour precipitation amount,
  aware timestamp,
)
```

No weighted comfort score is created. Humidity and wind are not scored a second time because they
already contribute to the selected client's feels-like calculation. An exact tie selects the
earliest hour.

Result states are distinct:

- a selected hour is the existing `HH:MM` state and retains location, aware time, air temperature,
  humidity, wind, and precipitation attributes; apparent temperature, PoP, and thunder probability
  are additive attributes;
- a healthy forecast with no remaining current-day hour, or at least one complete hour but none
  passing the limits, is available as `no_suitable_time` with no dynamic selection attributes;
- disabled, failed, empty, timestamp-unusable, or entirely incomplete remaining forecast data is
  unavailable and has no dynamic selection attributes.

Every calculation first clears the previous result, so yesterday's or an earlier refresh's
selection cannot survive. A later complete forecast recovers the same entity without reload.
Submitted inverted min/max pairs are rejected by the options form without partial persistence.
Historical inverted values remain loadable and unchanged so the user can correct them explicitly;
until corrected they produce the valid `no_suitable_time` outcome.

## Optional-Source Time Rules

Lightning and sea-level request windows use Home Assistant's aware UTC clock. Lightning payload
timestamps must be aware, no later than the current refresh time, and no older than the configured
inclusive maximum age. Sea-level timestamps must be aware and are normalized to UTC before
sorting and exposure. Malformed or naive optional-source timestamps make only the owning record or
source unavailable; they never fall back to host-local time. See `OPTIONAL_SOURCES.md`.
