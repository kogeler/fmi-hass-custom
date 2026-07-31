"""Characterization tests for current FMI entity behavior."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, cast
from zoneinfo import ZoneInfo

import pytest
from homeassistant.components.weather import (
    ATTR_FORECAST_NATIVE_PRECIPITATION,
    ATTR_FORECAST_NATIVE_TEMP,
    ATTR_FORECAST_TIME,
)
from homeassistant.const import STATE_UNAVAILABLE

from custom_components.fmi import utils
from custom_components.fmi import weather as weather_module
from custom_components.fmi.sensor import FMIBestConditionSensor
from custom_components.fmi.weather import FMIWeatherEntity
from tests.helpers.fmi import (
    forecast_from_fixture,
    load_json_fixture,
    weather_from_fixture,
)

HELSINKI = ZoneInfo("Europe/Helsinki")


class StubCoordinator:
    """Minimum coordinator surface consumed by weather entities."""

    def __init__(self, forecast, weather=None) -> None:
        self.forecast = forecast
        self.current = weather
        self.last_update_success = True
        self.hass = None

    def get_forecasts(self):
        return self.forecast.forecasts

    def get_weather(self):
        return self.current


def _entity(forecast, weather=None) -> FMIWeatherEntity:
    entity = cast(Any, object.__new__(FMIWeatherEntity))
    entity.coordinator = StubCoordinator(forecast, weather)
    return cast(FMIWeatherEntity, entity)


def _local_dates(result: list[Any]) -> list[date]:
    return [date.fromisoformat(item[ATTR_FORECAST_TIME][:10]) for item in result]


def test_hourly_forecast_spans_three_local_dates(monkeypatch) -> None:
    monkeypatch.setattr(weather_module.tz, "tzlocal", lambda: HELSINKI)
    forecast = forecast_from_fixture("forecast_normal.json")

    hourly = _entity(forecast)._forecast(daily_mode=False)

    assert hourly is not None
    assert len(hourly) == 49
    assert sorted(set(_local_dates(hourly))) == [
        date(2026, 2, 10),
        date(2026, 2, 11),
        date(2026, 2, 12),
    ]
    assert hourly[0][ATTR_FORECAST_NATIVE_PRECIPITATION] == 0.0
    assert hourly[1][ATTR_FORECAST_NATIVE_PRECIPITATION] == 0.4
    assert hourly[2][ATTR_FORECAST_NATIVE_PRECIPITATION] == 0.7


@pytest.mark.parametrize(
    ("series", "expected_dates"),
    [
        ("month_boundary", [date(2026, 1, 31), date(2026, 2, 1)]),
        ("year_boundary", [date(2026, 12, 31), date(2027, 1, 1)]),
    ],
)
def test_daily_grouping_crosses_calendar_boundaries(
    monkeypatch,
    series: str,
    expected_dates: list[date],
) -> None:
    monkeypatch.setattr(weather_module.tz, "tzlocal", lambda: HELSINKI)
    forecast = forecast_from_fixture("forecast_boundaries.json", series)

    daily = _entity(forecast)._forecast(daily_mode=True)

    assert daily is not None
    assert _local_dates(daily) == expected_dates


def test_hourly_forecast_uses_helsinki_dst_transition(monkeypatch) -> None:
    monkeypatch.setattr(weather_module.tz, "tzlocal", lambda: HELSINKI)
    forecast = forecast_from_fixture("forecast_boundaries.json", "dst_transition")

    hourly = _entity(forecast)._forecast(daily_mode=False)
    assert hourly is not None
    local_hours = [int(item[ATTR_FORECAST_TIME][11:13]) for item in hourly]

    assert local_hours == [0, 2, 4, 5]
    assert all(item[ATTR_FORECAST_TIME].endswith(("+02:00", "+03:00")) for item in hourly)


def test_current_weather_exposes_real_client_values() -> None:
    weather = weather_from_fixture("forecast_normal.json")
    entity = _entity(forecast_from_fixture("forecast_normal.json"), weather)
    coordinator = cast(StubCoordinator, cast(Any, entity).coordinator)
    entity._data_func = coordinator.get_weather
    entity._attr_name = "Synthetic Helsinki"
    entity.logger = logging.getLogger(__name__)

    entity.update_callback()

    assert entity._attr_native_temperature == -4.0
    assert entity._attr_native_wind_gust_speed == 9.0
    assert entity._attr_native_wind_speed_unit == "m/s"
    assert entity._attr_condition == "partlycloudy"


def test_missing_current_values_become_none() -> None:
    weather = weather_from_fixture("missing_values.json")
    entity = _entity(forecast_from_fixture("missing_values.json"), weather)
    coordinator = cast(StubCoordinator, cast(Any, entity).coordinator)
    entity._data_func = coordinator.get_weather
    entity._attr_name = "Synthetic missing values"
    entity.logger = logging.getLogger(__name__)

    entity.update_callback()

    assert entity._attr_native_temperature is None
    assert entity._attr_native_wind_gust_speed is None


def test_wind_gust_sensor_uses_current_client_field() -> None:
    observation = weather_from_fixture("observation.json", "observation")
    assert observation is not None
    sensor = object.__new__(FMIBestConditionSensor)
    sensor._attr_state = STATE_UNAVAILABLE

    cast(Any, sensor)._FMIBestConditionSensor__convert_float(observation.data, "wind_gust")

    assert sensor._attr_state == 7.8


@pytest.mark.xfail(
    strict=True,
    reason="Issue #114: daily precipitation must sum hourly amounts; fixed in S05",
)
def test_daily_forecast_sums_hourly_precipitation_issue_114(monkeypatch) -> None:
    monkeypatch.setattr(weather_module.tz, "tzlocal", lambda: HELSINKI)
    forecast = forecast_from_fixture("forecast_normal.json")

    daily = _entity(forecast)._forecast(daily_mode=True)

    assert daily is not None
    assert daily[0][ATTR_FORECAST_NATIVE_PRECIPITATION] == pytest.approx(1.1)
    assert daily[0][ATTR_FORECAST_NATIVE_TEMP] == 1.0


@pytest.mark.xfail(
    strict=True,
    reason="S08 missing-data robustness: Value(None) must make the sensor unavailable",
)
def test_sensor_handles_none_value_without_exception() -> None:
    weather = weather_from_fixture("missing_values.json")
    assert weather is not None
    sensor = object.__new__(FMIBestConditionSensor)
    sensor._attr_state = 123

    cast(Any, sensor)._FMIBestConditionSensor__convert_float(weather.data, "temperature")

    assert sensor._attr_state == STATE_UNAVAILABLE


@pytest.mark.xfail(
    strict=True,
    reason="PR #116: polar sun events may be None; guard is implemented in S08",
)
def test_clear_condition_handles_missing_polar_sun_events(monkeypatch) -> None:
    fixture = load_json_fixture("high_latitude.json")
    monkeypatch.setattr(utils, "get_astral_event_date", lambda *args: fixture["sunrise"])

    assert utils.get_weather_symbol(1, hass=object()) in {"sunny", "clear-night"}
