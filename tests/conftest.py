# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Shared FMI test fixtures."""

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading integrations from custom_components."""
    yield
