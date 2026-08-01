# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Focused regressions for the S13 runtime correctness audit."""

from __future__ import annotations

import importlib
import logging

import pytest

from custom_components.fmi import const, utils


def test_importing_constants_does_not_configure_root_logging(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A custom integration must not change Home Assistant's global logging policy."""
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
    monkeypatch.setattr(
        logging,
        "basicConfig",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    importlib.reload(const)

    assert calls == []


@pytest.mark.parametrize("value", [True, False])
def test_finite_float_rejects_booleans(value: bool) -> None:
    """Do not silently publish boolean sentinels as numeric zero or one."""
    assert utils.finite_float(value) is None
