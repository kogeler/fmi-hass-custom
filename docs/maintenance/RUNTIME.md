<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Runtime Maintenance

Normative entry ownership, polling, I/O, cancellation, and request-volume requirements are owned
by [the runtime contract](../contracts/RUNTIME.md). Source outcomes are in
[the availability contract](../contracts/AVAILABILITY.md), and logging/diagnostic/XML boundaries
are in [the compatibility, security, and privacy contract](../contracts/COMPATIBILITY_SECURITY.md).

Read these contracts before changing `custom_components/fmi/__init__.py`, `fmi_client.py`, or an
entity platform.

## Change Checklist

1. Map the change to its `RUN-*`, `AVL-*`, or `CSP-*` assertion and existing evidence.
2. Keep synchronous dependency/parser work behind the existing executor adapters and
   integration-owned HTTP on Home Assistant's shared session.
3. Exercise cancellation separately from ordinary exceptions.
4. Prove setup, unload, failed unload, reload, options update, reconfigure, and simultaneous-entry
   behavior when ownership/listeners change.
5. Prove request count and socket blocking when moving an I/O boundary.
6. Run `make test-full`, `make type-check`, `make test-network-block`, and `make confinement-test`.
   Use `make live` only for a changed external FMI contract.

## Architecture Notes

`FMIConfigEntryRuntimeData` is the ownership boundary visible to Home Assistant. The main
coordinator, configured-station coordinator, and entity platforms stay separate so lifecycle and
availability tests can observe exact ownership. The FMI client adapter exists to isolate the
selected synchronous/private dependency surface without spreading compatibility logic through
entities.

## References

- [Home Assistant blocking-operation guidance](https://developers.home-assistant.io/docs/asyncio_blocking_operations/)
- [Home Assistant coordinator and polling guidance](https://developers.home-assistant.io/docs/integration_fetching_data/)
- [Home Assistant diagnostics rules](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/diagnostics/)
