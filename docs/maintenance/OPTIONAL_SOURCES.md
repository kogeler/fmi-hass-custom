<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Optional Lightning and Sea-Level Sources

## Availability and freshness

Lightning and sea-level data are independent optional sources. A failure, empty result, or malformed response clears that source's previous data and makes only its sensor unavailable. Current weather, observations, and forecasts continue updating. A later valid response restores the optional sensor automatically.

All optional FMI HTTP requests use Home Assistant's shared aiohttp session. Each request has a 2-second connect timeout, a 3-second read timeout, a 5-second total timeout, and a 2 MiB response limit. HTTP client errors, server errors, transport failures, timeouts, empty responses, invalid XML, and invalid data shapes are classified separately in transition logs. The integration does not retry optional requests within one coordinator update.

XML parsing and reverse geocoding run in Home Assistant's executor. Lightning position and value arrays must have equal lengths. Individual malformed lightning rows are discarded; an unsafe array mismatch rejects the complete lightning response. Supported sea-level records require a finite numeric value and a timezone-aware ISO timestamp. All timestamps stored for Home Assistant are aware UTC datetimes.

## Lightning maximum age

`lightning_max_age_minutes` is configurable from 1 through 1440 minutes. The default is 1440 minutes, preserving the previous one-day query window for existing entries that do not yet store this option. No config-entry version migration is required: the coordinator and options form apply the default lazily, and the next options save persists it.

The age boundary is inclusive. A strike exactly the configured age is retained; a strike one second older is discarded. Future, missing, malformed, non-finite, or millisecond-scale timestamps are discarded. The configured age also determines the FMI query start time, reducing unnecessary response data for shorter windows.

## Reverse geocoding

Lightning remains useful without address lookup: UTC time, coordinates, distance, strike count, peak current, cloud cover, and ellipse size are preserved. Address lookup is best effort and never controls sensor availability.

The public Nominatim service is limited process-wide to one request every 15 seconds, and at most one previously unseen coordinate is submitted per coordinator update. Results and failures are cached in memory for the coordinator lifetime. When the cache or rate limit cannot provide an address, the sensor displays raw strike coordinates. Requests use an identifying project user agent, and the lightning sensor exposes OpenStreetMap attribution.

This bounded behavior follows the public Nominatim usage policy, which discourages periodic bulk geocoding, requires caching and an identifying user agent, and limits regularly running jobs to four requests per minute. The policy and Home Assistant async guidance were checked on 2026-07-31:

- <https://operations.osmfoundation.org/policies/nominatim/>
- <https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/inject-websession/>
- <https://developers.home-assistant.io/docs/asyncio_blocking_operations/>

Nominatim is a best-effort external service without an availability guarantee. Its address enrichment may remain unresolved while FMI data continues to work.

## Coordinate disclosure

Lightning queries send the configured bounding box to FMI, and sea-level queries send the configured latitude/longitude to FMI. Reverse geocoding sends only selected lightning-strike coordinates to Nominatim; it does not send the configured Home Assistant coordinates directly.
