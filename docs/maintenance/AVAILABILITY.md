<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Source Availability Policy

This policy defines how the integration behaves when one FMI data source is unavailable. It is
the current source-isolation contract for the supported Home Assistant environment.

Last verified against current code: 2026-08-20.

## Current conditions and setup

The primary coordinator requests forecast-backed current weather by coordinates. If that request fails or returns no data, it requests an observation by the config entry's place title. Failure includes FMI client/server errors, request-library transport errors, invalid XML/parser output, and malformed external model shapes. The fallback observation becomes the current weather for the primary weather entity and its current-condition sensors; it does not fabricate forecast data.

When an observation station is configured, its coordinator performs the first refresh independently from the primary coordinator. Initial entry setup follows this matrix:

| Primary current or place fallback | Configured station | Setup result |
|---|---|---|
| Available | Any result or not configured | Load the entry. |
| Unavailable | Available | Load the entry with primary entities unavailable and the station observation entity available. |
| Unavailable | Unavailable or not configured | Enter `setup_retry`. |

A configured station failure does not disable forecast-backed entities. A primary current failure does not disable a working station observation entity.

## Forecast and stale data

The forecast collection is independent from current conditions. A transport, parser, or validated external-shape error, `None`, or empty result clears the previous collection and exposes an empty forecast while current conditions remain available. The integration does not retain an old forecast without freshness metadata.

If both primary current and place fallback fail after a prior success, the coordinator clears current weather and forecast data and marks its dependent entities unavailable. It does not expose stale current values as available.

A timeout in the primary current/forecast path follows the same stale-data policy. Optional lightning and sea-level updates are outside that primary timeout boundary so their failures cannot invalidate current conditions.

Current PoP and thunderstorm probability are replaced with their forecast-backed current owner;
future values are replaced with the forecast collection by timestamp. A missing/invalid supplement
does not invalidate its weather sample or any unrelated sensor. It makes only the corresponding
probability sensor/forecast field unavailable. Owner replacement, failure, empty data, and timeout
clear the applicable values so an earlier probability cannot remain stale; later valid data
recovers without reload.

Best-time availability distinguishes a valid empty calculation from unusable data. A healthy
forecast with no remaining current-local-day hour, or with complete hours that all fail user
limits, exposes the available `no_suitable_time` token. Disabled, failed, empty, timestamp-unusable,
or entirely incomplete remaining forecast data makes only Best-time unavailable. Both outcomes
clear every prior selected value/attribute and recover on a later complete refresh.

## Recovery and lifecycle

Coordinator entities register only the listener managed by Home Assistant's `CoordinatorEntity` lifecycle. The first entity listener starts periodic refreshes, so an unavailable source can recover without a reload. A later successful refresh restores availability and current/forecast data as applicable. Unload removes entity listeners and the config-entry update listener; reload follows the same independent setup policy.

Source logs are transition-based: one warning when a source becomes unavailable and one
informational message when it recovers. Repeated failures in the same outage do not emit the same
source warning on every refresh. Primary FMI boundaries classify only their documented exception
set. Optional boundaries classify any ordinary exception locally so optional failures remain
isolated; cancellation still propagates.

## Optional sources

Lightning and sea-level work remains optional to current weather. An exception at either optional
update boundary clears only that source and does not fail the primary coordinator. Detailed
transport, parsing, freshness, local geometry, and option behavior is defined in
`OPTIONAL_SOURCES.md`.

A successful lightning response with no qualifying strikes is valid empty data: the lightning
sensor remains available with the stable `no_strikes` state and no dynamic strike attributes. A
lightning transport, payload, parser, or unusable-data failure makes only that sensor unavailable
and clears its prior state and dynamic attributes. Either state can recover on the next successful
coordinator refresh without reload.

Verification: `tests/test_availability.py` and `tests/test_lifecycle.py` cover setup matrices,
source-local failure, stale clearing, transition logs, and recovery.
