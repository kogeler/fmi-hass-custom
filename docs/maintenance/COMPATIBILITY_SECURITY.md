<!-- Copyright (c) 2026 kogeler. SPDX-License-Identifier: MIT. -->

# Compatibility, Security, And Privacy Maintenance

Normative support, moving-compatibility, logging, diagnostics, XML, disclosure, and fixture
requirements are owned exclusively by
[the compatibility, security, and privacy contract](../contracts/COMPATIBILITY_SECURITY.md).
Dependency/audit rules are in [the dependency contract](../contracts/DEPENDENCIES.md), and workflow
trust is in [the CI contract](../contracts/CI.md).

## Review Procedure

1. Identify the affected `CSP-*` assertion and review every linked test.
2. For a support-policy change, update PEP 621 or `hacs.json` only in its owning role and add a
   reproduced compatibility regression before raising the installation floor.
3. For logging/diagnostic changes, inspect emitted values and error paths for coordinates, search
   text, identity, payloads, and arbitrary external exception content.
4. For XML/parser changes, preserve the input ceiling, Expat floor, entity-disabled behavior, and
   executor boundary with hostile fixtures.
5. Review `.github/dependency-audit-exceptions.json` and `TODO.md` rather than copying accepted
   advisory versions into another document.
6. Run `make test-full`, `make type-check`, `make bandit`, `make test-network-block`,
   `make confinement-test`, `make validate`, `make audit`, and `make licenses`. Follow the final-only
   moving-compatibility protocol in `AGENTS.md` for an actual support/dependency change.

## Interpretation

This repository is a maintained HACS custom integration and does not infer an official Home
Assistant Core quality tier. The exact reference graph is reproducible evidence for development;
the HACS floor is a separate user-installation decision. A moving compatibility pass is evidence
for that run, not a permanent promise about future Home Assistant releases.

## References

- [Home Assistant integration quality guidance](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/)
- [Runtime data](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/runtime-data/)
- [Diagnostics and coordinate redaction](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/diagnostics/)
- [Python XML security guidance](https://docs.python.org/3.14/library/xml.html)
- [`xmltodict` security policy](https://github.com/martinblech/xmltodict/security)
