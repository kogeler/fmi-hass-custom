# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""S08 regressions for time boundaries and incomplete FMI values."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from types import MappingProxyType, SimpleNamespace
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

from custom_components.fmi import FMIDataUpdateCoordinator, const, fmi, utils
from custom_components.fmi.weather import FMIWeatherEntity
from tests.helpers.fmi import forecast_from_fixture, weather_from_fixture

HELSINKI = ZoneInfo("Europe/Helsinki")


class _ForecastCoordinator:
    """Minimum coordinator surface for forecast output tests."""

    def __init__(self, samples: list[Any]) -> None:
        self.forecast = SimpleNamespace(forecasts=samples)

    def get_hourly_forecasts(self) -> list[Any]:
        return self.forecast.forecasts

    def get_forecast_probabilities(self, timestamp: object) -> fmi.ForecastProbabilities:
        _ = timestamp
        return fmi.ForecastProbabilities(None, None)


def _entity(samples: list[Any]) -> FMIWeatherEntity:
    entity = cast(Any, object.__new__(FMIWeatherEntity))
    entity.coordinator = _ForecastCoordinator(samples)
    entity.logger = logging.getLogger(__name__)
    return cast(FMIWeatherEntity, entity)


def _value(value: object, unit: str = "") -> fmi_models.Value:
    return fmi_models.Value(cast(Any, value), unit)


def test_best_time_allowed_fmi_symbols_match_contract() -> None:
    """Keep the complete eligible-condition gate explicit and reviewable."""
    assert const.BEST_COND_SYMBOLS == [1, 2, 21, 3, 31, 32, 41, 42, 51, 52, 91, 92]


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

    assert _entity([sample])._hourly_forecast()[0][ATTR_FORECAST_CONDITION] is None


def test_empty_forecast_returns_empty_hourly_and_daily_lists() -> None:
    entity = _entity([])

    assert entity._hourly_forecast() == []
    assert entity._daily_forecast() == []


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

    result = _entity([sample])._hourly_forecast()

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

    result = _entity([sample])._hourly_forecast()

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

    result = _entity(samples)._hourly_forecast()

    assert len(result) == 1
    assert datetime.fromisoformat(result[0][ATTR_FORECAST_TIME]).tzinfo is not None


def _best_condition_coordinator(
    current: fmi_models.Weather,
    forecast: fmi_models.Forecast,
    probabilities: dict[datetime, fmi.ForecastProbabilities] | None = None,
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
    probability_map = probabilities or {
        sample.time.astimezone(UTC): fmi.ForecastProbabilities(20.0, 0.0)
        for sample in forecast.forecasts
        if isinstance(sample.time, datetime)
        and sample.time.tzinfo is not None
        and sample.time.utcoffset() is not None
    }
    coordinator._forecast_supplements = SimpleNamespace(
        current=fmi.ForecastProbabilities(None, None),
        by_time=MappingProxyType(probability_map),
    )
    return cast(FMIDataUpdateCoordinator, coordinator)


def test_best_time_prefers_apparent_comfort_over_hottest_hour(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Choose perceived comfort instead of rewarding the hottest summer hour."""
    base = forecast_from_fixture("forecast_normal.json")
    current_time = datetime(2026, 6, 15, 9, tzinfo=UTC)
    cooler = base.forecasts[0]._replace(
        time=datetime(2026, 6, 15, 10, tzinfo=UTC),
        temperature=_value(18.0, "°C"),
        feels_like=_value(23.0, "°C"),
    )
    hottest = base.forecasts[1]._replace(
        time=datetime(2026, 6, 15, 11, tzinfo=UTC),
        temperature=_value(27.0, "°C"),
        feels_like=_value(34.0, "°C"),
    )
    weather = weather_from_fixture("forecast_normal.json")
    assert weather is not None
    current = weather._replace(
        data=weather.data._replace(
            time=current_time,
            temperature=_value(15.0, "°C"),
        )
    )
    coordinator = _best_condition_coordinator(
        current,
        base._replace(forecasts=[cooler, hottest]),
    )
    coordinator.min_temperature = 15.0
    coordinator.max_temperature = 35.0
    monkeypatch.setattr(dt_util, "now", lambda: current_time.astimezone(HELSINKI))
    monkeypatch.setattr(dt_util, "as_local", lambda value: value.astimezone(HELSINKI))

    cast(Any, coordinator)._FMIDataUpdateCoordinator__update_best_weather_condition()

    best = coordinator.best_condition
    assert best.status == const.BEST_CONDITION_AVAIL
    assert best.time == cooler.time.astimezone(HELSINKI)
    assert best.temperature == 18.0
    assert best.apparent_temperature == 23.0


def test_best_time_reports_no_suitable_hour_without_current_weather_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Return a valid empty outcome instead of presenting the current time as best."""
    base = forecast_from_fixture("forecast_normal.json")
    current_time = datetime(2026, 6, 15, 9, tzinfo=UTC)
    rejected = base.forecasts[0]._replace(
        time=datetime(2026, 6, 15, 10, tzinfo=UTC),
        symbol=_value(61),
    )
    weather = weather_from_fixture("forecast_normal.json")
    assert weather is not None
    current = weather._replace(data=weather.data._replace(time=current_time))
    coordinator = _best_condition_coordinator(
        current,
        base._replace(forecasts=[rejected]),
    )
    monkeypatch.setattr(dt_util, "now", lambda: current_time.astimezone(HELSINKI))
    monkeypatch.setattr(dt_util, "as_local", lambda value: value.astimezone(HELSINKI))

    cast(Any, coordinator)._FMIDataUpdateCoordinator__update_best_weather_condition()

    best = coordinator.best_condition
    assert best.status == const.BEST_CONDITION_NO_SUITABLE
    assert best.time is None
    assert best.temperature is None


@pytest.mark.parametrize(
    ("fixture", "series", "now", "expected_date", "expected_temperature"),
    [
        (
            "forecast_boundaries.json",
            "month_boundary",
            datetime(2026, 1, 31, 12, tzinfo=HELSINKI),
            date(2026, 1, 31),
            -2.0,
        ),
        (
            "forecast_boundaries.json",
            "year_boundary",
            datetime(2026, 12, 31, 12, tzinfo=HELSINKI),
            date(2026, 12, 31),
            -4.0,
        ),
        (
            "forecast_boundaries.json",
            "leap_day",
            datetime(2028, 2, 29, 0, tzinfo=HELSINKI),
            date(2028, 2, 29),
            -4.0,
        ),
        (
            "forecast_daily_cases.json",
            "dst_end",
            datetime(2026, 10, 25, 0, tzinfo=HELSINKI),
            date(2026, 10, 25),
            0.0,
        ),
    ],
    ids=("month", "year", "leap-day", "dst-end"),
)
def test_best_time_stays_on_current_local_date_across_calendar_boundaries(
    monkeypatch: pytest.MonkeyPatch,
    fixture: str,
    series: str,
    now: datetime,
    expected_date: date,
    expected_temperature: float,
) -> None:
    forecast = forecast_from_fixture(fixture, series)
    weather = weather_from_fixture("forecast_normal.json")
    assert weather is not None
    coordinator = _best_condition_coordinator(weather, forecast)
    monkeypatch.setattr(dt_util, "now", lambda: now)
    monkeypatch.setattr(dt_util, "as_local", lambda value: value.astimezone(HELSINKI))

    cast(Any, coordinator)._FMIDataUpdateCoordinator__update_best_weather_condition()

    best = coordinator.best_condition
    assert best.status == const.BEST_CONDITION_AVAIL
    assert best.time is not None
    assert best.time.date() == expected_date
    assert best.temperature == expected_temperature


def test_best_time_accepts_numeric_strings_and_skips_invalid_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = forecast_from_fixture("forecast_normal.json")
    invalid = base.forecasts[0]._replace(
        time=datetime(2026, 2, 10, 10, tzinfo=UTC),
        temperature=_value("invalid", "°C"),
    )
    valid = base.forecasts[1]._replace(
        time=datetime(2026, 2, 10, 11, tzinfo=UTC),
        temperature=_value("12.5", "°C"),
        feels_like=_value("17.5", "°C"),
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

    best = coordinator.best_condition
    assert best.status == const.BEST_CONDITION_AVAIL
    assert best.temperature == 12.5
    assert best.apparent_temperature == 17.5
    assert best.humidity == 60.0
    assert best.wind_speed == 4.5
    assert best.precipitation == 0.1


@pytest.mark.parametrize(
    (
        "left_feels_like",
        "right_feels_like",
        "left_pop",
        "right_pop",
        "left_thunder",
        "right_thunder",
        "left_precipitation",
        "right_precipitation",
        "expected",
    ),
    [
        (30.0, 20.0, 90.0, 0.0, 0.0, 1.0, 0.2, 0.0, "left"),
        (17.0, 20.0, 20.0, 20.0, 0.0, 0.0, 0.1, 0.1, "right"),
        (20.0, 20.0, 30.0, 10.0, 0.0, 0.0, 0.1, 0.1, "right"),
        (20.0, 20.0, 10.0, 10.0, 0.0, 0.0, 0.2, 0.1, "right"),
        (20.0, 20.0, 10.0, 10.0, 0.0, 0.0, 0.1, 0.1, "left"),
    ],
    ids=("thunder", "thermal", "pop", "amount", "earliest"),
)
def test_best_time_uses_frozen_lexicographic_order(
    monkeypatch: pytest.MonkeyPatch,
    left_feels_like: float,
    right_feels_like: float,
    left_pop: float,
    right_pop: float,
    left_thunder: float,
    right_thunder: float,
    left_precipitation: float,
    right_precipitation: float,
    expected: str,
) -> None:
    """Apply thunder, thermal, PoP, amount, and timestamp priorities in order."""
    base = forecast_from_fixture("forecast_normal.json")
    left = base.forecasts[0]._replace(
        time=datetime(2026, 6, 15, 10, tzinfo=UTC),
        temperature=_value(20.0, "°C"),
        feels_like=_value(left_feels_like, "°C"),
        precipitation_amount=_value(left_precipitation, "mm/h"),
    )
    right = base.forecasts[1]._replace(
        time=datetime(2026, 6, 15, 11, tzinfo=UTC),
        temperature=_value(20.0, "°C"),
        feels_like=_value(right_feels_like, "°C"),
        precipitation_amount=_value(right_precipitation, "mm/h"),
    )
    probabilities = {
        left.time: fmi.ForecastProbabilities(left_pop, left_thunder),
        right.time: fmi.ForecastProbabilities(right_pop, right_thunder),
    }
    weather = weather_from_fixture("forecast_normal.json")
    assert weather is not None
    coordinator = _best_condition_coordinator(
        weather,
        base._replace(forecasts=[left, right]),
        probabilities,
    )
    coordinator.min_temperature = 10.0
    coordinator.max_temperature = 30.0
    now = datetime(2026, 6, 15, 9, tzinfo=UTC)
    monkeypatch.setattr(dt_util, "now", lambda: now.astimezone(HELSINKI))
    monkeypatch.setattr(dt_util, "as_local", lambda value: value.astimezone(HELSINKI))

    cast(Any, coordinator)._FMIDataUpdateCoordinator__update_best_weather_condition()

    selected = left if expected == "left" else right
    assert coordinator.best_condition.status == const.BEST_CONDITION_AVAIL
    assert coordinator.best_condition.time == selected.time.astimezone(HELSINKI)


@pytest.mark.parametrize(
    ("feels_like", "humidity", "wind", "precipitation", "probability"),
    [
        (10.0, 30.0, 0.0, 0.0, 0.0),
        (30.0, 70.0, 25.0, 0.2, 100.0),
    ],
    ids=("minimum", "maximum"),
)
def test_best_time_includes_every_configured_boundary(
    monkeypatch: pytest.MonkeyPatch,
    feels_like: float,
    humidity: float,
    wind: float,
    precipitation: float,
    probability: float,
) -> None:
    """Treat all user limits and probability endpoints as inclusive."""
    base = forecast_from_fixture("forecast_normal.json")
    sample = base.forecasts[0]._replace(
        time=datetime(2026, 6, 15, 10, tzinfo=UTC),
        feels_like=_value(feels_like, "°C"),
        humidity=_value(humidity, "%"),
        wind_speed=_value(wind, "m/s"),
        precipitation_amount=_value(precipitation, "mm/h"),
    )
    weather = weather_from_fixture("forecast_normal.json")
    assert weather is not None
    coordinator = _best_condition_coordinator(
        weather,
        base._replace(forecasts=[sample]),
        {sample.time: fmi.ForecastProbabilities(probability, probability)},
    )
    coordinator.min_temperature = 10.0
    coordinator.max_temperature = 30.0
    coordinator.min_humidity = 30.0
    coordinator.max_humidity = 70.0
    coordinator.min_wind_speed = 0.0
    coordinator.max_wind_speed = 25.0
    coordinator.min_precip = 0.0
    coordinator.max_precip = 0.2
    now = datetime(2026, 6, 15, 9, tzinfo=UTC)
    monkeypatch.setattr(dt_util, "now", lambda: now.astimezone(HELSINKI))
    monkeypatch.setattr(dt_util, "as_local", lambda value: value.astimezone(HELSINKI))

    cast(Any, coordinator)._FMIDataUpdateCoordinator__update_best_weather_condition()

    best = coordinator.best_condition
    assert best.status == const.BEST_CONDITION_AVAIL
    assert best.precipitation_probability == probability
    assert best.thunderstorm_probability == probability


def test_best_time_uses_only_remaining_configured_interval_samples(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exclude past, skipped-interval, and next-local-day forecast samples."""
    base = forecast_from_fixture("forecast_normal.json")
    samples = [
        base.forecasts[0]._replace(
            time=datetime(2026, 6, 15, 8, tzinfo=UTC),
            feels_like=_value(20.0, "°C"),
        ),
        base.forecasts[1]._replace(
            time=datetime(2026, 6, 15, 10, tzinfo=UTC),
            feels_like=_value(20.0, "°C"),
        ),
        base.forecasts[2]._replace(
            time=datetime(2026, 6, 16, 8, tzinfo=UTC),
            feels_like=_value(20.0, "°C"),
        ),
        base.forecasts[3]._replace(
            time=datetime(2026, 6, 15, 12, tzinfo=UTC),
            feels_like=_value(24.0, "°C"),
        ),
    ]
    weather = weather_from_fixture("forecast_normal.json")
    assert weather is not None
    forecast = base._replace(forecasts=samples)
    coordinator = _best_condition_coordinator(weather, forecast)
    coordinator.time_step = 3
    coordinator.min_temperature = 10.0
    coordinator.max_temperature = 30.0
    now = datetime(2026, 6, 15, 9, tzinfo=UTC)
    monkeypatch.setattr(dt_util, "now", lambda: now.astimezone(HELSINKI))
    monkeypatch.setattr(dt_util, "as_local", lambda value: value.astimezone(HELSINKI))

    cast(Any, coordinator)._FMIDataUpdateCoordinator__update_best_weather_condition()

    assert coordinator.best_condition.time == samples[3].time.astimezone(HELSINKI)


def test_best_time_clears_selection_for_empty_and_unusable_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Clear every selected factor and distinguish healthy-empty from unusable data."""
    base = forecast_from_fixture("forecast_normal.json")
    valid = base.forecasts[0]._replace(
        time=datetime(2026, 6, 15, 10, tzinfo=UTC),
        feels_like=_value(20.0, "°C"),
    )
    weather = weather_from_fixture("forecast_normal.json")
    assert weather is not None
    coordinator = _best_condition_coordinator(weather, base._replace(forecasts=[valid]))
    coordinator.min_temperature = 10.0
    coordinator.max_temperature = 30.0
    now = datetime(2026, 6, 15, 9, tzinfo=UTC)
    monkeypatch.setattr(dt_util, "now", lambda: now.astimezone(HELSINKI))
    monkeypatch.setattr(dt_util, "as_local", lambda value: value.astimezone(HELSINKI))

    cast(Any, coordinator)._FMIDataUpdateCoordinator__update_best_weather_condition()
    assert coordinator.best_condition.status == const.BEST_CONDITION_AVAIL

    rejected = valid._replace(symbol=_value(61))
    coordinator.forecast = base._replace(forecasts=[rejected])
    cast(Any, coordinator)._FMIDataUpdateCoordinator__update_best_weather_condition()
    best = coordinator.best_condition
    assert best.status == const.BEST_CONDITION_NO_SUITABLE
    assert best.time is None
    assert best.temperature is None
    assert best.apparent_temperature is None
    assert best.precipitation_probability is None
    assert best.thunderstorm_probability is None

    incomplete = valid._replace(feels_like=_value(None, "°C"))
    coordinator.forecast = base._replace(forecasts=[incomplete])
    cast(Any, coordinator)._FMIDataUpdateCoordinator__update_best_weather_condition()
    assert coordinator.best_condition.status == const.BEST_CONDITION_NOT_AVAIL
    assert coordinator.best_condition.time is None

    coordinator.forecast = base._replace(forecasts=[])
    cast(Any, coordinator)._FMIDataUpdateCoordinator__update_best_weather_condition()
    assert coordinator.best_condition.status == const.BEST_CONDITION_NOT_AVAIL


@pytest.mark.parametrize(
    "metric",
    (
        "symbol",
        "temperature",
        "feels_like",
        "humidity",
        "wind_speed",
        "precipitation_amount",
        "precipitation_probability",
        "thunderstorm_probability",
        "invalid_precipitation_probability",
        "invalid_thunderstorm_probability",
    ),
)
def test_best_time_requires_every_complete_finite_metric(
    monkeypatch: pytest.MonkeyPatch,
    metric: str,
) -> None:
    """Classify a remaining hour with any missing required factor as unusable."""
    base = forecast_from_fixture("forecast_normal.json")
    sample = base.forecasts[0]._replace(
        time=datetime(2026, 6, 15, 10, tzinfo=UTC),
        temperature=_value(20.0, "°C"),
        feels_like=_value(20.0, "°C"),
    )
    precipitation_probability: float | None = 10.0
    thunderstorm_probability: float | None = 0.0
    if metric == "precipitation_probability":
        precipitation_probability = None
    elif metric == "thunderstorm_probability":
        thunderstorm_probability = None
    elif metric == "invalid_precipitation_probability":
        precipitation_probability = 101.0
    elif metric == "invalid_thunderstorm_probability":
        thunderstorm_probability = -1.0
    else:
        sample = sample._replace(**{metric: _value(None)})
    weather = weather_from_fixture("forecast_normal.json")
    assert weather is not None
    coordinator = _best_condition_coordinator(
        weather,
        base._replace(forecasts=[sample]),
        {
            sample.time: fmi.ForecastProbabilities(
                precipitation_probability,
                thunderstorm_probability,
            )
        },
    )
    coordinator.min_temperature = 10.0
    coordinator.max_temperature = 30.0
    now = datetime(2026, 6, 15, 9, tzinfo=UTC)
    monkeypatch.setattr(dt_util, "now", lambda: now.astimezone(HELSINKI))
    monkeypatch.setattr(dt_util, "as_local", lambda value: value.astimezone(HELSINKI))

    cast(Any, coordinator)._FMIDataUpdateCoordinator__update_best_weather_condition()

    assert coordinator.best_condition.status == const.BEST_CONDITION_NOT_AVAIL
    assert coordinator.best_condition.time is None


def test_best_time_reports_no_suitable_when_today_has_no_remaining_hour(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Treat an exhausted local day as a healthy calculation with no result."""
    base = forecast_from_fixture("forecast_normal.json")
    samples = [
        base.forecasts[0]._replace(time=datetime(2026, 6, 15, 8, tzinfo=UTC)),
        base.forecasts[1]._replace(time=datetime(2026, 6, 16, 8, tzinfo=UTC)),
    ]
    weather = weather_from_fixture("forecast_normal.json")
    assert weather is not None
    coordinator = _best_condition_coordinator(weather, base._replace(forecasts=samples))
    now = datetime(2026, 6, 15, 9, tzinfo=UTC)
    monkeypatch.setattr(dt_util, "now", lambda: now.astimezone(HELSINKI))
    monkeypatch.setattr(dt_util, "as_local", lambda value: value.astimezone(HELSINKI))

    cast(Any, coordinator)._FMIDataUpdateCoordinator__update_best_weather_condition()

    assert coordinator.best_condition.status == const.BEST_CONDITION_NO_SUITABLE


def test_best_time_treats_stored_inverted_limits_as_no_suitable_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Do not mutate historical limits or choose outside an impossible range."""
    base = forecast_from_fixture("forecast_normal.json")
    sample = base.forecasts[0]._replace(
        time=datetime(2026, 6, 15, 10, tzinfo=UTC),
        feels_like=_value(20.0, "°C"),
    )
    weather = weather_from_fixture("forecast_normal.json")
    assert weather is not None
    coordinator = _best_condition_coordinator(weather, base._replace(forecasts=[sample]))
    coordinator.min_temperature = 30.0
    coordinator.max_temperature = 10.0
    now = datetime(2026, 6, 15, 9, tzinfo=UTC)
    monkeypatch.setattr(dt_util, "now", lambda: now.astimezone(HELSINKI))
    monkeypatch.setattr(dt_util, "as_local", lambda value: value.astimezone(HELSINKI))

    cast(Any, coordinator)._FMIDataUpdateCoordinator__update_best_weather_condition()

    assert coordinator.min_temperature == 30.0
    assert coordinator.max_temperature == 10.0
    assert coordinator.best_condition.status == const.BEST_CONDITION_NO_SUITABLE


def test_best_time_rejects_forecast_without_any_aware_timestamp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reserve unavailable for a forecast collection unusable for time evaluation."""
    base = forecast_from_fixture("forecast_normal.json")
    sample = base.forecasts[0]._replace(time=cast(Any, datetime(2026, 6, 15, 10)))
    weather = weather_from_fixture("forecast_normal.json")
    assert weather is not None
    coordinator = _best_condition_coordinator(weather, base._replace(forecasts=[sample]))
    now = datetime(2026, 6, 15, 9, tzinfo=UTC)
    monkeypatch.setattr(dt_util, "now", lambda: now.astimezone(HELSINKI))
    monkeypatch.setattr(dt_util, "as_local", lambda value: value.astimezone(HELSINKI))

    cast(Any, coordinator)._FMIDataUpdateCoordinator__update_best_weather_condition()

    assert coordinator.best_condition.status == const.BEST_CONDITION_NOT_AVAIL
