# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Offline contracts for bounded lightning and sea-level sources."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast

import pytest
from aiohttp import ClientConnectionError, ClientTimeout

from custom_components import fmi as integration
from custom_components.fmi import FMIDataUpdateCoordinator, OptionalSourceError
from tests.helpers.fmi import load_text_fixture


class _FakeResponse:
    def __init__(
        self,
        payload: bytes,
        status: int = 200,
        *,
        chunk_size: int | None = None,
        report_content_length: bool = True,
    ) -> None:
        self.status = status
        self.content_length = len(payload) if report_content_length else None
        self.content = _FakeContent(payload, chunk_size)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args) -> None:
        return None


class _FakeContent:
    def __init__(self, payload: bytes, chunk_size: int | None) -> None:
        self.payload = payload
        self.chunk_size = chunk_size
        self.offset = 0

    async def read(self, size: int) -> bytes:
        size = min(size, self.chunk_size) if self.chunk_size is not None else size
        chunk = self.payload[self.offset : self.offset + size]
        self.offset += len(chunk)
        return chunk


class _FakeSession:
    def __init__(
        self,
        payload: bytes = b"<root />",
        *,
        status: int = 200,
        error: Exception | None = None,
        chunk_size: int | None = None,
        report_content_length: bool = True,
    ) -> None:
        self.response = _FakeResponse(
            payload,
            status,
            chunk_size=chunk_size,
            report_content_length=report_content_length,
        )
        self.error = error
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        if self.error is not None:
            raise self.error
        return self.response


class _ExecutorHass:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, tuple[Any, ...]]] = []

    async def async_add_executor_job(self, target, *args):
        self.calls.append((target, args))
        return target(*args)


class _SyntheticGeocoder:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[tuple[Any, dict[str, Any]]] = []

    def reverse(self, location, **kwargs):
        self.calls.append((location, kwargs))
        if self.error is not None:
            raise self.error
        return SimpleNamespace(address=f"Synthetic location {location}")


def _coordinator(
    *,
    session: _FakeSession | None = None,
    hass: _ExecutorHass | None = None,
) -> FMIDataUpdateCoordinator:
    coordinator = object.__new__(FMIDataUpdateCoordinator)
    coordinator.latitude = 60.17
    coordinator.longitude = 24.94
    coordinator.logger = logging.getLogger(__name__)
    coordinator.mareo_data = None
    coordinator_private = cast(Any, coordinator)
    coordinator_private._lightning_state = integration._LightningState(
        enabled=False,
        radius=200,
        max_age_minutes=1440,
    )
    coordinator_private._session = session or _FakeSession()
    coordinator_private._hass = hass or _ExecutorHass()
    return coordinator


def _lightning_payload(rows: list[tuple[float, float, float]]) -> bytes:
    positions = "\n".join(f"{lat} {lon} {timestamp}" for lat, lon, timestamp in rows)
    reasons = "\n".join("1 12.5 40.0 1.2" for _row in rows)
    return (
        '<root xmlns:gml="http://www.opengis.net/gml/3.2" '
        'xmlns:gmlcov="http://www.opengis.net/gmlcov/1.0">'
        f"<gmlcov:positions>{positions}</gmlcov:positions>"
        f"<gml:doubleOrNilReasonTupleList>{reasons}</gml:doubleOrNilReasonTupleList>"
        "</root>"
    ).encode()


def _parse_lightning(
    coordinator: FMIDataUpdateCoordinator,
    payload: bytes,
    now: datetime,
):
    coordinator_private = cast(Any, coordinator)
    return coordinator_private._FMIDataUpdateCoordinator__parse_lightning_payload(payload, now)


def test_lightning_success_payload_builds_aware_structures(monkeypatch) -> None:
    coordinator = _coordinator()
    geocoder = _SyntheticGeocoder()
    monkeypatch.setattr(integration, "Nominatim", lambda **kwargs: geocoder)
    monkeypatch.setattr(integration, "_reserve_nominatim_request", lambda: True)
    now = datetime.fromtimestamp(1780000600, UTC)

    lightning_data = _parse_lightning(
        coordinator,
        load_text_fixture("lightning_success.xml").encode(),
        now,
    )

    assert len(lightning_data) == 2
    assert lightning_data[0].time == datetime.fromtimestamp(1780000300, UTC)
    assert lightning_data[0].time.tzinfo is UTC
    assert lightning_data[0].strikes == 2
    assert lightning_data[0].peak_current == -8.0
    assert lightning_data[0].location.startswith("Synthetic location")
    assert len(geocoder.calls) == 1


def test_sea_level_success_payload_uses_aware_supported_datum() -> None:
    coordinator = _coordinator()
    coordinator_private = cast(Any, coordinator)

    mareo_data = coordinator_private._FMIDataUpdateCoordinator__parse_mareo_payload(
        load_text_fixture("sea_level_success.xml").encode()
    )

    values = mareo_data.get_values()
    assert [(item.time, item.sea_level) for item in values] == [
        (datetime(2026, 5, 20, 12, 0, tzinfo=UTC), 12.5),
        (datetime(2026, 5, 20, 12, 30, tzinfo=UTC), 13.0),
    ]


def test_lightning_max_age_boundary_is_inclusive(monkeypatch) -> None:
    now = datetime(2026, 5, 20, 12, 0, tzinfo=UTC)
    coordinator = _coordinator()
    cast(Any, coordinator)._lightning_state.max_age_minutes = 60
    monkeypatch.setattr(integration, "_reserve_nominatim_request", lambda: False)
    payload = _lightning_payload(
        [
            (60.20, 24.90, (now - timedelta(minutes=60) + timedelta(seconds=1)).timestamp()),
            (60.21, 24.91, (now - timedelta(minutes=60)).timestamp()),
            (60.22, 24.92, (now - timedelta(minutes=60) - timedelta(seconds=1)).timestamp()),
        ]
    )

    lightning_data = _parse_lightning(coordinator, payload, now)

    assert [item.time for item in lightning_data] == [
        now - timedelta(minutes=60) + timedelta(seconds=1),
        now - timedelta(minutes=60),
    ]


def test_lightning_malformed_timestamp_drops_only_invalid_row(monkeypatch) -> None:
    coordinator = _coordinator()
    monkeypatch.setattr(integration, "_reserve_nominatim_request", lambda: False)
    valid_timestamp = datetime(2026, 5, 20, 11, 30, tzinfo=UTC).timestamp()
    payload = (
        "<root><positions>60.20 24.90 not-a-timestamp\n"
        f"60.21 24.91 {valid_timestamp}</positions>"
        "<doubleOrNilReasonTupleList>1 12.5 40.0 1.2\n"
        "2 13.5 41.0 1.3</doubleOrNilReasonTupleList></root>"
    ).encode()

    lightning_data = _parse_lightning(
        coordinator,
        payload,
        datetime(2026, 5, 20, 12, 0, tzinfo=UTC),
    )

    assert len(lightning_data) == 1
    assert lightning_data[0].strikes == 2


def test_lightning_unequal_arrays_are_rejected() -> None:
    coordinator = _coordinator()

    with pytest.raises(OptionalSourceError, match="parallel arrays"):
        _parse_lightning(
            coordinator,
            load_text_fixture("lightning_unequal.xml").encode(),
            datetime(2026, 5, 28, 21, 0, tzinfo=UTC),
        )


def test_geocoder_failure_keeps_coordinates_and_caches_fallback(monkeypatch) -> None:
    coordinator = _coordinator()
    geocoder = _SyntheticGeocoder(integration.GeocoderServiceError("synthetic outage"))
    monkeypatch.setattr(integration, "Nominatim", lambda **kwargs: geocoder)
    monkeypatch.setattr(integration, "_reserve_nominatim_request", lambda: True)
    payload = _lightning_payload([(60.20, 24.90, 1780000000)])

    first = _parse_lightning(
        coordinator,
        payload,
        datetime.fromtimestamp(1780000300, UTC),
    )
    second = _parse_lightning(
        coordinator,
        payload,
        datetime.fromtimestamp(1780000300, UTC),
    )

    assert first[0].location == "60.2, 24.9"
    assert second[0].location == "60.2, 24.9"
    assert len(geocoder.calls) == 1


def test_geocoder_resolves_at_most_one_new_coordinate_per_update(monkeypatch) -> None:
    coordinator = _coordinator()
    geocoder = _SyntheticGeocoder()
    monkeypatch.setattr(integration, "Nominatim", lambda **kwargs: geocoder)
    monkeypatch.setattr(integration, "_reserve_nominatim_request", lambda: True)
    payload = load_text_fixture("lightning_success.xml").encode()
    now = datetime.fromtimestamp(1780000600, UTC)

    first = _parse_lightning(coordinator, payload, now)
    second = _parse_lightning(coordinator, payload, now)

    assert len(geocoder.calls) == 2
    assert first[0].location.startswith("Synthetic location")
    assert first[1].location == "60.2, 24.9"
    assert all(item.location.startswith("Synthetic location") for item in second)


@pytest.mark.parametrize(
    ("status", "message"),
    [(400, "client error HTTP 400"), (503, "server error HTTP 503")],
)
async def test_optional_http_status_is_classified(status: int, message: str) -> None:
    coordinator = _coordinator(session=_FakeSession(status=status))
    coordinator_private = cast(Any, coordinator)

    with pytest.raises(OptionalSourceError, match=message):
        await coordinator_private._FMIDataUpdateCoordinator__async_update_mareo_data()


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (TimeoutError(), "request timed out"),
        (ClientConnectionError("synthetic disconnect"), "transport error"),
    ],
)
async def test_optional_transport_failure_is_classified(
    error: Exception,
    message: str,
) -> None:
    coordinator = _coordinator(session=_FakeSession(error=error))
    coordinator_private = cast(Any, coordinator)

    with pytest.raises(OptionalSourceError, match=message):
        await coordinator_private._FMIDataUpdateCoordinator__async_update_mareo_data()


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (b"", "empty response"),
        (b"<root><broken></root>", "invalid XML"),
        (load_text_fixture("sea_level_malformed.xml").encode(), "invalid XML"),
        (
            load_text_fixture("sea_level_invalid_record.xml").encode(),
            "invalid sea-level record shape",
        ),
    ],
)
async def test_invalid_sea_level_payload_is_isolated(payload: bytes, message: str) -> None:
    coordinator = _coordinator(session=_FakeSession(payload))
    coordinator_private = cast(Any, coordinator)

    with pytest.raises(OptionalSourceError, match=message):
        await coordinator_private._FMIDataUpdateCoordinator__async_update_mareo_data()

    assert coordinator.mareo_data is None


async def test_optional_http_uses_ha_session_bounded_timeout_and_executor() -> None:
    session = _FakeSession(
        load_text_fixture("sea_level_success.xml").encode(),
        chunk_size=7,
    )
    hass = _ExecutorHass()
    coordinator = _coordinator(session=session, hass=hass)
    coordinator_private = cast(Any, coordinator)

    await coordinator_private._FMIDataUpdateCoordinator__async_update_mareo_data()

    assert coordinator.mareo_data is not None
    assert len(hass.calls) == 1
    assert len(session.calls) == 1
    url, kwargs = session.calls[0]
    assert "starttime=" in url and url.endswith("Z&")
    request_timeout = kwargs["timeout"]
    assert isinstance(request_timeout, ClientTimeout)
    assert request_timeout.total == 5
    assert request_timeout.connect == 2
    assert request_timeout.sock_read == 3


async def test_lightning_request_uses_configured_max_age(monkeypatch) -> None:
    now = datetime(2026, 5, 20, 12, 0, tzinfo=UTC)
    session = _FakeSession(_lightning_payload([(60.20, 24.90, now.timestamp())]))
    coordinator = _coordinator(session=session)
    cast(Any, coordinator)._lightning_state.max_age_minutes = 60
    coordinator_private = cast(Any, coordinator)
    monkeypatch.setattr(integration.dt_util, "utcnow", lambda: now)
    monkeypatch.setattr(integration, "_reserve_nominatim_request", lambda: False)

    await coordinator_private._FMIDataUpdateCoordinator__async_update_lightning_strikes()

    assert len(session.calls) == 1
    assert "starttime=2026-05-20T11:00:00Z" in session.calls[0][0]
    assert coordinator.lightning_data is not None
    assert len(coordinator.lightning_data) == 1


async def test_optional_response_size_is_bounded() -> None:
    oversized = b"x" * (integration.const.AUX_HTTP_MAX_PAYLOAD_BYTES + 1)
    coordinator = _coordinator(
        session=_FakeSession(
            oversized,
            chunk_size=1024,
            report_content_length=False,
        )
    )
    coordinator_private = cast(Any, coordinator)

    with pytest.raises(OptionalSourceError, match="exceeds size limit"):
        await coordinator_private._FMIDataUpdateCoordinator__async_update_mareo_data()


def test_nominatim_reservation_enforces_four_per_minute(monkeypatch) -> None:
    monkeypatch.setattr(integration, "_NOMINATIM_NEXT_REQUEST_AT", 0.0)
    clock = iter((100.0, 100.0, 114.9, 115.0))
    monkeypatch.setattr(integration, "monotonic", lambda: next(clock))

    assert integration._reserve_nominatim_request()
    assert not integration._reserve_nominatim_request()
    assert not integration._reserve_nominatim_request()
    assert integration._reserve_nominatim_request()


async def test_optional_failure_clears_stale_data_and_success_recovers(monkeypatch) -> None:
    coordinator = _coordinator()
    coordinator._source_available = {}
    monkeypatch.setattr(integration, "_reserve_nominatim_request", lambda: False)
    now = datetime.fromtimestamp(1780000600, UTC)
    valid_data = _parse_lightning(
        coordinator,
        load_text_fixture("lightning_success.xml").encode(),
        now,
    )
    coordinator.lightning_data = valid_data

    async def fail() -> None:
        raise OptionalSourceError("synthetic outage")

    await coordinator._async_update_optional_source(
        "lightning",
        fail,
        "lightning_data",
        bool,
    )

    assert coordinator.lightning_data is None
    assert coordinator._source_available["lightning"] is False

    async def recover() -> None:
        coordinator.lightning_data = valid_data

    await coordinator._async_update_optional_source(
        "lightning",
        recover,
        "lightning_data",
        bool,
    )

    assert coordinator.lightning_data == valid_data
    assert coordinator._source_available["lightning"] is True


def test_malformed_lightning_xml_is_rejected() -> None:
    coordinator = _coordinator()

    with pytest.raises(OptionalSourceError, match="invalid XML"):
        _parse_lightning(
            coordinator,
            load_text_fixture("lightning_malformed.xml").encode(),
            datetime(2026, 5, 28, 21, 0, tzinfo=UTC),
        )
