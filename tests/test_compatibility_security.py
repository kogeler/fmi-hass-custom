# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Compatibility, diagnostics, and privacy regressions for S14."""

from __future__ import annotations

import logging
from datetime import timedelta
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from fmi_weather_client import models
from fmi_weather_client.errors import ClientError
from homeassistant import config_entries
from homeassistant.components.diagnostics import REDACTED
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.fmi import FMIDataUpdateCoordinator, const, fmi_client, utils


def _entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=const.DOMAIN,
        title="Private place",
        unique_id="60.123456:24.654321",
        data={
            CONF_NAME: "FMI",
            CONF_LATITUDE: 60.123456,
            CONF_LONGITUDE: 24.654321,
            const.CONF_ENTITY_IDENTITY: "60.123456:24.654321",
        },
        options={const.CONF_OBSERVATION_STATION: 101004},
        version=const.CONFIG_ENTRY_VERSION,
    )


def test_coordinator_debug_log_omits_private_coordinates(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Do not reveal a configured home location when integration debug is enabled."""
    entry = _entry()
    caplog.set_level(logging.DEBUG, logger="custom_components.fmi.coordinator")

    FMIDataUpdateCoordinator(hass, cast(Any, SimpleNamespace()), entry)

    assert "60.123456" not in caplog.text
    assert "24.654321" not in caplog.text


def test_external_error_details_do_not_include_payload_or_coordinates() -> None:
    """Availability logs should retain classification without external response text."""
    error = ClientError(400, "invalid location 60.123456,24.654321")

    detail = FMIDataUpdateCoordinator._fmi_error_detail(error)

    assert detail == "HTTP 400"
    assert "60.123456" not in detail
    assert "24.654321" not in detail


def test_upstream_parser_logs_no_response_payload(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Keep a parser failure visible without logging the raw FMI response body."""
    body = "<root><location>60.123456,24.654321</location></root>"
    caplog.set_level(logging.DEBUG, logger="fmi_weather_client.parsers.forecast")

    with pytest.raises((AttributeError, KeyError, TypeError)):
        fmi_client._parse_forecast_response(body, models.RequestType.FORECAST)  # noqa: SLF001

    assert "couldn't parse response body" in caplog.text
    assert "60.123456" not in caplog.text
    assert "24.654321" not in caplog.text


def test_upstream_privacy_filter_is_scoped_and_idempotent() -> None:
    """Drop only known sensitive dependency records and retain useful generic errors."""
    privacy_filter = fmi_client._UpstreamPrivacyFilter()  # noqa: SLF001

    def record(name: str, message: object) -> logging.LogRecord:
        return logging.LogRecord(name, logging.ERROR, __file__, 1, message, (), None)

    assert not privacy_filter.filter(
        record("fmi_weather_client.http", "GET request to %s. Parameters: %s")
    )
    assert privacy_filter.filter(record("another_dependency", "ordinary error"))
    assert not privacy_filter.filter(
        record("fmi_weather_client.parsers.forecast", "Received place: %s (%d, %d)")
    )
    assert not privacy_filter.filter(
        record("fmi_weather_client.parsers.forecast", {"private": "payload"})
    )
    assert not privacy_filter.filter(
        record("fmi_weather_client.parsers.forecast", "  <private>payload</private>")
    )
    assert privacy_filter.filter(
        record("fmi_weather_client.parsers.forecast", "couldn't parse response body:")
    )

    logger_names = ("fmi_weather_client.http", "fmi_weather_client.parsers.forecast")
    before = {name: len(logging.getLogger(name).filters) for name in logger_names}
    fmi_client._install_upstream_privacy_filters()  # noqa: SLF001
    after = {name: len(logging.getLogger(name).filters) for name in logger_names}
    assert after == before


async def test_config_flow_does_not_log_external_validation_payload(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Translate malformed responses without putting their exception text in normal logs."""

    async def invalid_response(*_: object) -> None:
        raise ValueError("response contains 60.123456,24.654321")

    monkeypatch.setattr(fmi_client, "async_weather_by_coordinates", invalid_response)
    caplog.set_level(logging.ERROR, logger="custom_components.fmi")

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "map"},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "FMI",
            CONF_LOCATION: {
                CONF_LATITUDE: 60.123456,
                CONF_LONGITUDE: 24.654321,
            },
        },
    )

    assert result["errors"] == {"base": "unknown"}
    assert "60.123456" not in caplog.text
    assert "24.654321" not in caplog.text


async def test_place_flow_does_not_log_query_or_malformed_result(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Keep transient search text and external result details out of normal logs."""
    private_query = "Private address 60.123456,24.654321"
    monkeypatch.setattr(
        fmi_client,
        "async_resolve_place",
        AsyncMock(side_effect=ValueError(f"malformed result for {private_query}")),
    )
    caplog.set_level(logging.ERROR, logger="custom_components.fmi")
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "place"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NAME: "FMI", const.CONF_PLACE_QUERY: private_query},
    )

    assert result["errors"] == {"base": "unknown"}
    assert private_query not in caplog.text
    assert "60.123456" not in caplog.text
    assert "24.654321" not in caplog.text


async def test_diagnostics_redact_location_and_stable_identity(
    hass: HomeAssistant,
) -> None:
    """Diagnostics expose health metadata but never a precise configured location."""
    from custom_components.fmi import FMIEntryRuntimeData
    from custom_components.fmi.diagnostics import async_get_config_entry_diagnostics

    entry = _entry()
    primary = SimpleNamespace(
        last_update_success=True,
        update_interval=timedelta(minutes=30),
        source_availability={"forecast": True},
    )
    entry.runtime_data = FMIEntryRuntimeData(
        coordinator=cast(Any, primary),
        observation_coordinator=None,
        undo_update_listener=lambda: None,
    )

    result = await async_get_config_entry_diagnostics(hass, cast(Any, entry))

    assert result["entry"]["data"][CONF_LATITUDE] == REDACTED
    assert result["entry"]["data"][CONF_LONGITUDE] == REDACTED
    assert result["entry"]["data"][const.CONF_ENTITY_IDENTITY] == REDACTED
    assert const.CONF_PLACE_QUERY not in result["entry"]["data"]
    assert result["coordinators"]["primary"] == {
        "last_update_success": True,
        "poll_interval_seconds": 1800.0,
        "source_availability": {"forecast": True},
    }
    serialized = repr(result)
    assert "60.123456" not in serialized
    assert "24.654321" not in serialized


def test_source_availability_snapshot_cannot_mutate_coordinator_state() -> None:
    """Keep sanitized diagnostics consumers from changing source health."""
    coordinator = cast(Any, object.__new__(FMIDataUpdateCoordinator))
    coordinator._source_available = {"forecast": True}

    snapshot = coordinator.source_availability
    snapshot["forecast"] = False

    assert coordinator.source_availability == {"forecast": True}


@pytest.mark.parametrize("latitude", [-90.0, 90.0])
def test_lightning_bounding_box_is_valid_at_geographic_poles(latitude: float) -> None:
    """Keep optional FMI bbox coordinates finite and inside WGS84 limits."""
    bbox = utils.get_bounding_box(latitude, 24.94, half_side_in_km=200)

    assert -90 <= bbox.lat_min <= bbox.lat_max <= 90
    assert -180 <= bbox.lon_min <= bbox.lon_max <= 180


def test_lightning_bounding_box_spans_globe_when_crossing_antimeridian() -> None:
    """Avoid an inverted FMI query box when a radius crosses the date line."""
    bbox = utils.get_bounding_box(0.0, 179.0, half_side_in_km=200)

    assert (bbox.lon_min, bbox.lon_max) == (-180.0, 180.0)


@pytest.mark.parametrize(
    ("latitude", "longitude", "half_side"),
    [(91.0, 24.94, 200), (60.17, 181.0, 200), (60.17, 24.94, 0)],
)
def test_lightning_bounding_box_rejects_invalid_inputs(
    latitude: float,
    longitude: float,
    half_side: int,
) -> None:
    """Input validation remains active under optimized Python execution."""
    with pytest.raises(ValueError):
        utils.get_bounding_box(latitude, longitude, half_side)
