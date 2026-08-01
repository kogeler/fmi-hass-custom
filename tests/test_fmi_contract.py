# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Contract tests for the selected fmi-weather-client release."""

from __future__ import annotations

import inspect
import threading
from datetime import UTC, datetime
from unittest.mock import Mock
from xml.parsers.expat import ExpatError

import fmi_weather_client as fmi
import pytest
from fmi_weather_client import models
from fmi_weather_client.errors import ClientError, ServerError
from homeassistant.util.loop import protect_loop

from custom_components.fmi import fmi_client as integration_fmi_client
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
    """Characterize the upstream WindGust field consumed by sensor entities."""
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


def test_current_client_forecast_query_omits_hourly_maximum_gust() -> None:
    """Reproduce the upstream query mismatch behind unavailable wind gusts."""
    params = fmi.http._create_params(  # noqa: SLF001
        models.RequestType.FORECAST,
        60,
        4,
        lat=60.17,
        lon=24.94,
    )

    assert "WindGust" in params["parameters"]
    assert "HourlyMaximumGust" not in params["parameters"]


@pytest.mark.parametrize(
    ("hourly_gust", "native_gust", "expected"),
    [
        (9.4, 7.0, 9.4),
        (0.0, 7.0, 0.0),
        (None, 7.0, 7.0),
        (None, None, None),
    ],
)
def test_client_adapter_maps_hourly_maximum_gust_with_finite_precedence(
    monkeypatch,
    hourly_gust: float | None,
    native_gust: float | None,
    expected: float | None,
) -> None:
    """Map forecast hourly maximum first and retain a valid native fallback."""
    timestamp = datetime(2026, 5, 20, 12, tzinfo=UTC)
    weather = weather_from_fixture("forecast_normal.json")
    assert weather is not None
    sample = weather.data._replace(
        time=timestamp,
        wind_gust=models.Value(native_gust, "m/s"),
        wind_max=models.Value(None, "m/s"),
    )
    parsed = models.Forecast("Helsinki", 60.17, 24.94, [sample])
    monkeypatch.setattr(
        integration_fmi_client.upstream.forecast_parser,
        "parse_fmi_response",
        lambda body, request_type: parsed,
    )
    raw_hourly = "NaN" if hourly_gust is None else str(hourly_gust)
    body = f"""
        <wfs:FeatureCollection
            xmlns:wfs="http://www.opengis.net/wfs/2.0"
            xmlns:gml="http://www.opengis.net/gml/3.2"
            xmlns:gmlcov="http://www.opengis.net/gmlcov/1.0"
            xmlns:swe="http://www.opengis.net/swe/2.0">
          <swe:DataRecord>
            <swe:field name="WindGust" />
            <swe:field name="HourlyMaximumGust" />
          </swe:DataRecord>
          <gmlcov:positions>60.17 24.94 {int(timestamp.timestamp())}</gmlcov:positions>
          <gml:doubleOrNilReasonTupleList>NaN {raw_hourly}</gml:doubleOrNilReasonTupleList>
        </wfs:FeatureCollection>
    """

    result = integration_fmi_client._parse_forecast_response(  # noqa: SLF001
        body,
        models.RequestType.FORECAST,
    )

    assert result.forecasts[0].wind_gust == models.Value(expected, "m/s")
    assert result.forecasts[0].wind_max == models.Value(hourly_gust, "m/s")


def test_client_adapter_adds_hourly_gust_without_second_request(monkeypatch) -> None:
    """Change the selected parameter list while retaining one upstream HTTP call."""
    captured: list[dict[str, object]] = []
    parsed = forecast_from_fixture("forecast_normal.json")

    def capture_request(params: dict[str, object]) -> str:
        captured.append(dict(params))
        return "synthetic body"

    monkeypatch.setattr(
        integration_fmi_client.upstream.http,
        "_create_params",
        lambda *args, **kwargs: {"parameters": "Temperature,WindGust"},
    )
    monkeypatch.setattr(
        integration_fmi_client.upstream.http,
        "_send_request",
        capture_request,
    )
    monkeypatch.setattr(
        integration_fmi_client,
        "_parse_forecast_response",
        lambda body, request_type: parsed,
    )

    result = integration_fmi_client._request_by_coordinates(  # noqa: SLF001
        models.RequestType.FORECAST,
        60.17,
        24.94,
        60,
        48,
    )

    assert result is parsed
    assert len(captured) == 1
    assert captured[0]["parameters"] == "Temperature,WindGust,HourlyMaximumGust"


@pytest.mark.parametrize(
    ("parameters", "expected"),
    [
        (
            "Temperature,HourlyMaximumGust",
            "Temperature,HourlyMaximumGust",
        ),
        (
            "Temperature",
            "Temperature,HourlyMaximumGust",
        ),
    ],
)
def test_client_adapter_keeps_one_hourly_gust_parameter(
    monkeypatch,
    parameters: str,
    expected: str,
) -> None:
    """Avoid duplicate fields and append the supported gust when no legacy field exists."""
    captured: list[dict[str, object]] = []
    parsed = forecast_from_fixture("forecast_normal.json")

    def capture_request(params: dict[str, object]) -> str:
        captured.append(dict(params))
        return "synthetic body"

    monkeypatch.setattr(
        integration_fmi_client.upstream.http,
        "_create_params",
        lambda *args, **kwargs: {"parameters": parameters},
    )
    monkeypatch.setattr(
        integration_fmi_client.upstream.http,
        "_send_request",
        capture_request,
    )
    monkeypatch.setattr(
        integration_fmi_client,
        "_parse_forecast_response",
        lambda body, request_type: parsed,
    )

    integration_fmi_client._request_by_coordinates(  # noqa: SLF001
        models.RequestType.FORECAST,
        60.17,
        24.94,
        60,
        48,
    )

    assert captured == [{"parameters": expected}]


def test_client_adapter_rejects_non_string_parameter_contract(monkeypatch) -> None:
    """Fail before an HTTP request when the installed client's parameter shape drifts."""
    send_request = Mock()
    monkeypatch.setattr(
        integration_fmi_client.upstream.http,
        "_create_params",
        lambda *args, **kwargs: {"parameters": None},
    )
    monkeypatch.setattr(integration_fmi_client.upstream.http, "_send_request", send_request)

    with pytest.raises(TypeError, match="non-string WFS parameters"):
        integration_fmi_client._request_by_coordinates(  # noqa: SLF001
            models.RequestType.FORECAST,
            60.17,
            24.94,
            60,
            48,
        )

    send_request.assert_not_called()


def test_hourly_gust_parser_ignores_absent_and_misaligned_fields() -> None:
    """Return no gusts when the optional field or its aligned value is unavailable."""
    no_hourly_field = f"""
        <root xmlns:swe="{integration_fmi_client.SWE_NAMESPACE}">
          <swe:field name="WindGust" />
        </root>
    """
    missing_aligned_value = f"""
        <root xmlns:gml="{integration_fmi_client.GML_NAMESPACE}"
              xmlns:gmlcov="{integration_fmi_client.GMLCOV_NAMESPACE}"
              xmlns:swe="{integration_fmi_client.SWE_NAMESPACE}">
          <swe:field name="WindGust" />
          <swe:field name="HourlyMaximumGust" />
          <gmlcov:positions>60.17 24.94</gmlcov:positions>
          <gml:doubleOrNilReasonTupleList>7.0</gml:doubleOrNilReasonTupleList>
        </root>
    """

    assert integration_fmi_client._hourly_gusts_by_time(no_hourly_field) == {}  # noqa: SLF001
    assert integration_fmi_client._hourly_gusts_by_time(missing_aligned_value) == {}  # noqa: SLF001


async def test_client_adapter_preserves_weather_and_forecast_timesteps(monkeypatch) -> None:
    """Keep the upstream ten-minute current query and hourly forecast query."""
    calls: list[tuple[object, ...]] = []
    worker_threads: list[int] = []
    loop_thread = threading.get_ident()
    parsed = forecast_from_fixture("forecast_normal.json")

    def capture_request(*args):
        calls.append(args)
        worker_threads.append(threading.get_ident())
        return parsed

    monkeypatch.setattr(
        integration_fmi_client,
        "_request_by_coordinates",
        protect_loop(capture_request, loop_thread),
    )

    current = await integration_fmi_client.async_weather_by_coordinates(60.17, 24.94)
    forecast = await integration_fmi_client.async_forecast_by_coordinates(60.17, 24.94, 1, 48)

    assert current is not None
    assert forecast is parsed
    assert calls == [
        (models.RequestType.WEATHER, 60.17, 24.94, 10, 4),
        (models.RequestType.FORECAST, 60.17, 24.94, 60, 48),
    ]
    assert all(thread_id != loop_thread for thread_id in worker_threads)


async def test_client_adapter_returns_none_for_empty_current_forecast(monkeypatch) -> None:
    """Keep the upstream empty-current contract without indexing an absent sample."""
    empty = models.Forecast("Helsinki", 60.17, 24.94, [])
    monkeypatch.setattr(integration_fmi_client, "_request_by_coordinates", lambda *args: empty)

    assert await integration_fmi_client.async_weather_by_coordinates(60.17, 24.94) is None


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
