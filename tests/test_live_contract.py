# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Offline diagnostics for the live FMI contract assertions."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fmi_weather_client.models import Value
from homeassistant.util import dt as dt_util

from tests.helpers.live_fmi import (
    LiveContractError,
    validate_daily_precipitation,
    validate_model_forecast,
)


@pytest.fixture
def malformed_live_forecast() -> SimpleNamespace:
    """Return a synthetic client-shaped forecast with a naive timestamp."""
    return SimpleNamespace(
        place="Synthetic Helsinki",
        forecasts=[
            SimpleNamespace(
                time=datetime(2026, 7, 31, 12, 0),
                temperature=Value(20.0, "C"),
            )
        ],
    )


def test_malformed_contract_reports_actionable_timestamp(
    malformed_live_forecast: SimpleNamespace,
) -> None:
    """Name the exact bad sample and timestamp contract in failure output."""
    with pytest.raises(
        LiveContractError,
        match="synthetic malformed sample 0 timestamp must be timezone-aware",
    ):
        validate_model_forecast(malformed_live_forecast, "synthetic malformed")


def test_daily_precipitation_allows_only_independent_display_rounding(monkeypatch) -> None:
    """Accept separate hourly/daily rounding while rejecting an aggregation mismatch."""
    monkeypatch.setattr(dt_util, "as_local", lambda value: value)
    midnight = datetime(2026, 8, 16, tzinfo=UTC)
    hourly = [
        (midnight, {"precipitation": 0.05}),
        (midnight + timedelta(hours=1), {"precipitation": 0.06}),
    ]

    validate_daily_precipitation(hourly, [(midnight, {"precipitation": 0.12})])

    with pytest.raises(LiveContractError, match="beyond the .* rounding bound"):
        validate_daily_precipitation(hourly, [(midnight, {"precipitation": 0.14})])
