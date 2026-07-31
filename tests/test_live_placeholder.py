# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Placeholder for the opt-in live FMI suite introduced in S12."""

import pytest


@pytest.mark.live
def test_live_suite_not_implemented() -> None:
    """Keep the live command valid until S12 replaces this placeholder."""
    pytest.skip("Live FMI tests are implemented in session S12")
