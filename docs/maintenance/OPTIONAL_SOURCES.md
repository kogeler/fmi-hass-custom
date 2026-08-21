<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Optional-Source Maintenance

Normative lightning and sea-level transport, freshness, parsing, geometry, presentation, and
coordinate-disclosure requirements are owned by
[the optional-source contract](../contracts/OPTIONAL_SOURCES.md). Shared XML/privacy rules are in
[the compatibility, security, and privacy contract](../contracts/COMPATIBILITY_SECURITY.md).

## Change Checklist

1. Map the change to `OPT-*`, `AVL-005`, and any applicable `CSP-*` assertion.
2. Keep public radius behavior based on unrounded local geometry and test exact boundaries.
3. Exercise empty success separately from malformed/transport failure and later recovery.
4. Test cancellation, response-size handling, parser isolation, timestamp freshness, and no raw
   coordinate disclosure.
5. Use only Home Assistant's shared session and local geometry helpers; a new provider or
   dependency requires separate dependency/privacy review.
6. Run `make test-full`, `make type-check`, `make test-network-block`, and `make live` only when the
   external FMI request contract changed.

## Design Rationale

Lightning uses local point-to-strike geometry because reverse geocoding would add a provider,
coordinate disclosure, availability coupling, and nondeterministic labels. Sea level remains an
independent best-effort source because geographic coverage differs from general weather coverage.
