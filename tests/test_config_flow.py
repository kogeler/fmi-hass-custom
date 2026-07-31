"""Config-flow and location-reconfiguration regressions for FMI issue #115."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from fmi_weather_client.errors import ClientError
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.fmi import FMIDataUpdateCoordinator, async_migrate_entry
from custom_components.fmi import fmi as fmi_client
from custom_components.fmi.const import CONF_ENTITY_IDENTITY, COORDINATOR, DOMAIN
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


def _patch_location_sources(monkeypatch) -> dict[str, AsyncMock]:
    helsinki, helsinki_forecast, tampere, tampere_forecast = _locations()
    weather_by_coordinates = {
        (60.17, 24.94): helsinki,
        (61.5, 23.76): tampere,
    }
    forecast_by_coordinates = {
        (60.17, 24.94): helsinki_forecast,
        (61.5, 23.76): tampere_forecast,
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
        "_FMIDataUpdateCoordinator__update_mareo_data",
        lambda self: None,
    )
    return mocks


async def _start_reconfigure(hass: HomeAssistant, entry_id: str):
    return await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry_id,
        },
    )


async def test_user_flow_creates_coordinate_independent_identity(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """Give fresh entries a stable identity that is not their current coordinates."""
    _patch_location_sources(monkeypatch)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_NAME: "FMI",
            CONF_LATITUDE: 60.17,
            CONF_LONGITUDE: 24.94,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Helsinki"
    entry = result["result"]
    assert entry.version == 2
    assert entry.unique_id is not None
    assert entry.unique_id == entry.data[CONF_ENTITY_IDENTITY]
    assert "60.17" not in entry.unique_id
    assert entry.data[CONF_LATITUDE] == 60.17
    assert entry.data[CONF_LONGITUDE] == 24.94


async def test_issue_115_reconfigure_updates_only_mutable_location(
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
    assert result["step_id"] == "reconfigure"
    assert result["data_schema"]({}) == {
        CONF_LATITUDE: 60.17,
        CONF_LONGITUDE: 24.94,
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_LATITUDE: 61.5,
            CONF_LONGITUDE: 23.76,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.title == "Tampere"
    assert entry.unique_id == old_unique_id
    assert entry.data[CONF_ENTITY_IDENTITY] == old_identity
    assert entry.data[CONF_LATITUDE] == 61.5
    assert entry.data[CONF_LONGITUDE] == 23.76


@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [
        (91.0, 24.94),
        (-91.0, 24.94),
        (60.17, 181.0),
        (60.17, -181.0),
    ],
)
async def test_reconfigure_rejects_invalid_coordinates(
    hass: HomeAssistant,
    latitude: float,
    longitude: float,
) -> None:
    """Apply Home Assistant coordinate bounds before any FMI request."""
    entry = _entry(hass)
    result = await _start_reconfigure(hass, entry.entry_id)

    with pytest.raises(InvalidData) as error:
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_LATITUDE: latitude,
                CONF_LONGITUDE: longitude,
            },
        )

    assert error.value.schema_errors
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
        {
            CONF_LATITUDE: 61.5,
            CONF_LONGITUDE: 23.76,
        },
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
        {
            CONF_LATITUDE: 61.5,
            CONF_LONGITUDE: 23.76,
        },
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
        {
            CONF_LATITUDE: 61.5,
            CONF_LONGITUDE: 23.76,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    validate.assert_not_awaited()
    assert entry.data[CONF_LATITUDE] == 60.17
    assert entry.data[CONF_LONGITUDE] == 24.94


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
        {
            CONF_LATITUDE: 61.5,
            CONF_LONGITUDE: 23.76,
        },
    )
    assert result["type"] is FlowResultType.ABORT
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
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
