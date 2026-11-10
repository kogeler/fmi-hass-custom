<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Weather-Warning Maintenance

Normative CAP snapshot, local geometry, language, and time/freshness requirements are owned by
[the warnings contract](../contracts/WARNINGS.md). Warning entity attributes are owned by
[SNS-007](../contracts/SENSORS.md#sns-007--warning-entities-expose-bounded-independent-state),
shared bounded transport and coordinate disclosure by
[the optional-source contract](../contracts/OPTIONAL_SOURCES.md), logs and diagnostics by
[the compatibility, security, and privacy contract](../contracts/COMPATIBILITY_SECURITY.md), and the
feature coverage gate by [DEP-008](../contracts/DEPENDENCIES.md).

## Change Checklist

1. Map the change to `WRN-*`, `SNS-007`, `OPT-001`/`OPT-007`, `AVL-005`, and any `CSP-*` assertion.
2. Reproduce feed or geometry changes with invented fixtures in `tests/helpers/warnings.py`; never
   store live bodies, owner coordinates, or captured message text.
3. Check envelope control, references, and cancellations before changing language selection or
   point matching; an empty local result cannot prove those paths.
4. Keep remote-message skipping within `WRN-002`: geometry that cannot be bounded is not remote.
5. Give every new failure class a coordinator reason code and a test asserting its exact value.
6. Run `make test-full` and review the feature coverage report as well as the aggregate result.
   Run the complete `make live` suite before release and keep its per-locale structure counts.

## Timeout Review

The feed's four request limits and their values are owned by
[OPT-001](../contracts/OPTIONAL_SOURCES.md#opt-001--optional-http-is-shared-bounded-and-non-retrying).
Each limit covers a different failure:

- `connect` and `sock_connect`: slow DNS, routing, or TLS setup before any data arrives. Home
  Assistant OS VMs behind a local DNS filter are the usual slow case.
- `sock_read`: the longest pause between received pieces of the multi-megabyte body, such as a
  stalled Wi-Fi link, a busy VM, or a provider-side hiccup.
- `total`: a whole download that is too slow even though data keeps arriving.

The first values (2-second connect, 3-second read) were inherited from the small lightning and
sea-level responses. A Home Assistant OS VM then repeatedly reported `timeout` failures, while the
same feed downloaded from another host in well under a second. The current values give a
home network room for one slow step and still fail a dead connection well before the five-minute
poll.

Review these values again when logs or diagnostics show repeated `timeout` failures, either several
outage transitions from one installation or the same report from several users. Each failure logs
the limit that expired, for example `FMI warnings retrieval failed (timeout): exceeded the read
timeout of 10 s`:

1. Collect the expired-limit names from the log lines and the reporter's network setup. Do not
   request coordinates or feed bodies.
2. Raise only the limit that expires, and keep `total` larger than the connect and read limits.
   A recurring `total` expiry with healthy connect/read usually means a slow link or a much larger
   publication, so compare it with the feed size before raising the limit.
3. Update OPT-001, the timeout assertions in `tests/test_warnings_coordinator.py`, the user guide's
   download allowance, and the changelog together.

A timeout no longer removes held messages before the freshness deadline under WRN-004. Frequent
timeouts can therefore stay invisible on dashboards until a 15-minute outage, and only the logs
reveal them.

## Design Rationale

The national feed is matched locally so configured coordinates never leave Home Assistant.
Validation fails closed for anything that could affect the configured point, but a message that
cannot geometrically reach it must not make every installation unavailable. Geometry is validated
without a GIS dependency; its work bound is computed before sweeping, so a valid dense ring is not
rejected because of a fixed sweep axis. Older publications are ignored for one freshness window,
so a lagging cache cannot restore replaced warnings and a rollback cannot keep the source
unavailable indefinitely. A multi-megabyte national feed downloaded every five minutes on a home
network will occasionally stall. A network failure therefore keeps the held snapshot only until
the same freshness deadline instead of flapping every warning entity, while an invalid publication
still fails closed. For the same reason, the feed's connect and read-stall limits are wider than
those of the small lightning and sea-level responses. Conditional HTTP requests are not used: FMI
documents no validator or polling contract, and entries deliberately share no warning state.

## Warning Feed Changes

For a changed FMI CAP profile, start with the production-path locale probes in
`tests/test_live_warnings.py` and the English Home Assistant probe in `tests/test_live_fmi.py`.
Compare the printed structure counts and size evidence without storing live bodies, and use the
shared request allocation in [LIV-003](../contracts/LIVE_TESTS.md).

For dashboard reports, distinguish unavailable, future-only, and available empty state, then
inspect coordinator health and the classified failure reason through sanitized diagnostics. Avoid
requesting the owner's XML, coordinates, or message attributes as a routine diagnostic step.
Reproduce parser failures with public locations or synthetic data.
