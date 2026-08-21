<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Availability Maintenance

Normative setup, source-isolation, stale-clearing, and recovery requirements are owned exclusively
by the [availability contract](../contracts/AVAILABILITY.md). Runtime ownership and request
boundaries are owned by [the runtime contract](../contracts/RUNTIME.md); optional-source details
are owned by [the optional-source contract](../contracts/OPTIONAL_SOURCES.md).

## Change Checklist

1. Identify the affected `AVL-*` assertion before changing coordinator or entity behavior.
2. Update the assertion and its evidence together when the public behavior deliberately changes.
3. Add Home Assistant-level coverage for setup, stale clearing, availability, and later recovery.
4. Exercise current/place fallback, configured station, hourly forecast, lightning, and sea-level
   boundaries independently; never prove isolation using only a fully successful refresh.
5. Verify unload/reload and two simultaneous entries when listener ownership or cached state changes.
6. Run `make test-full`, `make type-check`, and `make test-network-block`. Run `make live` only when
   the external FMI boundary or public live assertions changed.

## Design Rationale

The integration has several independently useful FMI sources. Treating every partial outage as a
single coordinator failure would discard usable data and make recovery depend on reload. The
contract therefore records observable success/failure ownership, while implementation details stay
in the coordinator and tests.

Transition logging exists for diagnosis without flooding logs during a sustained outage. Privacy
requirements for those messages are in `CSP-003`.
