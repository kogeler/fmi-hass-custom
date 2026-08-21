<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Migration Maintenance

Normative config-entry, device-registry, entity-registry, legacy-ID, collision, and optional-entity
guarantees are owned exclusively by [the migration contract](../contracts/MIGRATIONS.md).
Post-migration moves are governed by
[the reconfiguration contract](../contracts/RECONFIGURATION.md).

## Historical Fixture

`tests/fixtures/fmi/registry_v062.json` is the synthetic acceptance input for the supported v0.6.2
history. It represents two entries and the combinations needed to distinguish exact defaults,
ambiguous suffixes, custom IDs, occupied targets, and optional entities. It contains rounded public
city data rather than an owner registry or captured FMI payload.

## Change Checklist

1. Treat registry records and identifiers as user data; identify the affected `MIG-*` assertion.
2. Extend the serialized historical fixture only when a real supported history is missing.
3. Exercise config-only migration, combined setup, repeated migration/reload, future-version
   rejection, target collision, disabled state, and customized IDs.
4. Never infer registry provenance that Home Assistant does not store.
5. Run `make test-full`, `make type-check`, and `make validate`.
