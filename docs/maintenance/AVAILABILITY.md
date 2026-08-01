<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Source Availability Policy

This policy defines how the integration behaves when one FMI data source is unavailable. It addresses forecast failures disabling observations and applies to the stable Home Assistant environment selected by the maintenance plan.

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

## Recovery and lifecycle

Coordinator entities register only the listener managed by Home Assistant's `CoordinatorEntity` lifecycle. The first entity listener starts periodic refreshes, so an unavailable source can recover without a reload. A later successful refresh restores availability and current/forecast data as applicable. Unload removes entity listeners and the config-entry update listener; reload follows the same independent setup policy.

Source logs are transition-based: one warning when a source becomes unavailable and one informational message when it recovers. Repeated failures in the same outage do not emit the same source warning on every refresh. Cancellation and unrelated exception classes are not caught as source availability events.

## Optional sources

Lightning and sea-level work remains optional to current weather. An exception at either optional update boundary clears only that source and does not fail the primary coordinator. Detailed transport, parsing, freshness, geocoding, and option behavior remains assigned to S09.

Policy evidence: forecast failure disabling observations report, checked 2026-07-31.
