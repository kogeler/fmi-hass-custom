<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# P03 Verified Baseline

## Metadata

- Verified: 2026-08-19 UTC.
- Execution branch: `p03-reliable-local-lightning`.
- Starting commit: `7e2ac6ce28863c9cd675b7ec3bd4bce26cee9a67`.
- Starting release: `.version` and integration manifest both `1.1.0`.
- Reference runtime: Python 3.14.2, Home Assistant 2026.8.1,
  `pytest-homeassistant-custom-component` 0.13.355.
- Starting owner work: the supplied untracked `plans/P03/` directory. The requested `AGENTS.md`
  Git-safety edits were made before the execution branch was created and remain uncommitted.
- Release selected for P03: owner-confirmed `1.2.0`. Native state and the `location` attribute
  intentionally change, so release notes must identify the incompatibility prominently despite the
  selected minor version.

## Current lightning path

Enabling `lightning_sensor` makes the main per-entry coordinator request
`fmi::observations::lightning::multipointcoverage` every 30 minutes. It uses the entry's stored
latitude/longitude, `lightning_radius` as the square bounding-box half-side, and
`lightning_max_age_minutes` for the request start and inclusive local freshness filter. The shared
Home Assistant aiohttp session applies 2-second connect, 3-second read, 5-second total, and 2 MiB
limits. XML parsing and all current geopy/Nominatim work execute in `async_add_executor_job`.

The parser requires aligned `positions` and `doubleOrNilReasonTupleList` arrays. It rejects invalid
or non-finite numeric values, out-of-range coordinates, fractional/negative strike counts,
unrepresentable/future/stale timestamps, and malformed XML. It calculates geopy WGS84 distance,
retains the five nearest candidates, then presents those candidates newest first. It does not
compare calculated distance to `lightning_radius`, so a candidate inside a square bbox corner can
be farther than the advertised circular radius.

For retained rows, `_LightningState` owns a Nominatim client, coordinate/address cache, and data.
A process-global lock/timestamp permits at most one lookup per 15 seconds and candidate building
attempts at most one new lookup per update. Failure/rate limiting exposes raw strike coordinates.
Raw strike coordinates therefore leave the integration for Nominatim and can enter state and
attributes.

## Current source and entity contract

`lightning_data` is `list[FMILightningStruct] | None`, but the optional-source wrapper calls
`bool(data)`. Consequently both a valid empty list and `None` mark lightning unavailable. The
generic sensor availability rule also requires a non-`None` native value. Current results are:

| FMI outcome | Coordinator data/source flag | Lightning entity |
|---|---|---|
| Valid non-empty | list / true | Available; address or raw coordinates as state |
| Valid empty | empty list / false | Unavailable; dynamic attributes empty |
| Transport/payload/parser failure | `None` / false | Unavailable; stale dynamic attributes cleared |

A non-empty primary state is the newest retained group's `location`. Primary attributes are
`location`, `time`, `distance`, `strikes`, `peak_current`, `cloud_cover`, `ellipse_major`, and
`OBSERVATIONS`; each nested row repeats the same fields. Attribution combines FMI and
OpenStreetMap. The entity description key, unique-ID construction, entity registry row, device,
config entry, options, and update cadence need no migration for P03.

## Frozen P03 state and schema

- Successful empty: stored state token `no_strikes`; frontend translations `No lightning
  strikes` (English) and `Ei salamaniskuja` (Finnish); available; no dynamic strike attributes.
- Successful strike: stable stored state `{DIRECTION} · {distance:.1f} km`, for example
  `NW · 4.0 km`; no backend locale/unit conversion.
- Coincident strike: `HERE · 0.0 km`, `direction="here"`, and `bearing=None`.
- Failed/unusable source: native value `None`, unavailable, and no dynamic strike attributes.
- Primary and every nested observation retain `time`, numeric `distance` in kilometers rounded to
  two decimals, `strikes`, `peak_current`, `cloud_cover`, and `ellipse_major`, and add stable
  `direction` plus numeric `bearing` rounded to one decimal (or `None` at coincidence).
- `location`, address, latitude, longitude, and raw coordinate text are removed from state and
  attributes. Static attribution is FMI only.
- Recorder history is not edited. Automations comparing an address/state or reading `location`
  must migrate to `direction`, `bearing`, and `distance`; registry identity remains unchanged.

Home Assistant's documented state-translation API maps finite raw tokens under an entity's
`translation_key` when the entity has a unique ID. It does not provide a safe per-user translation
for arbitrary dynamic composite state. The backend state machine therefore keeps `no_strikes` and
the dynamic compass/distance string as stable machine values; only the finite empty token receives
frontend translation. The sensor remains textual without a numeric device or state class.

## Frozen geometry boundary

P03 uses `homeassistant.util.location.distance`, which is a local WGS84 Vincenty inverse helper
returning metres or `None` on non-convergence. Candidates are included when the unrounded result is
`<= lightning_radius * 1000`; only then is distance converted to kilometers and rounded to two
decimals. A `None` result rejects the candidate without logging coordinates. XML parsing remains in
the existing executor boundary.

Measured against GeographicLib WGS84 and the current geopy result:

| Vector | GeographicLib/geopy km | HA helper km | Result |
|---|---:|---:|---|
| Helsinki `(60.17,24.94)` to `(60.20,24.90)` | 4.012275535 | 4.012276 | within 1 mm |
| Equator across antimeridian | 22.263898159 | 22.263898 | within 1 mm |
| 89°N, 90° longitude difference | 157.954968632 | 157.954969 | within 1 mm |
| 89°S, 90° longitude difference | 157.954968632 | 157.954969 | within 1 mm |
| Coincident point | 0 | 0 | exact |
| Antipodal point | 20003.931458625 | `None` | explicit non-convergence; outside supported radius |

Initial bearing uses the standard spherical great-circle formula with longitude delta normalized
to `[-180, 180)`, then normalizes the result to `[0, 360)`. Direction selection uses the unrounded
bearing and half-open sectors: N `[337.5,360) ∪ [0,22.5)`, NE `[22.5,67.5)`, E
`[67.5,112.5)`, SE `[112.5,157.5)`, S `[157.5,202.5)`, SW `[202.5,247.5)`, W
`[247.5,292.5)`, and NW `[292.5,337.5)`. Published bearing is rounded to one decimal and
renormalized. Coincidence is detected from zero distance before bearing calculation.

## Dependency and active-surface inventory

`geopy==2.5.0` is direct in root PEP 621 metadata and `manifest.json`, and transitive records appear
in runtime/development locks. Active runtime use is confined to `custom_components/fmi/__init__.py`
for distance, `Nominatim`, and `GeocoderServiceError`. Related constants are in `const.py`, entity
attribution/schema is in `sensor.py`, and current tests/docs pin the old behavior. No other runtime
feature needs geopy, so S02 can remove it without replacement and regenerate all three locks plus
the dependency snapshot.

Current contracts requiring final updates are `README.md`, `docs/USER_GUIDE.md`, `TODO.md`,
`CHANGELOG.md`, and maintenance `AVAILABILITY.md`, `OPTIONAL_SOURCES.md`, `RUNTIME.md`,
`SENSORS.md`, `COMPATIBILITY_SECURITY.md`, and `DEPENDENCIES.md`. `LIVE_TESTS.md` and
`MIGRATIONS.md` need only changes proven by final behavior. Historical P01/P02 evidence remains
unchanged.

## Test and external evidence

Before P03 characterization tests, `make test-full` collected 328 offline tests: 328 passed with
99.41% branch-aware coverage (1378 statements, six missed; 95% gate). After adding only S00
reference/bbox characterization, `make test-fast` collected 335 tests and all passed. S00 also ran
format, Ruff/Pylint, mypy, version, and diff checks successfully.

The S00 reference tests freeze GeographicLib WGS84 values, current geopy parity, HA helper parity,
antipodal non-convergence, and the square-bbox/circular-radius discrepancy. Existing auxiliary,
availability, lifecycle, sensor, dependency, and privacy tests characterize current Nominatim,
empty/failure collapse, stale clearing, ordering, executor, and identity behavior.

References rechecked on 2026-08-19: Home Assistant sensor/entity state translation documentation,
the installed HA 2026.8.1 `homeassistant.util.location` source, GeographicLib WGS84 API/test-data
documentation, FMI WFS stored-query documentation, and public issues #4/#5. Both issues remained
open; no new issue-author scope change was visible. Normal coverage stays offline. Per the owner's
2026-08-19 instruction, S04 will run one bounded non-persistent marked-live current-lightning probe
within the existing twelve-attempt ceiling and will retain neither a test nor raw FMI payload.
