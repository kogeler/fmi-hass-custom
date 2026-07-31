"""Contract tests for the selected fmi-weather-client release."""

from __future__ import annotations

import inspect
from datetime import UTC, datetime
from xml.parsers.expat import ExpatError

import fmi_weather_client as fmi
import pytest
from fmi_weather_client import models
from fmi_weather_client.errors import ClientError, ServerError

from tests.helpers.fmi import (
    CONSUMED_WEATHER_DATA_FIELDS,
    FIXTURE_DIR,
    FakeFMIClient,
    FMIContractError,
    forecast_from_fixture,
    load_json_fixture,
    weather_data_from_payload,
    weather_from_fixture,
)


def test_consumed_model_shape_matches_installed_client() -> None:
    """Pin only model fields that production code reads."""
    assert models.Value._fields == ("value", "unit")
    assert models.Weather._fields == ("place", "lat", "lon", "data")
    assert models.Forecast._fields == ("place", "lat", "lon", "forecasts")
    assert CONSUMED_WEATHER_DATA_FIELDS <= set(models.WeatherData._fields)


def test_consumed_async_method_signatures_match_installed_client() -> None:
    """Detect incompatible method changes before the dependency upgrade."""
    assert tuple(inspect.signature(fmi.async_weather_by_coordinates).parameters) == ("lat", "lon")
    assert tuple(inspect.signature(fmi.async_forecast_by_coordinates).parameters) == (
        "lat",
        "lon",
        "timestep_hours",
        "forecast_points",
    )
    assert tuple(inspect.signature(fmi.async_observation_by_station_id).parameters) == ("fmi_sid",)
    assert tuple(inspect.signature(fmi.async_observation_by_place).parameters) == ("place",)


def test_current_client_maps_three_second_wind_gust_field() -> None:
    """Characterize the upstream WindGust field consumed for issue #111."""
    data = fmi.forecast_parser._create_weather_data(  # noqa: SLF001
        datetime(2026, 5, 20, 12, tzinfo=UTC),
        {
            "Temperature": 6.5,
            "Humidity": 79.0,
            "WindSpeedMS": 4.2,
            "WindGust": 7.8,
        },
    )

    assert data.wind_gust == models.Value(7.8, "m/s")
    assert data.wind_max == models.Value(None, "m/s")


def test_observation_and_empty_results_use_real_models() -> None:
    observation = weather_from_fixture("observation.json", "observation")
    empty_forecast = forecast_from_fixture("empty_results.json")
    empty_observation = weather_from_fixture("empty_results.json", "observation")

    assert isinstance(observation, models.Weather)
    assert observation.data.wind_gust.value == 7.8
    assert observation.data.time.tzinfo is not None
    assert empty_forecast.forecasts == []
    assert empty_observation is None


def test_unexpected_contract_shape_has_useful_error() -> None:
    fixture = load_json_fixture("observation.json")
    defaults = dict(fixture["defaults"])
    defaults.pop("wind_gust")

    with pytest.raises(FMIContractError, match=r"missing FMI weather fields: wind_gust"):
        weather_data_from_payload(fixture["observation"], defaults)


async def test_fake_client_replays_values_errors_and_calls() -> None:
    weather = weather_from_fixture("forecast_normal.json")
    forecast = forecast_from_fixture("forecast_normal.json")
    errors = load_json_fixture("errors.json")
    server_error = ServerError(errors["server"]["status_code"], errors["server"]["body"])
    fake = FakeFMIClient(weather=weather, forecast=forecast, forecast_error=server_error)

    assert await fake.async_weather_by_coordinates(60.17, 24.94) is weather
    with pytest.raises(ServerError) as raised:
        await fake.async_forecast_by_coordinates(60.17, 24.94, 1, 49)

    assert raised.value.status_code == 503
    assert raised.value.body == "Synthetic service unavailable"
    assert fake.calls == [
        ("weather", (60.17, 24.94)),
        ("forecast", (60.17, 24.94, 1, 49)),
    ]


def test_client_server_and_parse_error_shapes() -> None:
    errors = load_json_fixture("errors.json")
    client_error = ClientError(errors["client"]["status_code"], errors["client"]["message"])
    server_error = ServerError(errors["server"]["status_code"], errors["server"]["body"])

    assert (client_error.status_code, client_error.message) == (
        400,
        "Synthetic invalid stored query",
    )
    assert (server_error.status_code, server_error.body) == (
        503,
        "Synthetic service unavailable",
    )
    with pytest.raises(ExpatError):
        fmi.forecast_parser.parse_fmi_response(
            errors["parse"]["body"],
            models.RequestType.FORECAST,
        )


def test_fixture_corpus_is_small_synthetic_and_sanitized() -> None:
    """Keep the offline corpus reviewable and free of private capture data."""
    fixture_files = [path for path in FIXTURE_DIR.iterdir() if path.is_file()]

    assert fixture_files
    assert all(path.stat().st_size < 12_000 for path in fixture_files)
    for path in fixture_files:
        text = path.read_text(encoding="utf-8").lower()
        assert "api_key" not in text
        assert "access_token" not in text
        assert "password" not in text

    for path in FIXTURE_DIR.glob("*.json"):
        fixture = load_json_fixture(path.name)
        assert fixture["_meta"]["kind"] == "synthetic"
        if "lat" in fixture:
            assert float(fixture["lat"]) == round(float(fixture["lat"]), 2)
            assert float(fixture["lon"]) == round(float(fixture["lon"]), 2)
