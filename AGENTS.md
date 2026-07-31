# FMI Custom Integration Agent Guide

## Purpose and scope

This repository contains the `fmi` Home Assistant custom integration. It exposes Finnish Meteorological Institute forecast, observation, lightning, and sea-level data. Preserve existing user configuration and entity identity while executing the bounded maintenance sessions in `plans/CODEX_FMI_HASS_MAINTENANCE_PLAN.md`.

## Before work

- Read `plans/CODEX_FMI_HASS_MAINTENANCE_PLAN.md` in full, inspect its session tracker, and read the latest file in `docs/agent-handoffs/`.
- Execute exactly one eligible session. Do not start a later session or absorb unrelated cleanup.
- Correct the plan immediately when verified code or source evidence reveals an inaccuracy, mismatch, or necessary scope expansion. Record the correction in the current handoff.

## Engineering rules

- Do not refactor for its own sake. Require a reproduced correctness, compatibility, testing, migration, security, privacy, or validation reason.
- Ordinary tests must be deterministic and offline. Only explicitly marked `live` tests may access external services.
- Do not overwrite, reset, stash, reformat, or otherwise disturb unexplained user changes.
- Do not run Git operations that may require a hardware token, interactive credential prompt, or authenticated SSH access. Use local Git and anonymous public HTTPS/API inspection only.
- Do not commit. The repository owner creates commits. End each session with exactly one concise suggested message beginning with `SXX:` and record `OWNER_TO_COMMIT` until the owner SHA is known.
- Keep `manifest.json` runtime requirements separate from development/test dependencies. After dependency upgrades, generate the complete root `requirements.txt` from a clean supported environment with `python -m pip freeze`; do not hand-edit that generated freeze.
- Never claim a check passed unless that exact check was run successfully. Record unavailable tools and failures precisely.

## Commands

Run all supported Python and Home Assistant commands through rootless Podman; do not use the host Python as a fallback.

- Environment setup/sync: `make dev-build`
- Regenerate the complete dependency freeze: `make lock`
- Format: `make format`
- Format check: `make format-check`
- Lint: `make lint`
- Type check: `make type-check`
- Fast offline tests: `make test-fast`
- Full offline tests and coverage: `make test-full`
- Local layout and hassfest validation: `make validate`
- Prove unexpected network access fails: `make test-network-block`
- Live tests: `make live` (opt-in and never part of the ordinary suite)

The build and lock commands may use package registries. Formatting, linting, typing, ordinary tests, and local validation run with Podman `--network=none`; pytest additionally blocks sockets. `make live` is the only test command with container networking.

## Session handoff

Follow Sections 10, 11, and 13 of the plan. Update the tracker as work changes state, keep `docs/agent-handoffs/SXX.md` current, run the session's required verification, review `git diff --check` and `git status --short`, and stop when that session is complete.
