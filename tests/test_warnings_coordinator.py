# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Offline transport, temporal transitions, recovery, and privacy evidence."""

import json
from asyncio import CancelledError, Event, create_task
from datetime import UTC, datetime, timedelta
from threading import get_ident
from typing import cast
from unittest.mock import AsyncMock, Mock

import pytest
from aiohttp import ClientConnectionError, ClientSession
from homeassistant.core import HomeAssistant
from pytest_homeassistant.common import async_fire_time_changed

from custom_components.fmi import warnings_coordinator as implementation
from custom_components.fmi.warnings_client import WarningPayloadError
from custom_components.fmi.warnings_coordinator import (
    FMIWarningsCoordinator,
    async_fetch_warning_payload,
    warning_language,
)
from tests.helpers.warnings import SENDER, alert, feed, info
from tests.test_auxiliary_payloads import _FakeSession


@pytest.fixture
async def coordinator(hass: HomeAssistant, monkeypatch, freezer):
    freezer.move_to("2026-11-07T10:00:00Z")
    result = FMIWarningsCoordinator(hass, None, 60.5, 24.5, "en")
    monkeypatch.setattr(result, "_session", _FakeSession(feed(alert())))
    yield result
    await result.async_shutdown()


@pytest.mark.parametrize(
    "selected,configured,expected",
    [
        ("auto", "fi-FI", "fi"),
        ("auto", "sv_SE", "sv"),
        ("auto", "ru", "en"),
        ("en", "fi", "en"),
        ("fi", "en", "fi"),
        ("auto", "en", "en"),
    ],
)
def test_warning_content_language_is_explicit_and_bounded(selected, configured, expected) -> None:
    assert warning_language(selected, configured) == expected


async def test_warning_http_uses_one_bounded_shared_session_request() -> None:
    session = _FakeSession(feed(), chunk_size=7, report_content_length=False)
    payload = await async_fetch_warning_payload(cast(ClientSession, session), "sv")
    assert payload == feed()
    assert len(session.calls) == 1
    url, options = session.calls[0]
    assert url == "https://alerts.fmi.fi/cap/feed/atom_sv-FI.xml"
    assert options["allow_redirects"] is False
    assert options["timeout"].connect == 2
    assert options["timeout"].sock_read == 3
    assert options["timeout"].total == 30


@pytest.mark.parametrize(
    "status,reason", [(301, "redirect"), (400, "http_client"), (500, "http_server")]
)
async def test_warning_http_status_is_a_failure_without_retry(status: int, reason: str) -> None:
    session = _FakeSession(feed(), status=status)
    with pytest.raises(WarningPayloadError) as raised:
        await async_fetch_warning_payload(cast(ClientSession, session), "en")
    assert raised.value.reason == reason
    assert len(session.calls) == 1


@pytest.mark.parametrize("reported", [True, False])
async def test_warning_response_size_is_bounded(monkeypatch, reported: bool) -> None:
    monkeypatch.setattr(implementation.const, "WARNING_MAX_PAYLOAD_BYTES", 16)
    session = _FakeSession(b"x" * 17, report_content_length=reported, chunk_size=3)
    with pytest.raises(WarningPayloadError):
        await async_fetch_warning_payload(cast(ClientSession, session), "en")


async def test_warning_empty_body_is_not_an_empty_publication() -> None:
    with pytest.raises(WarningPayloadError):
        await async_fetch_warning_payload(cast(ClientSession, _FakeSession(b"  ")), "en")


async def test_warning_failure_clears_recovers_and_rejects_publication_rollback(
    coordinator, monkeypatch, caplog
) -> None:
    await coordinator.async_refresh()
    assert len(coordinator.data.active) == 1
    assert coordinator.data.level == "orange"
    attrs = coordinator.data.attributes()
    assert attrs["warnings"][0]["id"] == "synthetic-one"
    assert "polygon" not in str(attrs)
    attrs["warnings"].clear()
    assert len(coordinator.data.active) == 1
    for error in (ClientConnectionError("private coordinates 60.5,24.5"), TimeoutError()):
        monkeypatch.setattr(coordinator, "_session", _FakeSession(error=error))
        await coordinator.async_refresh()
        assert not coordinator.last_update_success
        assert coordinator.data is None
        assert coordinator._cancel_boundary is None
    assert "private coordinates" not in caplog.text
    monkeypatch.setattr(coordinator, "_session", _FakeSession(feed()))
    await coordinator.async_refresh()
    assert coordinator.data.level == "none"
    health = coordinator.source_availability
    health["warnings"] = False
    assert coordinator.source_availability == {"warnings": True}
    old = feed().replace(b"2026-11-07T10:00:00Z", b"2026-11-07T09:00:00Z")
    monkeypatch.setattr(coordinator, "_session", _FakeSession(old))
    await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert coordinator.data.updated == datetime(2026, 11, 7, 10, tzinfo=UTC)
    monkeypatch.setattr(coordinator, "_session", _FakeSession(error=TimeoutError()))
    await coordinator.async_refresh()
    monkeypatch.setattr(coordinator, "_session", _FakeSession(old))
    await coordinator.async_refresh()
    assert coordinator.data is None
    assert coordinator.failure_reason == "publication_rollback"
    monkeypatch.setattr(coordinator, "_session", _FakeSession(feed()))
    await coordinator.async_refresh()
    assert coordinator.last_update_success


async def test_warning_time_boundaries_notify_without_fetching(
    coordinator, hass, freezer, monkeypatch, caplog
) -> None:
    payload = feed(alert(infos=info(onset="2026-11-07T10:01:00Z", expires="2026-11-07T10:02:00Z")))
    session = _FakeSession(payload)
    monkeypatch.setattr(coordinator, "_session", session)
    await coordinator.async_refresh()
    assert coordinator.data.active == ()
    assert len(coordinator.data.upcoming) == 1
    for minute, expected in ((1, 1), (2, 0), (15, None)):
        now = datetime(2026, 11, 7, 10, tzinfo=UTC) + timedelta(minutes=minute)
        freezer.move_to(now)
        async_fire_time_changed(hass, now)
        await hass.async_block_till_done()
        if expected is None:
            assert coordinator.data is None
            assert not coordinator.last_update_success
            assert coordinator.failure_reason == "stale_retrieval"
            assert "FMI warnings source unavailable (stale_retrieval)" in caplog.text
        else:
            assert len(coordinator.data.active) == expected
    assert len(session.calls) == 1


async def test_warning_projection_overflow_is_unavailable(coordinator, monkeypatch) -> None:
    await coordinator.async_refresh()
    maximum = len(json.dumps(coordinator.data.attributes(), ensure_ascii=False).encode())
    monkeypatch.setattr(implementation, "WARNING_ATTRIBUTES_MAX_BYTES", maximum)
    monkeypatch.setattr(coordinator, "_session", _FakeSession(feed(alert())))
    await coordinator.async_refresh()
    assert coordinator.last_update_success
    monkeypatch.setattr(implementation, "WARNING_ATTRIBUTES_MAX_BYTES", maximum - 1)
    monkeypatch.setattr(coordinator, "_session", _FakeSession(feed(alert())))
    await coordinator.async_refresh()
    assert not coordinator.last_update_success
    assert coordinator.data is None


async def test_warning_cancellation_is_not_consumed(coordinator, monkeypatch) -> None:
    async def canceled(*_args):
        raise CancelledError

    monkeypatch.setattr(implementation, "async_fetch_warning_payload", canceled)
    with pytest.raises(CancelledError):
        await coordinator._async_update_data()


async def test_warning_queued_callback_after_shutdown_cannot_revive_data(coordinator) -> None:
    await coordinator.async_refresh()
    queued = coordinator._boundary
    await coordinator.async_shutdown()
    queued(datetime(2026, 11, 7, 10, 1, tzinfo=UTC))
    assert coordinator.data is None
    assert coordinator._cancel_boundary is None


async def test_warning_parser_runs_in_executor_and_unknown_level_remains_visible(
    coordinator, monkeypatch
) -> None:
    main_thread = get_ident()
    parser = implementation.parse_warning_feed
    observed = []

    def traced_parse(*args):
        observed.append(get_ident())
        return parser(*args)

    monkeypatch.setattr(implementation, "parse_warning_feed", traced_parse)
    payload = feed(alert(infos=info(severity="FutureSeverity")))
    monkeypatch.setattr(coordinator, "_session", _FakeSession(payload))
    await coordinator.async_refresh()
    assert coordinator.data.level == "unclassified"
    assert observed and all(thread != main_thread for thread in observed)


async def test_warning_temporal_callbacks_do_not_postpone_polling(
    coordinator, monkeypatch, hass, freezer
) -> None:
    payload = feed(alert(infos=info(onset="2026-11-07T10:01:00Z")))
    fetch = AsyncMock(return_value=payload)
    monkeypatch.setattr(implementation, "async_fetch_warning_payload", fetch)
    remove = coordinator.async_add_listener(Mock())
    try:
        await coordinator.async_refresh()
        for minute in (1, 2, 3, 4, 5):
            now = datetime(2026, 11, 7, 10, minute, 1, tzinfo=UTC)
            freezer.move_to(now)
            async_fire_time_changed(hass, now)
            await hass.async_block_till_done()
        assert fetch.await_count == 2
    finally:
        remove()


async def test_warning_delayed_and_obsolete_callbacks_use_current_time(
    coordinator, monkeypatch, freezer
):
    monkeypatch.setattr(
        coordinator,
        "_session",
        _FakeSession(
            feed(alert(infos=info(onset="2026-11-07T10:01:00Z", expires="2026-11-07T10:02:00Z")))
        ),
    )
    await coordinator.async_refresh()
    generation = coordinator._timer_generation
    observed = []
    remove = coordinator.async_add_listener(lambda: observed.append(len(coordinator.data.active)))
    freezer.move_to("2026-11-07T10:03:00Z")
    coordinator._run_boundary(generation, datetime(2026, 11, 7, 10, 1, tzinfo=UTC))
    assert observed == [0]
    coordinator._run_boundary(generation, datetime(2026, 11, 7, 10, 1, tzinfo=UTC))
    assert observed == [0]
    remove()


async def test_warning_inflight_refresh_cannot_accept_after_shutdown(coordinator, monkeypatch):
    entered, release = Event(), Event()

    async def pending(*args):
        entered.set()
        await release.wait()
        return feed(alert())

    monkeypatch.setattr(implementation, "async_fetch_warning_payload", pending)
    task = create_task(coordinator._async_update_data())
    await entered.wait()
    await coordinator.async_shutdown()
    release.set()
    assert await task is None
    assert coordinator._source is None and coordinator._cancel_boundary is None


async def test_warning_mixed_severity_sorting_and_repeated_publication(
    coordinator, monkeypatch, freezer
):
    payload = feed(
        *(
            alert(key, infos=info(severity=severity))
            for key, severity in (
                ("green", "Minor"),
                ("yellow", "Moderate"),
                ("red", "Extreme"),
                ("unclassified", "New"),
                ("orange", "Severe"),
            )
        )
    )
    monkeypatch.setattr(coordinator, "_session", _FakeSession(payload))
    await coordinator.async_refresh()
    assert [item.identifier for item in coordinator.data.active] == [
        "unclassified",
        "red",
        "orange",
        "yellow",
        "green",
    ]
    assert coordinator.data.level == "unclassified"
    freezer.move_to("2026-11-07T10:14:00Z")
    monkeypatch.setattr(coordinator, "_session", _FakeSession(payload))
    await coordinator.async_refresh()
    assert coordinator.last_update_success and coordinator.data.fetched.minute == 14
    assert coordinator.data.updated.minute == 0


async def test_warning_real_utf8_presentation_boundaries(coordinator, monkeypatch):
    await coordinator.async_refresh()
    maximum = implementation.WARNING_ATTRIBUTES_MAX_BYTES
    base = len(json.dumps(coordinator.data.attributes(), ensure_ascii=False).encode())
    old = "Invented description en-GB"
    size = maximum - base + len(old.encode())
    description = "雪" * (size // 3) + "x" * (size % 3)
    for extra, successful in (("", True), ("x", False)):
        payload = feed(alert()).replace(old.encode(), (description + extra).encode())
        monkeypatch.setattr(coordinator, "_session", _FakeSession(payload))
        await coordinator.async_refresh()
        assert coordinator.last_update_success is successful
        if successful:
            size = len(json.dumps(coordinator.data.attributes(), ensure_ascii=False).encode())
            assert size == maximum
        else:
            assert coordinator.data is None and coordinator.failure_reason == "attributes_too_large"


@pytest.mark.parametrize(
    "error,reason",
    [
        (TimeoutError("private"), "timeout"),
        (ClientConnectionError("private"), "transport"),
        (WarningPayloadError("private", reason="secret coordinates"), "invalid_snapshot"),
    ],
)
async def test_warning_failure_reasons_are_bounded_and_private(
    coordinator, monkeypatch, caplog, error, reason
):
    monkeypatch.setattr(implementation, "async_fetch_warning_payload", AsyncMock(side_effect=error))
    await coordinator.async_refresh()
    assert coordinator.failure_reason == reason
    assert "private" not in caplog.text and "secret coordinates" not in caplog.text
    monkeypatch.setattr(
        implementation, "async_fetch_warning_payload", AsyncMock(return_value=feed())
    )
    await coordinator.async_refresh()
    assert coordinator.failure_reason is None


async def test_warning_future_ordering_prioritizes_onset_then_severity_and_id(
    coordinator, monkeypatch
):
    payload = feed(
        *(
            alert(key, infos=info(severity=severity, onset=f"2026-11-07T10:0{minute}:00Z"))
            for key, severity, minute in (
                ("late", "Extreme", 5),
                ("early-green", "Minor", 4),
                ("early-red-b", "Extreme", 4),
                ("early-red-a", "Extreme", 4),
            )
        )
    )
    monkeypatch.setattr(coordinator, "_session", _FakeSession(payload))
    await coordinator.async_refresh()
    assert coordinator.data.active == () and coordinator.data.level == "none"
    assert [item.identifier for item in coordinator.data.upcoming] == [
        "early-red-a",
        "early-red-b",
        "early-green",
        "late",
    ]


def _published(identifier: str, updated: str) -> bytes:
    return feed(alert(identifier)).replace(b"2026-11-07T10:00:00Z", updated.encode())


def _active_ids(coordinator) -> list[str]:
    return [item.identifier for item in coordinator.data.active]


async def test_warning_older_publication_cannot_flap_or_stick(coordinator, monkeypatch, freezer):
    """Older publications never replace newer data, and the guard expires with freshness."""
    newer = _published("newer", "2026-11-07T10:00:00Z")
    older = _published("older", "2026-11-07T09:55:00Z")
    steps = (
        ("10:00", newer, ["newer"], "10:00"),
        ("10:05", older, ["newer"], "10:00"),
        ("10:10", newer, ["newer"], "10:10"),
    )
    for clock, payload, identifiers, fetched in steps:
        freezer.move_to(f"2026-11-07T{clock}:00Z")
        monkeypatch.setattr(coordinator, "_session", _FakeSession(payload))
        await coordinator.async_refresh()
        assert coordinator.last_update_success and coordinator.failure_reason is None
        assert _active_ids(coordinator) == identifiers
        assert coordinator.data.fetched.isoformat() == f"2026-11-07T{fetched}:00+00:00"
    assert coordinator.last_successful_refresh == "2026-11-07T10:10:00+00:00"
    freezer.move_to("2026-11-07T10:12:00Z")
    monkeypatch.setattr(coordinator, "_session", _FakeSession(error=ClientConnectionError()))
    await coordinator.async_refresh()
    freezer.move_to("2026-11-07T10:24:59Z")
    monkeypatch.setattr(coordinator, "_session", _FakeSession(older))
    await coordinator.async_refresh()
    assert coordinator.data is None and coordinator.failure_reason == "publication_rollback"
    freezer.move_to("2026-11-07T10:25:00Z")
    monkeypatch.setattr(coordinator, "_session", _FakeSession(older))
    await coordinator.async_refresh()
    assert _active_ids(coordinator) == ["older"]


@pytest.mark.parametrize(
    "reason,status,payload,error,limit",
    [
        ("timeout", 200, feed(), TimeoutError("private"), None),
        ("transport", 200, feed(), ClientConnectionError("private"), None),
        ("redirect", 302, feed(), None, None),
        ("http_client", 404, feed(), None, None),
        ("http_server", 503, feed(), None, None),
        ("empty_response", 200, b"  ", None, None),
        ("response_too_large", 200, feed(), None, ("const", "WARNING_MAX_PAYLOAD_BYTES", 16)),
        ("invalid_snapshot", 200, b"<private>", None, None),
        ("unrecognized_feed", 200, feed(alert().replace(SENDER, "urn:example:x")), None, None),
        (
            "geometry_too_complex",
            200,
            feed(alert()),
            None,
            ("geometry", "MAX_GEOMETRY_COMPARISONS", 0),
        ),
    ],
)
async def test_every_classified_warning_failure_reason_is_exposed(
    hass, coordinator, monkeypatch, caplog, reason, status, payload, error, limit
):
    """Each transport and payload class keeps its reason without external text."""
    from custom_components.fmi import warning_geometry

    await coordinator.async_refresh()
    if limit is not None:
        module = implementation.const if limit[0] == "const" else warning_geometry
        monkeypatch.setattr(module, limit[1], limit[2])
    session = _FakeSession(payload, status=status, error=error)
    monkeypatch.setattr(coordinator, "_session", session)
    await coordinator.async_refresh()
    assert coordinator.failure_reason == reason
    assert reason in implementation.FAILURE_REASONS
    assert coordinator.data is None and coordinator._cancel_boundary is None
    assert f"FMI warnings source unavailable ({reason})" in caplog.text
    assert "private" not in caplog.text and "60.5" not in caplog.text


async def test_warning_unexpected_failure_clears_state_and_names_only_the_class(
    coordinator, monkeypatch, caplog
):
    await coordinator.async_refresh()
    assert coordinator._source is not None and coordinator._cancel_boundary is not None

    def broken(*_args):
        raise TypeError("private 60.5,24.5")

    monkeypatch.setattr(implementation, "parse_warning_feed", broken)
    monkeypatch.setattr(coordinator, "_session", _FakeSession(feed(alert())))
    await coordinator.async_refresh()
    assert coordinator.failure_reason == "unexpected"
    assert coordinator._source is None and coordinator._cancel_boundary is None
    assert coordinator.data is None and not coordinator.last_update_success
    assert "(unexpected): TypeError" in caplog.text
    assert "private" not in caplog.text and "60.5" not in caplog.text


async def test_warning_unchanged_publication_keeps_the_projection_equal(
    coordinator, monkeypatch, freezer
):
    """Repeated delivery only refreshes internal freshness, not exported attributes."""
    await coordinator.async_refresh()
    first = coordinator.data.attributes()
    freezer.move_to("2026-11-07T10:05:00Z")
    monkeypatch.setattr(coordinator, "_session", _FakeSession(feed(alert())))
    await coordinator.async_refresh()
    assert coordinator.data.attributes() == first
    assert coordinator.last_successful_refresh == "2026-11-07T10:05:00+00:00"
