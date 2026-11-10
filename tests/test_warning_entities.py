# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Home Assistant warning presentation, availability, identity, and lifecycle evidence."""

import json
from asyncio import CancelledError, Event, create_task
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from aiohttp import ClientConnectionError
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import translation
from homeassistant.helpers.template import Template
from homeassistant.setup import async_setup_component
from pytest_homeassistant.common import async_fire_time_changed

from custom_components.fmi import async_unload_entry, const, warnings_coordinator
from custom_components.fmi.diagnostics import async_get_config_entry_diagnostics
from custom_components.fmi.warnings_client import WarningPayloadError
from tests.helpers.fmi import forecast_from_fixture, weather_from_fixture
from tests.helpers.warnings import SENDER, UPDATED, alert, feed, info
from tests.test_config_flow import _map_input, _start_reconfigure
from tests.test_lifecycle import _configure_options, _entry, _patch_sources


def _state(hass: HomeAssistant, entity_id: str) -> State:
    """Require public HA state rather than assuming an entity loaded."""
    state = hass.states.get(entity_id)
    assert state is not None
    return state


def _record(registry: er.EntityRegistry, entity_id: str) -> er.RegistryEntry:
    """Require a persistent entity-registry record."""
    record = registry.async_get(entity_id)
    assert record is not None
    return record


async def _load(
    hass, monkeypatch, *, payload=None, latitude=60.17, language="en", title="Warnings"
):
    mocks = _patch_sources(
        monkeypatch,
        weather=weather_from_fixture("forecast_normal.json"),
        forecast=forecast_from_fixture("forecast_normal.json"),
    )
    fetch = AsyncMock(return_value=feed(alert()) if payload is None else payload)
    monkeypatch.setattr(warnings_coordinator, "async_fetch_warning_payload", fetch)
    entry = _entry(
        hass,
        title=title,
        latitude=latitude,
        options={const.CONF_WEATHER_WARNINGS: True, const.CONF_WARNINGS_LANGUAGE: language},
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    identity = entry.runtime_data.coordinator.unique_id
    ids = {
        suffix: registry.async_get_entity_id(domain, const.DOMAIN, f"{identity}_{suffix}")
        for domain, suffix in (
            ("sensor", "weather_warnings"),
            ("sensor", "weather_warning_level"),
            ("binary_sensor", "weather_warning"),
        )
    }
    assert all(ids.values())
    return entry, ids, fetch, mocks


async def test_warning_public_entities_follow_independent_source_and_recover(
    hass: HomeAssistant, monkeypatch, freezer
) -> None:
    freezer.move_to("2026-11-07T10:00:00Z")
    entry, ids, fetch, mocks = await _load(hass, monkeypatch)
    count = _state(hass, ids["weather_warnings"])
    assert count.state == "1"
    assert count.attributes["warnings"][0]["headline"] == "Invented headline en-GB"
    assert count.attributes["upcoming_count"] == 0
    assert _state(hass, ids["weather_warning_level"]).state == "orange"
    assert _state(hass, ids["weather_warning_level"]).attributes["device_class"] == "enum"
    assert _state(hass, ids["weather_warning"]).state == "on"
    assert "device_class" not in _state(hass, ids["weather_warning"]).attributes
    registry = er.async_get(hass)
    device = _record(registry, ids["weather_warnings"]).device_id
    assert device is not None
    assert all(_record(registry, entity).device_id == device for entity in ids.values())
    mocks["weather"].return_value = None
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()
    assert _state(hass, ids["weather_warnings"]).state == "1"
    fetch.side_effect = ClientConnectionError("private source payload 60.17,24.94")
    await entry.runtime_data.warnings_coordinator.async_refresh()
    await hass.async_block_till_done()
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["coordinators"]["warnings"]["failure_reason"] == "transport"
    assert _state(hass, ids["weather_warnings"]).state == "1"
    fetch.side_effect = None
    fetch.return_value = b"<private source payload 60.17,24.94>"
    await entry.runtime_data.warnings_coordinator.async_refresh()
    await hass.async_block_till_done()
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["coordinators"]["warnings"]["failure_reason"] == "invalid_snapshot"
    for entity_id in ids.values():
        assert _state(hass, entity_id).state == STATE_UNAVAILABLE
        assert "warnings" not in _state(hass, entity_id).attributes
    for key in ("weather_warnings", "weather_warning_level"):
        entity = hass.data["sensor"].get_entity(ids[key])
        assert entity.native_value is None
    fetch.return_value = feed()
    await entry.runtime_data.warnings_coordinator.async_refresh()
    await hass.async_block_till_done()
    assert _state(hass, ids["weather_warnings"]).state == "0"
    assert _state(hass, ids["weather_warning_level"]).state == "none"
    assert _state(hass, ids["weather_warning"]).state == "off"
    assert _state(hass, ids["weather_warnings"]).attributes["warnings"] == []
    coordinator = entry.runtime_data.warnings_coordinator
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert not coordinator._listeners
    assert coordinator._cancel_boundary is None


async def test_warning_onset_expiry_and_replacement_update_ha_without_network(
    hass: HomeAssistant, monkeypatch, freezer
) -> None:
    freezer.move_to("2026-11-07T10:00:00Z")
    future = feed(alert(infos=info(onset="2026-11-07T10:01:00Z", expires="2026-11-07T10:02:00Z")))
    entry, ids, fetch, _ = await _load(hass, monkeypatch, payload=future)
    assert _state(hass, ids["weather_warnings"]).state == "0"
    assert _state(hass, ids["weather_warnings"]).attributes["upcoming_count"] == 1
    for minute, expected in ((1, "1"), (2, "0")):
        now = datetime(2026, 11, 7, 10, minute, tzinfo=UTC)
        freezer.move_to(now)
        async_fire_time_changed(hass, now)
        await hass.async_block_till_done()
        assert _state(hass, ids["weather_warnings"]).state == expected
    assert fetch.await_count == 1
    fetch.return_value = feed(alert("replacement"))
    await entry.runtime_data.warnings_coordinator.async_refresh()
    await hass.async_block_till_done()
    assert _state(hass, ids["weather_warnings"]).attributes["warnings"][0]["id"] == "replacement"
    fetch.return_value = feed(
        alert("replacement"),
        alert(
            "cancel",
            message_type="Cancel",
            references=f"{SENDER},replacement,{UPDATED}",
            infos="",
        ),
    )
    await entry.runtime_data.warnings_coordinator.async_refresh()
    await hass.async_block_till_done()
    cleared = _state(hass, ids["weather_warnings"])
    assert cleared.state == "0"
    assert cleared.attributes["warnings"] == []
    assert cleared.attributes["upcoming_warnings"] == []
    assert _state(hass, ids["weather_warning_level"]).state == "none"
    assert _state(hass, ids["weather_warning"]).state == "off"


async def test_warning_initial_failure_is_optional_and_primary_failure_is_not(
    hass: HomeAssistant, monkeypatch, freezer, caplog
) -> None:
    freezer.move_to("2026-11-07T10:00:00Z")
    entry, ids, fetch, _ = await _load(hass, monkeypatch, payload=b"<broken>")
    assert _state(hass, ids["weather_warnings"]).state == STATE_UNAVAILABLE
    assert "FMI warnings source unavailable (invalid_snapshot)" in caplog.text
    assert "60.17" not in caplog.text and "broken" not in caplog.text
    fetch.return_value = feed(alert())
    await entry.runtime_data.warnings_coordinator.async_refresh()
    await hass.async_block_till_done()
    assert _state(hass, ids["weather_warnings"]).state == "1"
    await hass.config_entries.async_unload(entry.entry_id)
    fetch.reset_mock()
    _patch_sources(monkeypatch)
    broken = _entry(hass, title="Primary outage", options={const.CONF_WEATHER_WARNINGS: True})
    assert not await hass.config_entries.async_setup(broken.entry_id)
    assert fetch.await_count == 0


@pytest.mark.parametrize("language,locale", [("fi", "fi-FI"), ("sv", "sv-FI"), ("en", "en-GB")])
async def test_warning_original_languages_and_ui_translations_load(
    hass: HomeAssistant, monkeypatch, freezer, language: str, locale: str
) -> None:
    freezer.move_to("2026-11-07T10:00:00Z")
    _, ids, _, _ = await _load(
        hass, monkeypatch, payload=feed(alert(infos=info(locale))), language=language
    )
    warning = _state(hass, ids["weather_warnings"]).attributes["warnings"][0]
    assert warning["language"] == locale
    assert warning["description"] == f"Invented description {locale}"
    strings = await translation.async_get_translations(hass, language, "entity", {const.DOMAIN})
    assert strings["component.fmi.entity.sensor.weather_warnings.name"]
    assert strings["component.fmi.entity.sensor.weather_warning_level.state.orange"]
    assert strings["component.fmi.entity.binary_sensor.weather_warning.name"]


async def test_warning_toggle_and_language_reload_preserve_customized_registry(
    hass: HomeAssistant, monkeypatch, freezer
) -> None:
    freezer.move_to("2026-11-07T10:00:00Z")
    publication = feed(alert(infos=info("en-GB") + info("fi-FI") + info("sv-FI")))
    entry, ids, _, _ = await _load(hass, monkeypatch, payload=publication)
    registry = er.async_get(hass)
    record = registry.async_update_entity(
        ids["weather_warnings"], new_entity_id="sensor.custom_warning_watch"
    )
    level = registry.async_update_entity(
        ids["weather_warning_level"], disabled_by=er.RegistryEntryDisabler.USER
    )
    identity = (record.id, record.unique_id, record.device_id, record.config_entry_id)
    old = entry.runtime_data.warnings_coordinator
    await _configure_options(hass, entry, weather_warnings=False)
    assert entry.runtime_data.warnings_coordinator is None
    assert not old._listeners and old._cancel_boundary is None
    assert _record(registry, "sensor.custom_warning_watch").id == record.id
    await _configure_options(hass, entry, weather_warnings=True, warnings_language="sv")
    after = _record(registry, "sensor.custom_warning_watch")
    assert (after.id, after.unique_id, after.device_id, after.config_entry_id) == identity
    assert _record(registry, level.entity_id).disabled_by is er.RegistryEntryDisabler.USER
    warning = _state(hass, after.entity_id).attributes["warnings"][0]
    assert warning["language"] == "sv-FI"
    assert entry.version == 2


async def test_warning_entries_filter_independently_and_diagnostics_are_health_only(
    hass: HomeAssistant, monkeypatch, freezer
) -> None:
    freezer.move_to("2026-11-07T10:00:00Z")
    first, first_ids, _, _ = await _load(hass, monkeypatch, title="First warnings")
    second, second_ids, _, _ = await _load(hass, monkeypatch, latitude=62, title="Second warnings")
    assert _state(hass, first_ids["weather_warnings"]).state == "1"
    assert _state(hass, second_ids["weather_warnings"]).state == "0"
    assert first.runtime_data.warnings_coordinator is not second.runtime_data.warnings_coordinator
    diagnostics = await async_get_config_entry_diagnostics(hass, first)
    assert diagnostics["coordinators"]["warnings"] == {
        "last_update_success": True,
        "poll_interval_seconds": 300,
        "source_availability": {"warnings": True},
        "failure_reason": None,
        "last_successful_refresh": "2026-11-07T10:00:00+00:00",
    }
    rendered = str(diagnostics)
    for private in ("60.17", "24.94", "Invented", first.runtime_data.coordinator.unique_id):
        assert private not in rendered


async def test_warning_move_preserves_identity_and_other_loaded_location(
    hass: HomeAssistant, monkeypatch, freezer
) -> None:
    freezer.move_to("2026-11-07T10:00:00Z")
    entry, ids, _, _ = await _load(hass, monkeypatch, title="Moving warnings")
    other, other_ids, _, _ = await _load(hass, monkeypatch, latitude=62, title="Other warnings")
    original_other = other.runtime_data.warnings_coordinator
    registry = er.async_get(hass)
    record = registry.async_update_entity(
        ids["weather_warnings"], new_entity_id="sensor.moving_warning_watch"
    )
    old_coordinator = entry.runtime_data.warnings_coordinator
    identity = entry.data[const.CONF_ENTITY_IDENTITY]
    result = await _start_reconfigure(hass, entry.entry_id)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _map_input(63, 24.94)
    )
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    moved = _record(registry, "sensor.moving_warning_watch")
    assert (moved.id, moved.unique_id, moved.device_id) == (
        record.id,
        record.unique_id,
        record.device_id,
    )
    assert entry.data[const.CONF_ENTITY_IDENTITY] == identity
    assert _state(hass, moved.entity_id).state == "0"
    assert not old_coordinator._listeners and old_coordinator._cancel_boundary is None
    assert other.runtime_data.warnings_coordinator is original_other
    assert _state(hass, other_ids["weather_warnings"]).state == "0"


async def test_warning_failed_platform_unload_keeps_live_runtime(
    hass: HomeAssistant, monkeypatch, freezer
) -> None:
    freezer.move_to("2026-11-07T10:00:00Z")
    entry, ids, _, _ = await _load(hass, monkeypatch)
    runtime = entry.runtime_data
    with monkeypatch.context() as context:
        context.setattr(
            hass.config_entries, "async_unload_platforms", AsyncMock(return_value=False)
        )
        assert not await async_unload_entry(hass, entry)
        assert entry.runtime_data is runtime
        assert runtime.warnings_coordinator._listeners
        assert runtime.warnings_coordinator._cancel_boundary is not None
        assert _state(hass, ids["weather_warnings"]).state == "1"
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert runtime.warnings_coordinator._cancel_boundary is None


async def test_warning_dashboard_and_notification_templates_distinguish_outage_and_changes(
    hass: HomeAssistant, monkeypatch, freezer
) -> None:
    freezer.move_to("2026-11-07T10:00:00Z")
    entry, ids, fetch, _ = await _load(hass, monkeypatch)
    entity_id = ids["weather_warnings"]
    first = _state(hass, entity_id)
    template = Template(
        "{% if not has_value(entity) %}unavailable{% else %}"
        "{% for warning in state_attr(entity, 'warnings') or [] %}"
        "{{ warning.headline | e }}{% endfor %}{% endif %}",
        hass,
    )
    assert "Invented headline" in template.async_render({"entity": entity_id})
    unchanged = first
    fetch.return_value = feed(alert("different-warning"))
    await entry.runtime_data.warnings_coordinator.async_refresh()
    await hass.async_block_till_done()
    replaced = _state(hass, entity_id)
    notify = Template(
        "{{ old.attributes.get('warnings', []) != new.attributes.get('warnings', []) }}", hass
    )
    assert notify.async_render({"old": unchanged, "new": replaced}) is True
    assert notify.async_render({"old": replaced, "new": replaced}) is False
    fetch.return_value = b"invalid XML"
    await entry.runtime_data.warnings_coordinator.async_refresh()
    await hass.async_block_till_done()
    assert template.async_render({"entity": entity_id}) == "unavailable"


async def test_warning_setup_cancel_and_platform_failure_clean_listener(hass, monkeypatch, freezer):
    freezer.move_to("2026-11-07T10:00:00Z")
    _patch_sources(
        monkeypatch,
        weather=weather_from_fixture("forecast_normal.json"),
        forecast=forecast_from_fixture("forecast_normal.json"),
    )
    entered, release = Event(), Event()

    async def suspended(*args):
        entered.set()
        await release.wait()
        return feed()

    monkeypatch.setattr(warnings_coordinator, "async_fetch_warning_payload", suspended)
    entry = _entry(hass, options={const.CONF_WEATHER_WARNINGS: True})
    task = create_task(hass.config_entries.async_setup(entry.entry_id))
    await entered.wait()
    task.cancel()
    try:
        await task
    except CancelledError:
        pass
    assert not entry.update_listeners
    assert await hass.config_entries.async_unload(entry.entry_id)
    monkeypatch.setattr(
        warnings_coordinator, "async_fetch_warning_payload", AsyncMock(return_value=feed())
    )
    with monkeypatch.context() as context:
        context.setattr(
            hass.config_entries,
            "async_forward_entry_setups",
            AsyncMock(side_effect=RuntimeError("synthetic platform failure")),
        )
        assert not await hass.config_entries.async_setup(entry.entry_id)
    assert not entry.update_listeners
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert len(entry.update_listeners) == 1
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert not entry.update_listeners


async def test_warning_recorder_excludes_large_attributes(hass, monkeypatch, freezer, tmp_path):
    from homeassistant.components.recorder import get_instance
    from homeassistant.components.recorder.db_schema import StateAttributes
    from homeassistant.helpers.recorder import async_initialize_recorder, session_scope

    freezer.move_to("2026-11-07T10:00:00Z")
    async_initialize_recorder(hass)
    assert await async_setup_component(
        hass,
        "recorder",
        {"recorder": {"db_url": f"sqlite:///{tmp_path / 'warnings.db'}", "commit_interval": 0}},
    )
    _, ids, _, _ = await _load(hass, monkeypatch)
    recorder = get_instance(hass)
    await recorder.async_block_till_done()

    def recorded():
        with session_scope(hass=hass, read_only=True) as session:
            return [
                json.loads(row.shared_attrs or "{}") for row in session.query(StateAttributes).all()
            ]

    rows = await hass.async_add_executor_job(recorded)
    assert rows
    assert any(row.get("requested_language") == "en" for row in rows)
    assert all(
        not {"warnings", "upcoming_warnings", "last_successful_refresh"}.intersection(row)
        for row in rows
    )
    current = _state(hass, ids["weather_warnings"]).attributes
    assert current["warnings"] and "last_successful_refresh" not in current


async def test_warning_full_documented_dashboard_and_automation(hass, monkeypatch, freezer):
    import yaml
    from homeassistant.components.persistent_notification.helpers import (
        _async_get_or_create_notifications,
    )

    freezer.move_to("2026-11-07T10:00:00Z")
    entry, ids, fetch, _ = await _load(hass, monkeypatch)
    entity_id = ids["weather_warnings"]
    guide = (Path(__file__).parents[1] / "docs/USER_GUIDE.md").read_text()
    section = guide.split("## Official Weather Warnings", 1)[1].split("## Useful Weather", 1)[0]
    examples = [yaml.safe_load(part.split("```", 1)[0]) for part in section.split("```yaml\n")[1:]]
    card, automation = examples

    def render(target: str) -> str:
        content = card["content"].replace("sensor.helsinki_weather_warnings", target)
        # The Markdown card renders strictly, so an undefined value would blank it.
        return Template(content, hass).async_render(parse_result=False, strict=True)

    assert (
        '<ha-alert alert-type="error" title="Invented headline en-GB">'
        '<ha-icon icon="mdi:weather-windy"></ha-icon>'
    ) in render(entity_id)
    for other in (ids["weather_warning_level"], ids["weather_warning"]):
        assert "is not an FMI weather warnings count sensor" in render(other)
    automation["triggers"][0]["entity_id"] = entity_id
    assert await async_setup_component(hass, "persistent_notification", {})
    notices = _async_get_or_create_notifications(hass)
    assert await async_setup_component(hass, "automation", {"automation": [automation]})
    await hass.async_block_till_done()
    for identifier, expected in (("replacement", 1), ("replacement", 1), ("another", 2)):
        fetch.return_value = feed(alert(identifier))
        await entry.runtime_data.warnings_coordinator.async_refresh()
        await hass.async_block_till_done(wait_background_tasks=True)
        assert len(notices) == expected
    fetch.return_value = feed(
        alert("future", infos=info(onset="2026-11-07T10:01:00Z", expires="2026-11-07T10:02:00Z"))
    )
    await entry.runtime_data.warnings_coordinator.async_refresh()
    await hass.async_block_till_done()
    rendered = render(entity_id)
    assert "No active warnings for this location." in rendered
    assert '<ha-alert alert-type="info" title="Upcoming: Invented headline en-GB">' in rendered
    assert "Starts:" in rendered
    freezer.move_to("2026-11-07T10:01:00Z")
    async_fire_time_changed(hass, datetime(2026, 11, 7, 10, 1, tzinfo=UTC))
    await hass.async_block_till_done()
    assert len(notices) == 3
    fetch.return_value = b"bad XML"
    await entry.runtime_data.warnings_coordinator.async_refresh()
    await hass.async_block_till_done()
    assert "Warning data is unavailable" in render(entity_id)
    assert len(notices) == 3


async def test_warning_delayed_boundaries_and_inflight_unload_in_ha(
    hass, monkeypatch, freezer, caplog
):
    freezer.move_to("2026-11-07T10:00:00Z")
    payload = feed(alert(infos=info(onset="2026-11-07T10:01:00Z", expires="2026-11-07T10:02:00Z")))
    entry, ids, _, _ = await _load(hass, monkeypatch, payload=payload)
    states = []
    remove = hass.bus.async_listen("state_changed", lambda event: states.append(event.data))
    freezer.move_to("2026-11-07T10:03:00Z")
    async_fire_time_changed(hass, datetime(2026, 11, 7, 10, 3, tzinfo=UTC))
    await hass.async_block_till_done()
    assert not any(
        event["entity_id"] == ids["weather_warning"] and event["new_state"].state == "on"
        for event in states
    )
    remove()
    entered, release = Event(), Event()

    async def pending(*args):
        entered.set()
        await release.wait()
        return feed(alert())

    monkeypatch.setattr(warnings_coordinator, "async_fetch_warning_payload", pending)
    coordinator = entry.runtime_data.warnings_coordinator
    task = create_task(coordinator.async_refresh())
    await entered.wait()
    assert await hass.config_entries.async_unload(entry.entry_id)
    release.set()
    await task
    assert coordinator.data is None and coordinator._cancel_boundary is None
    assert coordinator._source is None and "Error fetching" not in caplog.text


async def test_warning_transient_failures_hold_entities_until_the_freshness_deadline(
    hass, monkeypatch, freezer, caplog
):
    freezer.move_to("2026-11-07T10:00:00Z")
    payload = feed(alert(infos=info(expires="2026-11-07T10:07:00Z")))
    entry, ids, fetch, _ = await _load(hass, monkeypatch, payload=payload)
    coordinator = entry.runtime_data.warnings_coordinator
    assert _state(hass, ids["weather_warnings"]).state == "1"
    freezer.move_to("2026-11-07T10:05:00Z")
    fetch.side_effect = TimeoutError("private 60.17,24.94")
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    health = diagnostics["coordinators"]["warnings"]
    assert health["last_update_success"] is False and health["failure_reason"] == "timeout"
    assert health["source_availability"] == {"warnings": True}
    assert _state(hass, ids["weather_warnings"]).state == "1"
    assert _state(hass, ids["weather_warning"]).state == "on"
    freezer.move_to("2026-11-07T10:07:00Z")
    async_fire_time_changed(hass, datetime(2026, 11, 7, 10, 7, tzinfo=UTC))
    await hass.async_block_till_done()
    assert _state(hass, ids["weather_warnings"]).state == "0"
    assert _state(hass, ids["weather_warning"]).state == "off"
    freezer.move_to("2026-11-07T10:12:00Z")
    fetch.side_effect = WarningPayloadError("private", reason="http_server")
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert coordinator.failure_reason == "http_server"
    assert _state(hass, ids["weather_warning_level"]).state == "none"
    assert caplog.text.count("Error fetching FMI warnings data") == 1
    freezer.move_to("2026-11-07T10:15:00Z")
    async_fire_time_changed(hass, datetime(2026, 11, 7, 10, 15, tzinfo=UTC))
    await hass.async_block_till_done()
    assert coordinator.failure_reason == "stale_retrieval"
    for entity_id in ids.values():
        assert _state(hass, entity_id).state == STATE_UNAVAILABLE
    assert "FMI warnings source unavailable (stale_retrieval)" in caplog.text
    assert "private" not in caplog.text and "60.17" not in caplog.text
    fetch.side_effect = None
    fetch.return_value = feed()
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert coordinator.failure_reason is None
    assert _state(hass, ids["weather_warnings"]).state == "0"


async def test_warning_unchanged_publication_writes_no_state_change(hass, monkeypatch, freezer):
    """Repeated delivery of the same publication must not churn state history or triggers."""
    freezer.move_to("2026-11-07T10:00:00Z")
    entry, ids, fetch, _ = await _load(hass, monkeypatch)
    changes = []
    remove = hass.bus.async_listen(
        "state_changed",
        lambda event: (
            changes.append(event.data["entity_id"])
            if event.data["entity_id"] in ids.values()
            else None
        ),
    )
    for minute in (5, 10):
        freezer.move_to(f"2026-11-07T10:{minute:02d}:00Z")
        await entry.runtime_data.warnings_coordinator.async_refresh()
        await hass.async_block_till_done()
    assert fetch.await_count == 3
    assert changes == []
    fetch.return_value = feed(alert("changed"))
    await entry.runtime_data.warnings_coordinator.async_refresh()
    await hass.async_block_till_done()
    assert ids["weather_warnings"] in changes
    remove()
