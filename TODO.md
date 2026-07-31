# Maintenance TODO

## Replace vulnerable Home Assistant-pinned packages

- Status: `BLOCKED_UPSTREAM`; temporary risk accepted by the repository owner on 2026-07-31.
- Home Assistant 2026.7.4 requires `pillow==12.2.0` and `PyJWT==2.12.1` exactly. Current High-severity advisories are fixed in Pillow 12.3.0 and PyJWT 2.13.0.
- The FMI integration does not import or declare either package. Its manifest dependency closure passes `pip-audit`; the affected packages enter the development/test environment through Home Assistant Core.
- Do not override Home Assistant's exact pins locally. Doing so makes `pip check` fail and tests an environment that Home Assistant does not support.

Close this item when a stable Home Assistant release and its matching `pytest-homeassistant-custom-component` release select fixed versions:

1. Update the Home Assistant/helper pair in `requirements-direct.txt`.
2. Run `make lock` and `make dev-build`.
3. Run `make audit`, the full offline suite, and `make validate`.
4. Remove the temporary exception from `docs/maintenance/DEPENDENCIES.md` and the S03 handoff only after the full audit passes.

Evidence checked 2026-07-31: [Pillow advisory](https://osv.dev/vulnerability/PYSEC-2026-2253), [PyJWT advisory](https://osv.dev/vulnerability/PYSEC-2026-179), and the installed Home Assistant 2026.7.4 package metadata.
