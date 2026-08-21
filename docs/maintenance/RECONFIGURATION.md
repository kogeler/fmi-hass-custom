<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Reconfiguration Maintenance

Normative mutable-location, immutable-identity, duplicate, transient search, atomic failure, and
reload requirements are owned exclusively by
[the reconfiguration contract](../contracts/RECONFIGURATION.md). Legacy identity guarantees are in
[the migration contract](../contracts/MIGRATIONS.md).

## Change Checklist

1. Identify the affected `RCF-*` and `MIG-*` assertions before changing either flow.
2. Exercise map and place-search paths, pre/post-validation duplicate checks, retry, cancellation,
   malformed FMI data, and unexpected failure without writes.
3. Prove customized IDs and all immutable identifiers before and after a loaded move.
4. Prove that only the selected loaded entry reloads and other entries retain coordinator state.
5. Keep search text and exact coordinates out of failure logs and transient mode metadata.
6. Run `make test-full`, `make type-check`, and `make validate`.

## References

- [Home Assistant reconfiguration-flow guidance](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/reconfiguration-flow/)
- [Home Assistant config-flow guidance](https://developers.home-assistant.io/docs/core/integration/config_flow/)
