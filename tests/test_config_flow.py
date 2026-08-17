# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Config-flow and location-reconfiguration regressions for FMI."""

from __future__ import annotations

import asyncio
import math
from typing import Any
from unittest.mock import AsyncMock
from xml.parsers.expat import ExpatError

import pytest
import voluptuous as vol
from fmi_weather_client.errors import ClientError, ServerError
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import LocationSelector
from pytest_homeassistant_custom_component.common import MockConfigEntry
from requests.exceptions import RequestException

from custom_components.fmi import FMIDataUpdateCoordinator, async_migrate_entry
from custom_components.fmi import fmi as fmi_client
from custom_components.fmi.const import (
    CONF_ENTITY_IDENTITY,
    CONF_LIGHTNING_MAX_AGE,
    CONF_PLACE_QUERY,
    DOMAIN,
    LIGHTNING_MAX_AGE_DEFAULT_MINUTES,
    LIGHTNING_MAX_AGE_MAX_MINUTES,
)
from tests.helpers.fmi import forecast_from_fixture, weather_from_fixture


def _entry(
    hass: HomeAssistant,
    *,
    latitude: float = 60.17,
    longitude: float = 24.94,
    title: str = "Helsinki",
    entry_id: str | None = None,
    unique_id: str | None = None,
    version: int = 2,
    entity_identity: str = "60.17:24.94",
) -> MockConfigEntry:
    data: dict[str, Any] = {
        CONF_NAME: "FMI",
        CONF_LATITUDE: latitude,
        CONF_LONGITUDE: longitude,
    }
    if version >= 2:
        data[CONF_ENTITY_IDENTITY] = entity_identity
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=title,
        entry_id=entry_id,
        unique_id=unique_id or f"fmi:{entry_id or 'stable-test-entry'}",
        data=data,
        version=version,
    )
    entry.add_to_hass(hass)
    return entry


def _locations():
    helsinki = weather_from_fixture("forecast_normal.json")
    helsinki_forecast = forecast_from_fixture("forecast_normal.json")
    assert helsinki is not None
    tampere = helsinki._replace(place="Tampere", lat=61.5, lon=23.76)
    tampere_forecast = helsinki_forecast._replace(place="Tampere", lat=61.5, lon=23.76)
    return helsinki, helsinki_forecast, tampere, tampere_forecast


def _map_input(
    latitude: object,
    longitude: object,
    *,
    name: str | None = None,
) -> dict[str, object]:
    """Build transient standard-map input without resembling stored entry data."""
    data: dict[str, object] = {
        CONF_LOCATION: {
            CONF_LATITUDE: latitude,
            CONF_LONGITUDE: longitude,
        }
    }
    if name is not None:
        data[CONF_NAME] = name
    return data


async def _start_user_menu(hass: HomeAssistant):
    return await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )


async def _choose_menu_step(hass: HomeAssistant, result, step_id: str):
    return await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": step_id},
    )


async def _start_user_map(hass: HomeAssistant):
    return await _choose_menu_step(hass, await _start_user_menu(hass), "map")


async def _start_user_place(hass: HomeAssistant):
    return await _choose_menu_step(hass, await _start_user_menu(hass), "place")


async def _submit_user_map(
    hass: HomeAssistant,
    latitude: float,
    longitude: float,
):
    result = await _start_user_map(hass)
    return await hass.config_entries.flow.async_configure(
        result["flow_id"],
        _map_input(latitude, longitude, name="FMI"),
    )


async def _start_reconfigure_menu(hass: HomeAssistant, entry_id: str):
    return await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry_id,
        },
    )


async def _start_reconfigure(hass: HomeAssistant, entry_id: str):
    return await _choose_menu_step(
        hass,
        await _start_reconfigure_menu(hass, entry_id),
        "map",
    )


async def _start_reconfigure_place(hass: HomeAssistant, entry_id: str):
    return await _choose_menu_step(
        hass,
        await _start_reconfigure_menu(hass, entry_id),
        "place",
    )


async def test_options_flow_defaults_and_stores_lightning_max_age(
    hass: HomeAssistant,
) -> None:
    """Give existing entries a lazy-compatible 24-hour default and validate the range."""
    entry = _entry(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    schema = result["data_schema"]
    assert schema is not None
    defaults = schema({})
    assert defaults[CONF_LIGHTNING_MAX_AGE] == LIGHTNING_MAX_AGE_DEFAULT_MINUTES

    with pytest.raises(vol.Invalid):
        schema(
            {
                **defaults,
                CONF_LIGHTNING_MAX_AGE: LIGHTNING_MAX_AGE_MAX_MINUTES + 1,
            }
        )

    defaults[CONF_LIGHTNING_MAX_AGE] = 60
    result = await hass.config_entries.options.async_configure(result["flow_id"], defaults)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_LIGHTNING_MAX_AGE] == 60


async def test_user_flow_form_uses_home_assistant_location_defaults(
    hass: HomeAssistant,
) -> None:
    """Expose the complete translated setup form through the public flow API."""
    result = await _start_user_menu(hass)

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"
    assert result["menu_options"] == ["map", "place"]

    result = await _choose_menu_step(hass, result, "map")

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "map"
    assert result["errors"] == {}
    schema = result["data_schema"]
    assert schema is not None
    assert schema({}) == {
        CONF_NAME: "FMI",
        CONF_LOCATION: {
            CONF_LATITUDE: hass.config.latitude,
            CONF_LONGITUDE: hass.config.longitude,
        },
    }
    assert CONF_LATITUDE not in schema.schema
    assert CONF_LONGITUDE not in schema.schema
    location_selector = next(
        validator for marker, validator in schema.schema.items() if marker.schema == CONF_LOCATION
    )
    assert isinstance(location_selector, LocationSelector)
    assert location_selector.selector_type == "location"


async def test_user_flow_accepts_home_assistant_location_default(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Create an entry by accepting the standard map's initial Home marker."""
    weather = weather_from_fixture("forecast_normal.json")
    forecast = forecast_from_fixture("forecast_normal.json")
    assert weather is not None
    validate = AsyncMock(return_value=weather)
    monkeypatch.setattr(fmi_client, "async_weather_by_coordinates", validate)
    monkeypatch.setattr(
        fmi_client,
        "async_forecast_by_coordinates",
        AsyncMock(return_value=forecast),
    )
    monkeypatch.setattr(
        fmi_client,
        "async_observation_by_place",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        FMIDataUpdateCoordinator,
        "_FMIDataUpdateCoordinator__async_update_mareo_data",
        AsyncMock(return_value=None),
    )
    result = await _start_user_map(hass)
    schema = result["data_schema"]
    assert schema is not None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        schema({}),
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].data[CONF_LATITUDE] == hass.config.latitude
    assert result["result"].data[CONF_LONGITUDE] == hass.config.longitude
    assert CONF_LOCATION not in result["result"].data
    assert validate.await_args_list[0].args == (
        hass.config.latitude,
        hass.config.longitude,
    )


@pytest.mark.parametrize(
    ("latitude", "longitude", "expected_title"),
    [
        (60.17, 24.94, "Helsinki"),
        (61.5, 23.76, "Tampere"),
    ],
    ids=["confirm-resolved", "adjust-before-confirm"],
)
async def test_user_place_search_confirms_or_adjusts_on_map(
    hass: HomeAssistant,
    monkeypatch,
    latitude: float,
    longitude: float,
    expected_title: str,
) -> None:
    """Resolve through FMI but let the common final point determine persisted data."""
    _patch_location_sources(monkeypatch)
    resolve = AsyncMock(return_value=fmi_client.PlaceResolution("Helsinki", 60.17, 24.94))
    monkeypatch.setattr(fmi_client, "async_resolve_place", resolve)
    result = await _start_user_place(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "place"
    schema = result["data_schema"]
    assert schema is not None
    assert schema({}) == {CONF_NAME: "FMI", CONF_PLACE_QUERY: ""}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NAME: "My forecast", CONF_PLACE_QUERY: " Helsinki "},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "place_confirm"
    assert result["description_placeholders"] == {"place": "Helsinki"}
    schema = result["data_schema"]
    assert schema is not None
    assert schema({}) == {CONF_LOCATION: {CONF_LATITUDE: 60.17, CONF_LONGITUDE: 24.94}}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        _map_input(latitude, longitude),
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == expected_title
    entry = result["result"]
    assert entry.data[CONF_NAME] == "My forecast"
    assert entry.data[CONF_LATITUDE] == latitude
    assert entry.data[CONF_LONGITUDE] == longitude
    assert CONF_PLACE_QUERY not in entry.data
    assert CONF_LOCATION not in entry.data
    resolve.assert_awaited_once_with("Helsinki")


async def test_reconfigure_place_search_updates_only_mutable_location(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Offer the same search path while retaining the selected entry's identity."""
    _patch_location_sources(monkeypatch)
    monkeypatch.setattr(
        fmi_client,
        "async_resolve_place",
        AsyncMock(return_value=fmi_client.PlaceResolution("Tampere", 61.5, 23.76)),
    )
    entry = _entry(hass)
    original = (entry.unique_id, entry.data[CONF_ENTITY_IDENTITY], entry.data[CONF_NAME])
    menu = await _start_reconfigure_menu(hass, entry.entry_id)
    assert menu["type"] is FlowResultType.MENU
    assert menu["step_id"] == "reconfigure"
    assert menu["menu_options"] == ["map", "place"]
    result = await _choose_menu_step(hass, menu, "place")
    defaults = result["data_schema"]({})
    assert defaults == {CONF_PLACE_QUERY: ""}
    assert CONF_NAME not in defaults

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PLACE_QUERY: "Tampere"},
    )
    assert result["step_id"] == "place_confirm"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        _map_input(61.5, 23.76),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.title == "Tampere"
    assert (entry.unique_id, entry.data[CONF_ENTITY_IDENTITY], entry.data[CONF_NAME]) == original
    assert entry.data[CONF_LATITUDE] == 61.5
    assert entry.data[CONF_LONGITUDE] == 23.76


@pytest.mark.parametrize(
    ("resolution", "expected_error"),
    [
        (None, "place_not_found"),
        (ClientError(400, "Synthetic unknown place"), "place_not_found"),
        (ServerError(503, "Synthetic service failure"), "cannot_connect"),
        (RequestException("Synthetic transport failure"), "cannot_connect"),
        (AttributeError("Synthetic malformed attribute"), "unknown"),
        (ExpatError("Synthetic malformed XML"), "unknown"),
        (IndexError("Synthetic malformed shape"), "unknown"),
        (KeyError("Synthetic malformed key"), "unknown"),
        (OverflowError("Synthetic malformed number"), "unknown"),
        (SyntaxError("Synthetic malformed syntax"), "unknown"),
        (TypeError("Synthetic malformed type"), "unknown"),
        (ValueError("Synthetic malformed result"), "unknown"),
    ],
)
async def test_user_place_search_translates_failures_without_writes(
    hass: HomeAssistant,
    monkeypatch,
    resolution: object,
    expected_error: str,
) -> None:
    """Keep lookup failures retryable and free of partial config entries."""
    resolve = (
        AsyncMock(side_effect=resolution)
        if isinstance(resolution, Exception)
        else AsyncMock(return_value=resolution)
    )
    monkeypatch.setattr(fmi_client, "async_resolve_place", resolve)
    result = await _start_user_place(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NAME: "FMI", CONF_PLACE_QUERY: "Missing"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "place"
    assert result["errors"] == {"base": expected_error}
    assert not hass.config_entries.async_entries(DOMAIN)


async def test_place_search_rejects_invalid_query_before_fmi(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Require the transient search string before external I/O."""
    resolve = AsyncMock()
    monkeypatch.setattr(fmi_client, "async_resolve_place", resolve)
    result = await _start_user_place(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NAME: "FMI", CONF_PLACE_QUERY: "   "},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_PLACE_QUERY: "place_required"}
    resolve.assert_not_awaited()


async def test_place_confirmation_rejects_duplicate_before_validation(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Apply the common final duplicate boundary to a resolved search result."""
    validate = AsyncMock()
    monkeypatch.setattr(fmi_client, "async_weather_by_coordinates", validate)
    monkeypatch.setattr(
        fmi_client,
        "async_resolve_place",
        AsyncMock(return_value=fmi_client.PlaceResolution("Helsinki", 60.17, 24.94)),
    )
    _entry(hass)
    result = await _start_user_place(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NAME: "FMI", CONF_PLACE_QUERY: "Helsinki"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        _map_input(60.17, 24.94),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    validate.assert_not_awaited()
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.parametrize(
    ("validation_result", "expected_error"),
    [(None, "cannot_connect"), (ValueError("Malformed final point"), "unknown")],
)
async def test_place_confirmation_failure_keeps_transient_form_without_entry(
    hass: HomeAssistant,
    monkeypatch,
    validation_result: object,
    expected_error: str,
) -> None:
    """Do not write after search when final coordinate validation fails."""
    validate = (
        AsyncMock(side_effect=validation_result)
        if isinstance(validation_result, Exception)
        else AsyncMock(return_value=validation_result)
    )
    monkeypatch.setattr(fmi_client, "async_weather_by_coordinates", validate)
    monkeypatch.setattr(
        fmi_client,
        "async_resolve_place",
        AsyncMock(return_value=fmi_client.PlaceResolution("Helsinki", 60.17, 24.94)),
    )
    result = await _start_user_place(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NAME: "FMI", CONF_PLACE_QUERY: "Helsinki"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        _map_input(60.17, 24.94),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "place_confirm"
    assert result["errors"] == {"base": expected_error}
    assert result["description_placeholders"] == {"place": "Helsinki"}
    assert not hass.config_entries.async_entries(DOMAIN)


async def test_place_search_and_confirmation_can_retry_in_same_flow(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Replace failed transient candidates and retry final validation without writes."""
    helsinki, helsinki_forecast, _, _ = _locations()
    resolve = AsyncMock(side_effect=[None, fmi_client.PlaceResolution("Helsinki", 60.17, 24.94)])
    weather = AsyncMock(side_effect=[None, helsinki, helsinki])
    monkeypatch.setattr(fmi_client, "async_resolve_place", resolve)
    monkeypatch.setattr(fmi_client, "async_weather_by_coordinates", weather)
    monkeypatch.setattr(
        fmi_client,
        "async_forecast_by_coordinates",
        AsyncMock(return_value=helsinki_forecast),
    )
    monkeypatch.setattr(
        fmi_client,
        "async_observation_by_place",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        FMIDataUpdateCoordinator,
        "_FMIDataUpdateCoordinator__async_update_mareo_data",
        AsyncMock(return_value=None),
    )
    result = await _start_user_place(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NAME: "FMI", CONF_PLACE_QUERY: "Missing"},
    )
    assert result["errors"] == {"base": "place_not_found"}
    assert not hass.config_entries.async_entries(DOMAIN)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NAME: "FMI", CONF_PLACE_QUERY: "Helsinki"},
    )
    assert result["step_id"] == "place_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        _map_input(60.17, 24.94),
    )
    assert result["errors"] == {"base": "cannot_connect"}
    assert not hass.config_entries.async_entries(DOMAIN)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        _map_input(60.17, 24.94),
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert resolve.await_args_list[0].args == ("Missing",)
    assert resolve.await_args_list[1].args == ("Helsinki",)


async def test_concurrent_place_confirmations_create_only_one_entry(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Serialize identical final points across genuinely overlapping setup flows."""
    helsinki, _, _, _ = _locations()
    _patch_location_sources(monkeypatch)
    release_validation = asyncio.Event()
    validation_started = asyncio.Event()
    validation_calls = 0

    async def validate(_latitude: float, _longitude: float):
        nonlocal validation_calls
        validation_calls += 1
        validation_started.set()
        await release_validation.wait()
        return helsinki

    monkeypatch.setattr(fmi_client, "async_weather_by_coordinates", validate)
    monkeypatch.setattr(
        fmi_client,
        "async_resolve_place",
        AsyncMock(return_value=fmi_client.PlaceResolution("Helsinki", 60.17, 24.94)),
    )
    confirmations = []
    for name in ("First", "Second"):
        result = await _start_user_place(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_NAME: name, CONF_PLACE_QUERY: "Helsinki"},
        )
        assert result["step_id"] == "place_confirm"
        confirmations.append(result)

    first = asyncio.create_task(
        hass.config_entries.flow.async_configure(
            confirmations[0]["flow_id"],
            _map_input(60.17, 24.94),
        )
    )
    await validation_started.wait()
    second = asyncio.create_task(
        hass.config_entries.flow.async_configure(
            confirmations[1]["flow_id"],
            _map_input(60.17, 24.94),
        )
    )
    await asyncio.sleep(0)
    release_validation.set()
    results = await asyncio.gather(first, second)

    assert [result["type"] for result in results].count(FlowResultType.CREATE_ENTRY) == 1
    assert [result["type"] for result in results].count(FlowResultType.ABORT) == 1
    aborted = next(result for result in results if result["type"] is FlowResultType.ABORT)
    assert aborted["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert validation_calls == 3  # two overlapping validations plus created-entry setup


async def test_concurrent_distinct_place_confirmations_create_independent_entries(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Let overlapping flows persist distinct final points without shared state."""
    _patch_location_sources(monkeypatch)

    async def resolve(place: str) -> fmi_client.PlaceResolution:
        if place == "Helsinki":
            return fmi_client.PlaceResolution(place, 60.17, 24.94)
        return fmi_client.PlaceResolution(place, 61.5, 23.76)

    monkeypatch.setattr(fmi_client, "async_resolve_place", resolve)
    confirmations = []
    for place in ("Helsinki", "Tampere"):
        result = await _start_user_place(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_NAME: place, CONF_PLACE_QUERY: place},
        )
        confirmations.append(result)

    results = await asyncio.gather(
        *(
            hass.config_entries.flow.async_configure(
                result["flow_id"],
                _map_input(*coordinates),
            )
            for result, coordinates in zip(
                confirmations,
                ((60.17, 24.94), (61.5, 23.76)),
                strict=True,
            )
        )
    )

    assert all(result["type"] is FlowResultType.CREATE_ENTRY for result in results)
    entries = hass.config_entries.async_entries(DOMAIN)
    locations = {
        (entry.title, entry.data[CONF_LATITUDE], entry.data[CONF_LONGITUDE]) for entry in entries
    }
    assert locations == {
        ("Helsinki", 60.17, 24.94),
        ("Tampere", 61.5, 23.76),
    }
    assert len({entry.data[CONF_ENTITY_IDENTITY] for entry in entries}) == 2


async def test_abandoned_place_confirmation_can_restart_without_stale_state(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Model frontend Back/cancel as abort plus a fresh independent map flow."""
    _patch_location_sources(monkeypatch)
    monkeypatch.setattr(
        fmi_client,
        "async_resolve_place",
        AsyncMock(return_value=fmi_client.PlaceResolution("Tampere", 61.5, 23.76)),
    )
    result = await _start_user_place(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NAME: "Abandoned", CONF_PLACE_QUERY: "Tampere"},
    )
    assert result["step_id"] == "place_confirm"

    hass.config_entries.flow.async_abort(result["flow_id"])

    assert not hass.config_entries.async_entries(DOMAIN)
    result = await _submit_user_map(hass, 60.17, 24.94)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Helsinki"
    assert result["result"].data[CONF_NAME] == "FMI"


async def test_reconfigure_place_confirmation_cancel_preserves_entry(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Discard a resolved candidate without mutating the selected entry."""
    monkeypatch.setattr(
        fmi_client,
        "async_resolve_place",
        AsyncMock(return_value=fmi_client.PlaceResolution("Tampere", 61.5, 23.76)),
    )
    entry = _entry(hass)
    original = (dict(entry.data), entry.title, entry.unique_id, entry.version)
    result = await _start_reconfigure_place(hass, entry.entry_id)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PLACE_QUERY: "Tampere"},
    )
    assert result["step_id"] == "place_confirm"

    hass.config_entries.flow.async_abort(result["flow_id"])

    assert (dict(entry.data), entry.title, entry.unique_id, entry.version) == original


@pytest.mark.parametrize(
    ("validation_result", "expected_error"),
    [
        (None, "cannot_connect"),
        (ClientError(400, "Synthetic client failure"), "cannot_connect"),
        (ServerError(503, "Synthetic service failure"), "cannot_connect"),
        (RequestException("Synthetic transport failure"), "cannot_connect"),
        (AttributeError("Synthetic malformed attribute"), "unknown"),
        (ExpatError("Synthetic malformed XML"), "unknown"),
        (IndexError("Synthetic malformed shape"), "unknown"),
        (KeyError("Synthetic malformed key"), "unknown"),
        (OverflowError("Synthetic malformed number"), "unknown"),
        (SyntaxError("Synthetic malformed syntax"), "unknown"),
        (TypeError("Synthetic malformed type"), "unknown"),
        (ValueError("Synthetic malformed response"), "unknown"),
    ],
)
async def test_user_flow_translates_validation_failures(
    hass: HomeAssistant,
    monkeypatch,
    validation_result: object,
    expected_error: str,
) -> None:
    """Return stable UI error keys for empty, transport, and malformed FMI responses."""
    validate = (
        AsyncMock(side_effect=validation_result)
        if isinstance(validation_result, Exception)
        else AsyncMock(return_value=validation_result)
    )
    monkeypatch.setattr(fmi_client, "async_weather_by_coordinates", validate)

    result = await _submit_user_map(hass, 60.17, 24.94)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "map"
    assert result["errors"] == {"base": expected_error}
    assert not hass.config_entries.async_entries(DOMAIN)


async def test_user_flow_rejects_blank_canonical_place(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Treat a coordinate result without a usable canonical title as malformed."""
    weather = weather_from_fixture("forecast_normal.json")
    assert weather is not None
    monkeypatch.setattr(
        fmi_client,
        "async_weather_by_coordinates",
        AsyncMock(return_value=weather._replace(place="   ")),
    )

    result = await _submit_user_map(hass, 60.17, 24.94)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "map"
    assert result["errors"] == {"base": "unknown"}
    assert not hass.config_entries.async_entries(DOMAIN)


async def test_user_flow_rejects_existing_location_before_validation(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Abort a duplicate setup without making an unnecessary FMI request."""
    validate = AsyncMock()
    monkeypatch.setattr(fmi_client, "async_weather_by_coordinates", validate)
    _entry(hass)

    result = await _submit_user_map(hass, 60.17, 24.94)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    validate.assert_not_awaited()


async def test_user_flow_rechecks_duplicate_after_validation(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Close the race where another flow stores the location during validation."""
    weather = weather_from_fixture("forecast_normal.json")
    assert weather is not None

    async def validate_and_add_duplicate(_latitude: float, _longitude: float):
        _entry(
            hass,
            entry_id="concurrent-entry",
            unique_id="fmi:concurrent-entry",
            entity_identity="concurrent-identity",
        )
        return weather

    monkeypatch.setattr(
        fmi_client,
        "async_weather_by_coordinates",
        validate_and_add_duplicate,
    )

    result = await _submit_user_map(hass, 60.17, 24.94)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


def _patch_location_sources(monkeypatch) -> dict[str, AsyncMock]:
    helsinki, helsinki_forecast, tampere, tampere_forecast = _locations()
    oulu = helsinki._replace(place="Oulu", lat=65.01, lon=25.47)
    oulu_forecast = helsinki_forecast._replace(place="Oulu", lat=65.01, lon=25.47)
    weather_by_coordinates = {
        (60.17, 24.94): helsinki,
        (61.5, 23.76): tampere,
        (65.01, 25.47): oulu,
    }
    forecast_by_coordinates = {
        (60.17, 24.94): helsinki_forecast,
        (61.5, 23.76): tampere_forecast,
        (65.01, 25.47): oulu_forecast,
    }
    mocks = {
        "weather": AsyncMock(
            side_effect=lambda latitude, longitude: weather_by_coordinates[(latitude, longitude)]
        ),
        "forecast": AsyncMock(
            side_effect=lambda latitude, longitude, *_: forecast_by_coordinates[
                (latitude, longitude)
            ]
        ),
        "place_observation": AsyncMock(return_value=None),
    }
    monkeypatch.setattr(
        fmi_client,
        "async_weather_by_coordinates",
        mocks["weather"],
    )
    monkeypatch.setattr(
        fmi_client,
        "async_forecast_by_coordinates",
        mocks["forecast"],
    )
    monkeypatch.setattr(
        fmi_client,
        "async_observation_by_place",
        mocks["place_observation"],
    )
    monkeypatch.setattr(
        FMIDataUpdateCoordinator,
        "_FMIDataUpdateCoordinator__async_update_mareo_data",
        AsyncMock(return_value=None),
    )
    return mocks


async def test_user_flow_creates_coordinate_independent_identity(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Give fresh entries a stable identity that is not their current coordinates."""
    _patch_location_sources(monkeypatch)

    result = await _submit_user_map(hass, 60.17, 24.94)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Helsinki"
    entry = result["result"]
    assert entry.version == 2
    assert entry.unique_id is not None
    assert entry.unique_id == entry.data[CONF_ENTITY_IDENTITY]
    assert "60.17" not in entry.unique_id
    assert entry.data[CONF_LATITUDE] == 60.17
    assert entry.data[CONF_LONGITUDE] == 24.94
    assert entry.data[CONF_NAME] == "FMI"
    assert CONF_LOCATION not in entry.data


async def test_reconfigure_updates_only_mutable_location(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Change coordinates/title while preserving stable config and entity identity."""
    _patch_location_sources(monkeypatch)
    entry = _entry(hass)
    old_unique_id = entry.unique_id
    old_identity = entry.data[CONF_ENTITY_IDENTITY]

    result = await _start_reconfigure(hass, entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "map"
    assert result["data_schema"]({}) == {
        CONF_LOCATION: {
            CONF_LATITUDE: 60.17,
            CONF_LONGITUDE: 24.94,
        },
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        _map_input(61.5, 23.76),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.title == "Tampere"
    assert entry.unique_id == old_unique_id
    assert entry.data[CONF_ENTITY_IDENTITY] == old_identity
    assert entry.data[CONF_LATITUDE] == 61.5
    assert entry.data[CONF_LONGITUDE] == 23.76


@pytest.mark.parametrize(
    "location",
    [
        {CONF_LATITUDE: 91.0, CONF_LONGITUDE: 24.94},
        {CONF_LATITUDE: -91.0, CONF_LONGITUDE: 24.94},
        {CONF_LATITUDE: 60.17, CONF_LONGITUDE: 181.0},
        {CONF_LATITUDE: 60.17, CONF_LONGITUDE: -181.0},
        {CONF_LATITUDE: math.nan, CONF_LONGITUDE: 24.94},
        {CONF_LATITUDE: math.inf, CONF_LONGITUDE: 24.94},
        {CONF_LATITUDE: 60.17, CONF_LONGITUDE: -math.inf},
        {CONF_LATITUDE: True, CONF_LONGITUDE: 24.94},
        {CONF_LATITUDE: 60.17, CONF_LONGITUDE: False},
        {CONF_LONGITUDE: 24.94},
        {CONF_LATITUDE: 60.17},
    ],
)
async def test_reconfigure_rejects_invalid_map_locations(
    hass: HomeAssistant,
    monkeypatch,
    location: dict[str, object],
) -> None:
    """Reject malformed, non-finite, boolean, and out-of-range map input."""
    validate = AsyncMock()
    monkeypatch.setattr(fmi_client, "async_weather_by_coordinates", validate)
    entry = _entry(hass)
    result = await _start_reconfigure(hass, entry.entry_id)

    with pytest.raises(InvalidData) as error:
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_LOCATION: location},
        )

    assert error.value.schema_errors
    validate.assert_not_awaited()
    assert entry.data[CONF_LATITUDE] == 60.17
    assert entry.data[CONF_LONGITUDE] == 24.94


async def test_reconfigure_validation_failure_preserves_entry(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Leave every stored value untouched when FMI rejects the new location."""
    error = ClientError(400, "Synthetic invalid location")
    validate = AsyncMock(side_effect=error)
    monkeypatch.setattr(fmi_client, "async_weather_by_coordinates", validate)
    entry = _entry(hass)
    original = (dict(entry.data), entry.title, entry.unique_id, entry.version)
    result = await _start_reconfigure(hass, entry.entry_id)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        _map_input(61.5, 23.76),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert (dict(entry.data), entry.title, entry.unique_id, entry.version) == original


async def test_reconfigure_unexpected_response_preserves_entry(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Translate a malformed FMI response without storing proposed coordinates."""
    monkeypatch.setattr(
        fmi_client,
        "async_weather_by_coordinates",
        AsyncMock(side_effect=ValueError("Synthetic malformed response")),
    )
    entry = _entry(hass)
    original_data = dict(entry.data)
    result = await _start_reconfigure(hass, entry.entry_id)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        _map_input(61.5, 23.76),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}
    assert dict(entry.data) == original_data


async def test_reconfigure_rejects_duplicate_location_without_validation(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Do not let two entries converge on the same configured coordinates."""
    validate = AsyncMock()
    monkeypatch.setattr(fmi_client, "async_weather_by_coordinates", validate)
    entry = _entry(hass)
    _entry(
        hass,
        latitude=61.5,
        longitude=23.76,
        title="Tampere",
        entry_id="other-entry",
        unique_id="fmi:other-entry",
        entity_identity="other-stable-identity",
    )
    result = await _start_reconfigure(hass, entry.entry_id)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        _map_input(61.5, 23.76),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    validate.assert_not_awaited()
    assert entry.data[CONF_LATITUDE] == 60.17
    assert entry.data[CONF_LONGITUDE] == 24.94


async def test_reconfigure_rechecks_duplicate_after_validation(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Keep a concurrent flow from moving another entry onto the same point."""
    _, _, tampere, _ = _locations()
    entry = _entry(hass)
    original = (dict(entry.data), entry.title)

    async def validate_and_add_duplicate(_latitude: float, _longitude: float):
        _entry(
            hass,
            latitude=61.5,
            longitude=23.76,
            title="Tampere",
            entry_id="concurrent-entry",
            unique_id="fmi:concurrent-entry",
            entity_identity="concurrent-identity",
        )
        return tampere

    monkeypatch.setattr(
        fmi_client,
        "async_weather_by_coordinates",
        validate_and_add_duplicate,
    )
    result = await _start_reconfigure(hass, entry.entry_id)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        _map_input(61.5, 23.76),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert (dict(entry.data), entry.title) == original


async def test_reconfigure_cancellation_preserves_entry(hass: HomeAssistant) -> None:
    """Discard a reconfigure form without mutating or reloading its entry."""
    entry = _entry(hass)
    original = (dict(entry.data), entry.title, entry.unique_id, entry.version)
    result = await _start_reconfigure(hass, entry.entry_id)

    hass.config_entries.flow.async_abort(result["flow_id"])

    assert (dict(entry.data), entry.title, entry.unique_id, entry.version) == original


async def test_v062_migration_preserves_legacy_entity_identity(
    hass: HomeAssistant,
) -> None:
    """Move config identity off coordinates without changing legacy entity IDs."""
    entry = _entry(
        hass,
        version=1,
        unique_id="60.17_24.94",
    )

    assert await async_migrate_entry(hass, entry)

    assert entry.version == 2
    assert entry.unique_id == f"fmi:{entry.entry_id}"
    assert entry.data[CONF_ENTITY_IDENTITY] == "60.17:24.94"


async def test_v062_migration_collision_keeps_safe_legacy_config_id(
    hass: HomeAssistant,
) -> None:
    """Never overwrite another entry's stable config ID during migration."""
    legacy = MockConfigEntry(
        domain=DOMAIN,
        title="Helsinki",
        unique_id="60.17_24.94",
        data={
            CONF_NAME: "FMI",
            CONF_LATITUDE: 60.17,
            CONF_LONGITUDE: 24.94,
        },
        version=1,
    )
    occupied = MockConfigEntry(
        domain=DOMAIN,
        title="Occupied identity",
        unique_id=f"fmi:{legacy.entry_id}",
        data={
            CONF_NAME: "FMI",
            CONF_LATITUDE: 62.0,
            CONF_LONGITUDE: 25.0,
            CONF_ENTITY_IDENTITY: "occupied-identity",
        },
        version=2,
    )
    occupied.add_to_hass(hass)
    legacy.add_to_hass(hass)

    assert await async_migrate_entry(hass, legacy)

    assert legacy.version == 2
    assert legacy.unique_id == "60.17_24.94"
    assert legacy.data[CONF_ENTITY_IDENTITY] == "60.17:24.94"
    assert occupied.unique_id == f"fmi:{legacy.entry_id}"

    first_result = (dict(legacy.data), legacy.unique_id, legacy.version, legacy.minor_version)
    assert await async_migrate_entry(hass, legacy)
    assert (
        dict(legacy.data),
        legacy.unique_id,
        legacy.version,
        legacy.minor_version,
    ) == first_result


async def test_loaded_reconfigure_preserves_custom_entity_and_loads_new_place(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Reload only the moved entry with new data while automations keep their ID."""
    mocks = _patch_location_sources(monkeypatch)
    entry = _entry(
        hass,
        version=1,
        unique_id="60.17_24.94",
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    registry = er.async_get(hass)
    temperature = registry.async_get("sensor.helsinki_temperature")
    assert temperature is not None
    weather_entity = registry.async_get("weather.helsinki")
    assert weather_entity is not None
    old_registry_id = temperature.id
    old_unique_id = temperature.unique_id
    old_weather_registry_id = weather_entity.id
    old_weather_unique_id = weather_entity.unique_id
    registry.async_update_entity(
        temperature.entity_id,
        new_entity_id="sensor.outdoor_custom_temperature",
    )

    result = await _start_reconfigure(hass, entry.entry_id)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        _map_input(61.5, 23.76),
    )
    assert result["type"] is FlowResultType.ABORT
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    coordinator = entry.runtime_data.coordinator
    assert (coordinator.latitude, coordinator.longitude) == (61.5, 23.76)
    assert coordinator.get_current_place() == "Tampere"
    customized = registry.async_get("sensor.outdoor_custom_temperature")
    assert customized is not None
    assert customized.id == old_registry_id
    assert customized.unique_id == old_unique_id
    assert hass.states.get("sensor.outdoor_custom_temperature") is not None
    weather_after = registry.async_get("weather.helsinki")
    assert weather_after is not None
    assert weather_after.id == old_weather_registry_id
    assert weather_after.unique_id == old_weather_unique_id
    assert registry.async_get("weather.tampere") is None
    weather_state = hass.states.get("weather.helsinki")
    assert weather_state is not None
    assert weather_state.attributes["friendly_name"] == "Tampere"
    assert customized.device_id is not None
    device = dr.async_get(hass).async_get(customized.device_id)
    assert device is not None
    assert device.name == "Tampere"
    assert mocks["weather"].await_count == 3  # initial setup, validation, one reload


async def test_loaded_place_reconfigure_reloads_only_selected_entry(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Keep another loaded location's coordinator and listeners untouched."""
    _patch_location_sources(monkeypatch)
    monkeypatch.setattr(
        fmi_client,
        "async_resolve_place",
        AsyncMock(return_value=fmi_client.PlaceResolution("Oulu", 65.01, 25.47)),
    )
    helsinki = _entry(hass, entry_id="loaded-helsinki")
    tampere = _entry(
        hass,
        latitude=61.5,
        longitude=23.76,
        title="Tampere",
        entry_id="loaded-tampere",
        entity_identity="61.5:23.76",
    )
    for entry in (helsinki, tampere):
        if entry.state is ConfigEntryState.NOT_LOADED:
            assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    old_helsinki_coordinator = helsinki.runtime_data.coordinator
    tampere_coordinator = tampere.runtime_data.coordinator
    tampere_data = dict(tampere.data)
    assert len(helsinki.update_listeners) == 1
    assert len(tampere.update_listeners) == 1

    result = await _start_reconfigure_place(hass, helsinki.entry_id)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PLACE_QUERY: "Oulu"},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        _map_input(65.01, 25.47),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()

    assert helsinki.state is ConfigEntryState.LOADED
    assert helsinki.runtime_data.coordinator is not old_helsinki_coordinator
    assert not old_helsinki_coordinator._listeners
    assert len(helsinki.update_listeners) == 1
    assert tampere.state is ConfigEntryState.LOADED
    assert tampere.runtime_data.coordinator is tampere_coordinator
    assert tampere_coordinator._listeners
    assert len(tampere.update_listeners) == 1
    assert dict(tampere.data) == tampere_data
