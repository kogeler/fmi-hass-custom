# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Offline diagnostics for the live FMI contract assertions."""

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from fmi_weather_client.models import Value
from homeassistant.util import dt as dt_util

from tests.helpers.live_budget import LiveBudgetExceeded, LiveRequestBudget
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


async def test_live_budget_is_shared_and_hard_bounded(tmp_path: Path) -> None:
    """Independent worker-shaped instances share one request counter."""
    first = LiveRequestBudget(tmp_path, maximum=2)
    second = LiveRequestBudget(tmp_path, maximum=2)

    async with first.request() as attempt:
        assert attempt == 1
    async with second.request() as attempt:
        assert attempt == 2
    with pytest.raises(LiveBudgetExceeded, match="exhausted at 2"):
        async with first.request():
            pass


async def test_live_budget_limits_parallel_requests(tmp_path: Path) -> None:
    """The cross-process semaphore also bounds local async concurrency."""
    budget = LiveRequestBudget(tmp_path, maximum=6, concurrency=2)
    active = 0
    peak = 0
    guard = asyncio.Lock()

    async def exercise() -> None:
        nonlocal active, peak
        async with budget.request():
            async with guard:
                active += 1
                peak = max(peak, active)
            await asyncio.sleep(0.02)
            async with guard:
                active -= 1

    await asyncio.gather(*(exercise() for _ in range(6)))
    assert peak == 2
