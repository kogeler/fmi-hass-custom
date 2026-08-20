<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Optional Lightning and Sea-Level Sources

Last verified against current code: 2026-08-19.

## Availability and freshness

Lightning and sea-level data are independent optional sources. A successful lightning response
with no qualifying strikes is available empty data and exposes the stable `no_strikes` state with
no dynamic strike attributes. A lightning failure or malformed/unusable response clears previous
data and makes only its sensor unavailable. Sea-level failure, empty data, or malformed data clears
that source and makes only its sensor unavailable. Current weather, observations, and forecasts
continue updating. A later valid response restores either optional sensor automatically.

All optional FMI HTTP requests use Home Assistant's shared aiohttp session. Each request has a 2-second connect timeout, a 3-second read timeout, a 5-second total timeout, and a 2 MiB response limit. HTTP client errors, server errors, transport failures, timeouts, empty responses, invalid XML, and invalid data shapes are classified separately in transition logs. The integration does not retry optional requests within one coordinator update.

XML parsing runs in Home Assistant's executor. XML uses the direct
`xmltodict==1.0.4` runtime dependency with entity declarations explicitly disabled. Both internal
and external entity declarations are rejected. Expat has no external-resource handler in this
path, so a bare external DTD declaration is accepted as inert metadata but is never loaded. The
parser rejects Expat older than 2.7.2 and applies the same 2 MiB input ceiling even when invoked
outside the HTTP fetch path. Lightning position and value arrays must have equal lengths.
Individual malformed lightning rows are discarded; an unsafe array mismatch rejects the complete
lightning response. Supported sea-level records require a finite numeric value and a timezone-aware
ISO timestamp. All timestamps stored for Home Assistant are aware UTC datetimes.

## Lightning maximum age

`lightning_max_age_minutes` is configurable from 1 through 1440 minutes. The default is 1440 minutes, preserving the previous one-day query window for existing entries that do not yet store this option. No config-entry version migration is required: the coordinator and options form apply the default lazily, and the next options save persists it.

The age boundary is inclusive. A strike exactly the configured age is retained; a strike one second older is discarded. Future, missing, malformed, non-finite, or millisecond-scale timestamps are discarded. The configured age also determines the FMI query start time, reducing unnecessary response data for shorter windows.

## Local lightning geometry

Each valid FMI row is calculated locally relative to the coordinates stored by its owning config
entry. Distance uses Home Assistant's local WGS84 helper. The configured radius is enforced as an
inclusive circle on the unrounded metre result after the square FMI bbox prefilter. A geometry
non-convergence result discards only that row. Up to five nearest qualifying groups are retained,
then presented newest first.

Initial bearing is normalized to `[0, 360)` and mapped through half-open 45-degree sectors to `N`,
`NE`, `E`, `SE`, `S`, `SW`, `W`, or `NW`. Coincident coordinates expose `direction=here` and no
bearing rather than inventing north. Distance is stored in kilometers to two decimals and bearing
to one decimal. Direction describes the configured-point-to-strike observation only; it does not
represent storm motion, path, arrival, or safety.

## Coordinate disclosure

Lightning queries send the configured bounding box to FMI, and sea-level queries send the
configured latitude/longitude to FMI. Lightning makes no other network request. Raw strike
coordinates are used transiently for local geometry and are not exposed in state or attributes.
