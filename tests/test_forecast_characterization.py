"""Characterization tests for current FMI entity behavior."""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from typing import Any, cast
from zoneinfo import ZoneInfo

import pytest
from homeassistant.components.weather import (
    ATTR_FORECAST_CLOUD_COVERAGE,
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_HUMIDITY,
    ATTR_FORECAST_NATIVE_DEW_POINT,
    ATTR_FORECAST_NATIVE_PRECIPITATION,
    ATTR_FORECAST_NATIVE_PRESSURE,
    ATTR_FORECAST_NATIVE_TEMP,
    ATTR_FORECAST_NATIVE_TEMP_LOW,
    ATTR_FORECAST_NATIVE_WIND_GUST_SPEED,
    ATTR_FORECAST_NATIVE_WIND_SPEED,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    WeatherEntityFeature,
)
from homeassistant.util import dt as dt_util

from custom_components.fmi import utils
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
        self.unique_id = "60.17:24.94"

    def get_forecasts(self):
        return self.forecast.forecasts

    def get_hourly_forecasts(self):
        return self.forecast.forecasts

    def get_weather(self):
        return self.current

    def get_observation(self):
        return self.current


def _entity(forecast, weather=None) -> FMIWeatherEntity:
    entity = cast(Any, object.__new__(FMIWeatherEntity))
    entity.coordinator = StubCoordinator(forecast, weather)
    return cast(FMIWeatherEntity, entity)


def _local_dates(result: list[Any]) -> list[date]:
    return [
        datetime.fromisoformat(item[ATTR_FORECAST_TIME]).astimezone(HELSINKI).date()
        for item in result
    ]


def _set_helsinki_timezone(monkeypatch) -> None:
    monkeypatch.setattr(dt_util, "as_local", lambda value: value.astimezone(HELSINKI))
    monkeypatch.setattr(
        dt_util,
        "start_of_local_day",
        lambda value: datetime.combine(value, time(), tzinfo=HELSINKI),
    )


def test_hourly_forecast_spans_three_local_dates(monkeypatch) -> None:
    _set_helsinki_timezone(monkeypatch)
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
    _set_helsinki_timezone(monkeypatch)
    forecast = forecast_from_fixture("forecast_boundaries.json", series)

    daily = _entity(forecast)._forecast(daily_mode=True)

    assert daily is not None
    assert _local_dates(daily) == expected_dates


def test_hourly_forecast_uses_helsinki_dst_transition(monkeypatch) -> None:
    _set_helsinki_timezone(monkeypatch)
    forecast = forecast_from_fixture("forecast_boundaries.json", "dst_transition")

    hourly = _entity(forecast)._forecast(daily_mode=False)
    assert hourly is not None
    timestamps = [datetime.fromisoformat(item[ATTR_FORECAST_TIME]) for item in hourly]
    local_hours = [timestamp.astimezone(HELSINKI).hour for timestamp in timestamps]

    assert local_hours == [0, 2, 4, 5]
    assert all(timestamp.tzinfo is not None for timestamp in timestamps)
    assert all(timestamp.utcoffset() == timedelta(0) for timestamp in timestamps)


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
    sensor._attr_native_value = None

    cast(Any, sensor)._FMIBestConditionSensor__convert_float(observation.data, "wind_gust")

    assert sensor._attr_native_value == 7.8


def test_daily_forecast_sums_hourly_precipitation_issue_114(monkeypatch) -> None:
    _set_helsinki_timezone(monkeypatch)
    forecast = forecast_from_fixture("forecast_normal.json")

    daily = _entity(forecast)._forecast(daily_mode=True)

    assert daily is not None
    assert daily[0][ATTR_FORECAST_NATIVE_PRECIPITATION] == pytest.approx(1.1)
    assert daily[0][ATTR_FORECAST_NATIVE_TEMP] == 1.0


def test_daily_forecast_aggregates_mixed_conditions_wind_and_means(monkeypatch) -> None:
    _set_helsinki_timezone(monkeypatch)
    forecast = forecast_from_fixture("forecast_daily_cases.json", "mixed_conditions")

    daily = _entity(forecast)._forecast(daily_mode=True)

    assert daily is not None
    assert len(daily) == 1
    item = daily[0]
    assert item[ATTR_FORECAST_CONDITION] == "snowy"
    assert item[ATTR_FORECAST_NATIVE_TEMP] == -2.0
    assert item[ATTR_FORECAST_NATIVE_TEMP_LOW] == -5.0
    assert item[ATTR_FORECAST_NATIVE_PRECIPITATION] == pytest.approx(0.6)
    assert item[ATTR_FORECAST_NATIVE_WIND_SPEED] == 8.0
    assert item[ATTR_FORECAST_NATIVE_WIND_GUST_SPEED] == 12.0
    assert item[ATTR_FORECAST_WIND_BEARING] == 225.0
    assert item[ATTR_FORECAST_HUMIDITY] == pytest.approx(60.0)
    assert item[ATTR_FORECAST_NATIVE_PRESSURE] == pytest.approx(1002.0)
    assert item[ATTR_FORECAST_NATIVE_DEW_POINT] == pytest.approx(-14 / 3)
    assert item[ATTR_FORECAST_CLOUD_COVERAGE] == 60


@pytest.mark.parametrize(
    ("series", "expected"),
    [
        ("no_precipitation", None),
        ("explicit_zero_precipitation", 0.0),
    ],
)
def test_daily_forecast_distinguishes_missing_precipitation_from_zero(
    monkeypatch,
    series: str,
    expected: float | None,
) -> None:
    _set_helsinki_timezone(monkeypatch)
    forecast = forecast_from_fixture("forecast_daily_cases.json", series)

    daily = _entity(forecast)._forecast(daily_mode=True)

    assert daily is not None
    assert daily[0][ATTR_FORECAST_NATIVE_PRECIPITATION] == expected


@pytest.mark.parametrize(
    ("series", "expected_high", "expected_low"),
    [
        ("missing_temperatures", -2.0, -5.0),
        ("all_temperatures_missing", None, None),
    ],
)
def test_daily_forecast_handles_negative_and_missing_temperatures(
    monkeypatch,
    series: str,
    expected_high: float | None,
    expected_low: float | None,
) -> None:
    _set_helsinki_timezone(monkeypatch)
    forecast = forecast_from_fixture("forecast_daily_cases.json", series)

    daily = _entity(forecast)._forecast(daily_mode=True)

    assert daily is not None
    assert daily[0][ATTR_FORECAST_NATIVE_TEMP] == expected_high
    assert daily[0][ATTR_FORECAST_NATIVE_TEMP_LOW] == expected_low


def test_forecast_sorts_and_deduplicates_timestamps(monkeypatch) -> None:
    _set_helsinki_timezone(monkeypatch)
    forecast = forecast_from_fixture("forecast_daily_cases.json", "unordered_duplicates")
    entity = _entity(forecast)

    hourly = entity._forecast(daily_mode=False)
    daily = entity._forecast(daily_mode=True)

    assert hourly is not None
    assert [item[ATTR_FORECAST_NATIVE_TEMP] for item in hourly] == [1.0, 2.5, 3.0]
    assert [item[ATTR_FORECAST_TIME] for item in hourly] == sorted(
        item[ATTR_FORECAST_TIME] for item in hourly
    )
    assert daily is not None
    assert daily[0][ATTR_FORECAST_NATIVE_PRECIPITATION] == pytest.approx(0.6)


def test_daily_forecast_uses_partial_local_day_without_extrapolation(monkeypatch) -> None:
    _set_helsinki_timezone(monkeypatch)
    forecast = forecast_from_fixture("forecast_daily_cases.json", "mixed_conditions")

    daily = _entity(forecast)._forecast(daily_mode=True)

    assert daily is not None
    assert len(daily) == 1
    assert _local_dates(daily) == [date(2026, 5, 1)]
    assert daily[0][ATTR_FORECAST_NATIVE_PRECIPITATION] == pytest.approx(0.6)
    assert daily[0][ATTR_FORECAST_TIME] == "2026-04-30T21:00:00+00:00"


def test_hourly_forecast_preserves_both_dst_end_hours(monkeypatch) -> None:
    _set_helsinki_timezone(monkeypatch)
    forecast = forecast_from_fixture("forecast_daily_cases.json", "dst_end")

    hourly = _entity(forecast)._forecast(daily_mode=False)

    assert hourly is not None
    local_times = [
        datetime.fromisoformat(item[ATTR_FORECAST_TIME]).astimezone(HELSINKI) for item in hourly
    ]
    assert [timestamp.hour for timestamp in local_times] == [0, 1, 2, 3, 3, 4]
    assert local_times[3].utcoffset() != local_times[4].utcoffset()
    assert _local_dates(hourly) == [date(2026, 10, 25)] * 6


async def test_forecast_methods_return_literal_granularity(monkeypatch) -> None:
    _set_helsinki_timezone(monkeypatch)
    forecast = forecast_from_fixture("forecast_normal.json")
    coordinator = StubCoordinator(forecast)
    legacy_daily = FMIWeatherEntity("FMI", cast(Any, coordinator), daily_mode=True)

    hourly = await legacy_daily.async_forecast_hourly()
    daily = await legacy_daily.async_forecast_daily()

    assert hourly is not None and len(hourly) == 49
    assert daily is not None and len(daily) == 3
    primary = FMIWeatherEntity("FMI", cast(Any, coordinator))
    observation = FMIWeatherEntity("FMI", cast(Any, coordinator), station_id=True)
    assert primary.supported_features == (
        WeatherEntityFeature.FORECAST_HOURLY | WeatherEntityFeature.FORECAST_DAILY
    )
    assert observation.supported_features == 0
    assert "forecast" not in FMIWeatherEntity.__dict__


def test_hourly_forecast_uses_current_home_assistant_keys_and_units(monkeypatch) -> None:
    _set_helsinki_timezone(monkeypatch)
    forecast = forecast_from_fixture("forecast_daily_cases.json", "mixed_conditions")
    entity = _entity(forecast, weather_from_fixture("forecast_normal.json"))
    coordinator = cast(StubCoordinator, cast(Any, entity).coordinator)
    entity._data_func = coordinator.get_weather
    entity._attr_name = "Synthetic Helsinki"
    entity.logger = logging.getLogger(__name__)

    entity.update_callback()
    hourly = entity._forecast(daily_mode=False)

    assert entity._attr_native_precipitation_unit == "mm"
    assert hourly is not None
    assert set(hourly[0]) == {
        ATTR_FORECAST_TIME,
        ATTR_FORECAST_CONDITION,
        ATTR_FORECAST_NATIVE_TEMP,
        ATTR_FORECAST_NATIVE_PRECIPITATION,
        ATTR_FORECAST_NATIVE_WIND_SPEED,
        ATTR_FORECAST_NATIVE_WIND_GUST_SPEED,
        ATTR_FORECAST_WIND_BEARING,
        ATTR_FORECAST_NATIVE_PRESSURE,
        ATTR_FORECAST_HUMIDITY,
        ATTR_FORECAST_CLOUD_COVERAGE,
        ATTR_FORECAST_NATIVE_DEW_POINT,
    }


def test_sensor_handles_none_value_without_exception() -> None:
    weather = weather_from_fixture("missing_values.json")
    assert weather is not None
    sensor = object.__new__(FMIBestConditionSensor)
    sensor._attr_native_value = 123

    cast(Any, sensor)._FMIBestConditionSensor__convert_float(weather.data, "temperature")

    assert sensor._attr_native_value is None


@pytest.mark.xfail(
    strict=True,
    reason="PR #116: polar sun events may be None; guard is implemented in S08",
)
def test_clear_condition_handles_missing_polar_sun_events(monkeypatch) -> None:
    fixture = load_json_fixture("high_latitude.json")
    monkeypatch.setattr(utils, "get_astral_event_date", lambda *args: fixture["sunrise"])

    assert utils.get_weather_symbol(1, hass=object()) in {"sunny", "clear-night"}
