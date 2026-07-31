# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""S08 regressions for time boundaries and incomplete FMI values."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from types import SimpleNamespace
from typing import Any, cast
from zoneinfo import ZoneInfo

import fmi_weather_client.models as fmi_models
import pytest
from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_HUMIDITY,
    ATTR_FORECAST_NATIVE_PRESSURE,
    ATTR_FORECAST_NATIVE_TEMP,
    ATTR_FORECAST_TIME,
)
from homeassistant.const import SUN_EVENT_SUNRISE, SUN_EVENT_SUNSET
from homeassistant.util import dt as dt_util

from custom_components.fmi import FMIDataUpdateCoordinator, const, utils
from custom_components.fmi.weather import FMIWeatherEntity
from tests.helpers.fmi import forecast_from_fixture, weather_from_fixture

HELSINKI = ZoneInfo("Europe/Helsinki")


class _ForecastCoordinator:
    """Minimum coordinator surface for forecast output tests."""

    def __init__(self, samples: list[Any]) -> None:
        self.forecast = SimpleNamespace(forecasts=samples)

    def get_hourly_forecasts(self) -> list[Any]:
        return self.forecast.forecasts


def _entity(samples: list[Any]) -> FMIWeatherEntity:
    entity = cast(Any, object.__new__(FMIWeatherEntity))
    entity.coordinator = _ForecastCoordinator(samples)
    entity.logger = logging.getLogger(__name__)
    return cast(FMIWeatherEntity, entity)


def _value(value: object, unit: str = "") -> fmi_models.Value:
    return fmi_models.Value(cast(Any, value), unit)


@pytest.mark.parametrize(
    ("sunrise", "sunset"),
    [
        pytest.param(None, None, id="midnight-sun"),
        pytest.param(None, None, id="polar-night"),
        pytest.param(None, datetime(2026, 6, 21, 20, tzinfo=UTC), id="missing-sunrise"),
        pytest.param(datetime(2026, 6, 21, 2, tzinfo=UTC), None, id="missing-sunset"),
        pytest.param(
            datetime(2026, 6, 21, 2),
            datetime(2026, 6, 21, 20, tzinfo=UTC),
            id="naive-sunrise",
        ),
        pytest.param(
            datetime(2026, 6, 21, 2, tzinfo=UTC),
            datetime(2026, 6, 21, 20),
            id="naive-sunset",
        ),
        pytest.param(
            datetime(2026, 6, 21, 20, tzinfo=UTC),
            datetime(2026, 6, 21, 2, tzinfo=UTC),
            id="inconsistent-order",
        ),
    ],
)
def test_clear_symbol_falls_back_to_day_when_sun_events_are_incomplete(
    monkeypatch: pytest.MonkeyPatch,
    sunrise: datetime | None,
    sunset: datetime | None,
) -> None:
    """Incomplete polar sun events must never crash symbol resolution."""
    events = {SUN_EVENT_SUNRISE: sunrise, SUN_EVENT_SUNSET: sunset}
    monkeypatch.setattr(
        utils,
        "get_astral_event_date",
        lambda _hass, event, _day: events[event],
    )
    monkeypatch.setattr(dt_util, "now", lambda: datetime(2026, 6, 21, 12, tzinfo=UTC))

    assert utils.get_weather_symbol(1, hass=cast(Any, object())) == "sunny"


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (datetime(2026, 6, 21, 1, tzinfo=UTC), "clear-night"),
        (datetime(2026, 6, 21, 12, tzinfo=UTC), "sunny"),
        (datetime(2026, 6, 21, 21, tzinfo=UTC), "clear-night"),
    ],
)
def test_clear_symbol_uses_aware_sun_boundaries(
    monkeypatch: pytest.MonkeyPatch,
    now: datetime,
    expected: str,
) -> None:
    events = {
        SUN_EVENT_SUNRISE: datetime(2026, 6, 21, 2, tzinfo=UTC),
        SUN_EVENT_SUNSET: datetime(2026, 6, 21, 20, tzinfo=UTC),
    }
    monkeypatch.setattr(
        utils,
        "get_astral_event_date",
        lambda _hass, event, _day: events[event],
    )
    monkeypatch.setattr(dt_util, "now", lambda: now)

    assert utils.get_weather_symbol(1, hass=cast(Any, object())) == expected


@pytest.mark.parametrize("symbol", [None, "invalid", 999, "999", 1.5, float("nan")])
def test_unknown_or_invalid_weather_symbol_has_no_condition(symbol: object) -> None:
    assert utils.get_weather_symbol(symbol) == ""


def test_numeric_string_weather_symbol_is_supported() -> None:
    assert utils.get_weather_symbol("31") == "rainy"


def test_unknown_forecast_symbol_becomes_none() -> None:
    sample = forecast_from_fixture("forecast_normal.json").forecasts[0]._replace(symbol=_value(999))

    assert _entity([sample])._forecast(daily_mode=False)[0][ATTR_FORECAST_CONDITION] is None


def test_empty_forecast_returns_empty_hourly_and_daily_lists() -> None:
    entity = _entity([])

    assert entity._forecast(daily_mode=False) == []
    assert entity._forecast(daily_mode=True) == []


def test_hourly_forecast_accepts_numeric_strings_and_rejects_invalid_values() -> None:
    sample = (
        forecast_from_fixture("forecast_normal.json")
        .forecasts[0]
        ._replace(
            temperature=_value("2.5", "°C"),
            humidity=_value("invalid", "%"),
            pressure=_value(float("inf"), "hPa"),
            symbol=_value("31"),
        )
    )

    result = _entity([sample])._forecast(daily_mode=False)

    assert len(result) == 1
    assert result[0][ATTR_FORECAST_NATIVE_TEMP] == 2.5
    assert result[0][ATTR_FORECAST_HUMIDITY] is None
    assert result[0][ATTR_FORECAST_NATIVE_PRESSURE] is None
    assert result[0][ATTR_FORECAST_CONDITION] == "rainy"


def test_hourly_forecast_treats_missing_fields_as_unavailable() -> None:
    sample = SimpleNamespace(
        time=datetime(2026, 2, 10, 10, tzinfo=UTC),
        temperature=_value(-4.0, "°C"),
    )

    result = _entity([sample])._forecast(daily_mode=False)

    assert len(result) == 1
    assert result[0][ATTR_FORECAST_NATIVE_TEMP] == -4.0
    assert result[0][ATTR_FORECAST_HUMIDITY] is None
    assert result[0][ATTR_FORECAST_CONDITION] is None


def test_forecast_ignores_missing_and_timezone_naive_timestamps() -> None:
    sample = forecast_from_fixture("forecast_normal.json").forecasts[0]
    samples = [
        sample._replace(time=cast(Any, None)),
        sample._replace(time=datetime(2026, 2, 10, 10)),
        sample,
    ]

    result = _entity(samples)._forecast(daily_mode=False)

    assert len(result) == 1
    assert datetime.fromisoformat(result[0][ATTR_FORECAST_TIME]).tzinfo is not None


def _best_condition_coordinator(
    current: fmi_models.Weather,
    forecast: fmi_models.Forecast,
) -> FMIDataUpdateCoordinator:
    coordinator = cast(Any, object.__new__(FMIDataUpdateCoordinator))
    coordinator.current = current
    coordinator.forecast = forecast
    coordinator.time_step = 1
    coordinator.min_temperature = -40.0
    coordinator.max_temperature = 50.0
    coordinator.min_humidity = 0.0
    coordinator.max_humidity = 100.0
    coordinator.min_wind_speed = 0.0
    coordinator.max_wind_speed = 100.0
    coordinator.min_precip = 0.0
    coordinator.max_precip = 100.0
    return cast(FMIDataUpdateCoordinator, coordinator)


def test_best_time_stays_on_current_local_date_at_month_end(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    forecast = forecast_from_fixture("forecast_boundaries.json", "month_boundary")
    weather = weather_from_fixture("forecast_normal.json")
    assert weather is not None
    current = weather._replace(
        data=forecast.forecasts[0]._replace(
            time=datetime(2026, 1, 31, 12, tzinfo=UTC),
            temperature=_value(-10.0, "°C"),
        )
    )
    coordinator = _best_condition_coordinator(current, forecast)
    monkeypatch.setattr(dt_util, "now", lambda: datetime(2026, 1, 31, 12, tzinfo=HELSINKI))
    monkeypatch.setattr(dt_util, "as_local", lambda value: value.astimezone(HELSINKI))

    cast(Any, coordinator)._FMIDataUpdateCoordinator__update_best_weather_condition()

    assert coordinator.best_state == const.BEST_CONDITION_AVAIL
    assert coordinator.best_time is not None
    assert coordinator.best_time.date() == date(2026, 1, 31)
    assert coordinator.best_temperature == -2.0


def test_best_time_accepts_numeric_strings_and_skips_invalid_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = forecast_from_fixture("forecast_normal.json")
    invalid = base.forecasts[0]._replace(temperature=_value("invalid", "°C"))
    valid = base.forecasts[1]._replace(
        temperature=_value("12.5", "°C"),
        humidity=_value("60", "%"),
        wind_speed=_value("4.5", "m/s"),
        precipitation_amount=_value("0.1", "mm/h"),
        symbol=_value("1"),
    )
    forecast = base._replace(forecasts=[invalid, valid])
    weather = weather_from_fixture("forecast_normal.json")
    assert weather is not None
    current = weather._replace(
        data=weather.data._replace(
            time=datetime(2026, 2, 10, 8, tzinfo=UTC),
            temperature=_value(-10.0, "°C"),
        )
    )
    coordinator = _best_condition_coordinator(current, forecast)
    monkeypatch.setattr(dt_util, "now", lambda: datetime(2026, 2, 10, 12, tzinfo=HELSINKI))
    monkeypatch.setattr(dt_util, "as_local", lambda value: value.astimezone(HELSINKI))

    cast(Any, coordinator)._FMIDataUpdateCoordinator__update_best_weather_condition()

    assert coordinator.best_state == const.BEST_CONDITION_AVAIL
    assert coordinator.best_temperature == 12.5
    assert coordinator.best_humidity == 60.0
    assert coordinator.best_wind_speed == 4.5
    assert coordinator.best_precipitation == 0.1
