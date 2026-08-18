<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# P02 Verified Baseline

Verified on 2026-08-17 before the P02 user-visible flow change.

## Repository snapshot

- Branch: `feat/map-location`.
- Baseline commit and matching remote branch: `2c884b0402a00c59e9276ac25610b242b403a849`.
- Release source `.version`, integration manifest mirror, and current changelog section: `1.1.0`.
- Runtime direct dependencies: `fmi-weather-client==1.0.0`, `geopy==2.5.0`, and
  `xmltodict==1.0.4` in root PEP 621 metadata.
- Reference development environment: Home Assistant 2026.8.1 on Python 3.14.2.
- Generated hash locks contain 9 runtime, 176 development, and 1 Ruff distributions.
- All pytest Make targets use `-n auto --dist=worksteal`. The live suite has a cross-process
  ten-attempt counter and two-request semaphore before P02.
- Project-aware commands other than Ruff run in tar-streamed, rootless, confined Podman
  containers. P02 does not alter this boundary.

The pre-change fast offline suite passed with 269 tests after the S00 place-API characterization
was added. P02 starts from the repository's existing 95% coverage gate; the most recent recorded
full-suite result was 99.36%, which S04 must remeasure rather than assume.

## Pre-change config-flow and persistence behavior

Initial setup has one `user` form containing `name`, raw `latitude`, and raw `longitude`. The
coordinates default to the Home Assistant home location. Reconfigure has one `reconfigure` form
containing raw coordinates initialized from the selected entry.

Both flows:

1. reject an exact-coordinate duplicate before external validation;
2. call the integration's async coordinate weather adapter;
3. use the returned FMI place as the entry title;
4. recheck duplicates at the write boundary.

Initial setup writes `name`, top-level latitude/longitude, and a new random `entity_identity` only
after success. Reconfigure updates only top-level coordinates and title with
`async_update_and_abort`; its update listener reloads only the affected loaded entry. Config-entry
version 2 already separates mutable coordinates from immutable config/device/entity identity, so
P02 requires no persistent-data migration.

## Verified Home Assistant UI boundary

Local executable inspection of Home Assistant 2026.8.1 established:

- `ConfigFlow.async_show_menu` accepts a step ID and translated list of menu option step IDs;
- `LocationSelector` is registered with selector type `location` and returns a mapping containing
  latitude and longitude;
- `LocationSelector.DATA_SCHEMA` only coerces both values to `float`. It does not reject boolean,
  non-finite, or out-of-WGS84 inputs;
- `TextSelector` is the standard free-text input for the place query.

Therefore P02 retains the standard selector metadata/UI while adding integration-owned final
candidate validation. The normalizer will require a mapping with non-boolean numeric latitude and
longitude, require finite values, and enforce latitude `[-90, 90]` and longitude `[-180, 180]`.
Only normalized top-level coordinates reach duplicate detection, FMI validation, or persistence.

## Verified FMI place boundary

The selected client exposes the public method
`async_weather_by_place_name(name: str) -> Weather`. Its implementation delegates the synchronous
public `weather_by_place_name` call to the default executor. The synchronous path:

- sends a WFS weather request with the `place` parameter;
- uses the client's bounded ten-second Requests timeout;
- parses the result into `Weather(place, lat, lon, data)`;
- returns `None` when no forecast samples are present despite the narrower type annotation;
- propagates `ClientError` for 4xx responses, `ServerError` for service errors, Requests transport
  failures, and parser/model exceptions.

The existing integration privacy filter drops the upstream HTTP parameter record and forecast
parser records that may contain place/coordinate or raw XML data. S02 review corrected one S00
assumption: calling the async convenience method directly would let its parser consume the body
before the integration's 2 MiB ceiling. The integration adapter therefore composes the same
selected-client place request, ten-second timeout, and parser inside `asyncio.to_thread`, runs the
existing bounded safe-XML validation before the upstream parser, and reduces the result to an
immutable canonical place plus coordinates. A missing result, blank canonical place,
boolean/non-numeric or non-finite coordinates, and coordinates outside WGS84 are malformed boundary
results. The flow classifies a place-search `ClientError` or `None` as `place_not_found`,
transport/server failures as `cannot_connect`, and malformed/parser results as sanitized `unknown`.

No new captured response is needed. The existing public, compact
`tests/fixtures/fmi/forecast_normal.json` supplies a sanitized Helsinki `Weather` model sufficient
for offline place-adapter and flow tests. S00 pins the upstream async signature and proves executor
dispatch with that fixture.

## Frozen flow state and data contract

Initial setup:

```text
user menu
├── map form (name + location, default: HA home)
│   └── common final coordinate validation → create entry
└── place form (name + place query)
    └── FMI resolution
        └── place_confirm form (location, default: resolved point)
            └── common final coordinate validation → create entry
```

Reconfiguration:

```text
reconfigure menu
├── map form (location, default: stored entry point)
│   └── common final coordinate validation → update selected entry
└── place form (place query)
    └── FMI resolution
        └── place_confirm form (location, default: resolved point)
            └── common final coordinate validation → update selected entry
```

Menu options are exactly `map` and `place`. The setup display `name` is collected on the selected
path's first form; the FMI query uses a separate `place` field and is never confused with or stored
as `name`. The resolved canonical name and coordinates exist only on the flow instance until final
submission. If the confirmation marker moves, the common coordinate call determines the final
canonical entry title. The supported backend flow API has no distinct Back callback; frontend
back/close abandons the current flow. Abort/cancel/abandonment before the sole create/update
boundary therefore makes no persistent write, and a newly started path has a fresh flow instance.

The final stored setup mapping remains exactly `name`, `latitude`, `longitude`, and
`entity_identity`. Reconfiguration retains `name`, options, unique ID, identity, and registry state
and updates only coordinates and title. Duplicate checks use normalized final coordinates before
the external call and immediately before the write.

## Live probe and request policy

P02 reuses the existing public Helsinki location; no owner location or new captured payload is
introduced. S03 will repurpose the southern dependency contract so it resolves `Helsinki` through
the new adapter and validates the resolved coordinates through the production coordinate boundary.
This adds one nominal request and two worst-case retry attempts compared with the old southern
single-call probe. The documented suite ceiling therefore becomes twelve attempts while the
two-request concurrency guard and auto-worker policy remain unchanged.

## Closed planning questions

- Home location is not a third mode: accepting the default map marker is the Home path.
- Map adjustment after place search is allowed and always revalidated.
- The place query is transient; no runtime or migration requirement justifies persistence.
- A standard selector alone is insufficient input validation under the locked HA release.
- An upstream `Weather` object is too broad to retain as flow state; use a narrow validated result.
- Unknown/no-data place lookup remains on the search form; no partial entry is created or updated.
- P02 is part of the already selected `1.1.0` release section and does not increment the version.
- No country/city/station catalog, manual-coordinate form, or third-party geocoder is required.

## Authoritative evidence

Accessed 2026-08-17:

- Home Assistant data-entry flow forms and menus:
  <https://developers.home-assistant.io/docs/data_entry_flow_index/>
- Home Assistant config-flow guidance:
  <https://developers.home-assistant.io/docs/core/integration/config_flow/>
- Home Assistant user-friendly config-flow rule:
  <https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/config-flow/>
- FMI WFS examples and documented `place` parameter:
  <https://en.ilmatieteenlaitos.fi/open-data-manual-wfs-examples-and-guidelines>
- Selected client release/API and documented error categories:
  <https://pypi.org/project/fmi-weather-client/>
- Locked Home Assistant and FMI client source installed in the content-addressed toolbox; S00
  characterization tests are executable evidence for exact signatures and selected semantics.
  D013 records the S02 security correction needed to preserve bounded parsing.
