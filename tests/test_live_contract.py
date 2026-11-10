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
    validate_first_available_local_day_ha_metrics,
    validate_first_available_local_day_probability_supplements,
    validate_model_forecast,
    validate_probabilities,
)
from tests.helpers.live_network import live_call


async def test_live_warning_allocation_includes_retries_and_all_locales(tmp_path, monkeypatch):
    """Exercise actual retry accounting before reserving every remaining HA/CAP request."""
    monkeypatch.setenv("FMI_LIVE_BUDGET_DIR", str(tmp_path))
    calls: dict[str, int] = {}
    for label in ("resolution", "northern forecast"):

        async def operation(current=label):
            calls[current] = calls.get(current, 0) + 1
            if calls[current] == 1:
                raise TimeoutError
            return True

        assert await live_call(label, operation)
    budget = LiveRequestBudget(tmp_path)
    for label in ("current", "forecast", "station", "fallback", "CAP en", "CAP fi", "CAP sv"):
        async with budget.request():
            calls[label] = calls.get(label, 0) + 1
    assert calls["resolution"] == calls["northern forecast"] == 2
    assert all(calls[f"CAP {locale}"] == 1 for locale in ("en", "fi", "sv"))
    assert int((tmp_path / "requests").read_text()) == 11


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


def test_live_probability_contract_requires_aligned_finite_first_future_day_values() -> None:
    """Keep live probability checks strict without asserting exact weather."""
    now = datetime(2026, 8, 20, 10, 30, tzinfo=UTC)
    first = datetime(2026, 8, 20, 11, tzinfo=UTC)
    second = datetime(2026, 8, 20, 12, tzinfo=UTC)
    tomorrow = datetime(2026, 8, 20, 22, tzinfo=UTC)
    samples = [
        SimpleNamespace(time=first),
        SimpleNamespace(time=second),
        SimpleNamespace(time=tomorrow),
    ]
    probabilities = {
        first: SimpleNamespace(precipitation=0.0, thunderstorm=100.0),
        second: SimpleNamespace(precipitation=35.0, thunderstorm=4.0),
    }

    assert (
        validate_first_available_local_day_probability_supplements(
            samples,
            probabilities,
            "synthetic forecast",
            now=now,
        )
        == 2
    )
    assert validate_probabilities(probabilities[first], "synthetic") == (0.0, 100.0)

    late_night = datetime(2026, 8, 20, 20, 30, tzinfo=UTC)
    next_local_day_probabilities = {tomorrow: SimpleNamespace(precipitation=0.0, thunderstorm=0.0)}
    assert (
        validate_first_available_local_day_probability_supplements(
            [SimpleNamespace(time=tomorrow)],
            next_local_day_probabilities,
            "synthetic late-night forecast",
            now=late_night,
        )
        == 1
    )

    with pytest.raises(LiveContractError, match="has no aligned probabilities"):
        validate_first_available_local_day_probability_supplements(
            samples,
            {first: probabilities[first]},
            "synthetic forecast",
            now=now,
        )
    with pytest.raises(LiveContractError, match="outside 0..100"):
        validate_probabilities(
            SimpleNamespace(precipitation=-1.0, thunderstorm=101.0),
            "synthetic",
        )


def test_live_ha_metric_contract_requires_apparent_temperature_and_pop() -> None:
    """Keep presentation checks strict while accepting valid zero probability."""
    now = datetime(2026, 8, 20, 10, 30, tzinfo=UTC)
    first = datetime(2026, 8, 20, 11, tzinfo=UTC)
    valid = [(first, {"apparent_temperature": 18.0, "precipitation_probability": 0})]

    assert validate_first_available_local_day_ha_metrics(valid, "synthetic", now=now) == 1

    late_night = datetime(2026, 8, 20, 20, 30, tzinfo=UTC)
    next_local_midnight = datetime(2026, 8, 20, 21, tzinfo=UTC)
    next_local_day = [
        (
            next_local_midnight,
            {"apparent_temperature": 12.0, "precipitation_probability": 0},
        )
    ]
    assert (
        validate_first_available_local_day_ha_metrics(
            next_local_day,
            "synthetic late-night HA forecast",
            now=late_night,
        )
        == 1
    )

    with pytest.raises(LiveContractError, match="apparent_temperature is not numeric"):
        validate_first_available_local_day_ha_metrics(
            [(first, {"precipitation_probability": 10})],
            "synthetic",
            now=now,
        )


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


def test_live_target_reports_cap_structure_after_the_request_counter() -> None:
    """The live gate prints public CAP structure counts and accepts no ad hoc pytest arguments."""
    makefile = (Path(__file__).parents[1] / "Makefile").read_text(encoding="utf-8")
    live = makefile.split("\nlive:", 1)[1].split("\n\n", 1)[0]
    counter = live.index('printf "live FMI request attempts')
    summaries = live.index('"$${FMI_LIVE_BUDGET_DIR}"/cap-*.txt')
    assert counter < summaries < live.index("exit $$status")
    assert "-m live -q ||" in live and "LIVE_TEST_ARGS" not in makefile
