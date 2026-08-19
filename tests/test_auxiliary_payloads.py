# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Offline contracts for bounded lightning and sea-level sources."""

from __future__ import annotations

import logging
from asyncio import CancelledError
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
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


def _lightning_payload(rows: Sequence[tuple[float, float, float]]) -> bytes:
    positions = "\n".join(f"{lat} {lon} {timestamp}" for lat, lon, timestamp in rows)
    reasons = "\n".join("1 12.5 40.0 1.2" for _row in rows)
    return (
        '<root xmlns:gml="http://www.opengis.net/gml/3.2" '
        'xmlns:gmlcov="http://www.opengis.net/gmlcov/1.0">'
        f"<gmlcov:positions>{positions}</gmlcov:positions>"
        f"<gml:doubleOrNilReasonTupleList>{reasons}</gml:doubleOrNilReasonTupleList>"
        "</root>"
    ).encode()


def _sea_level_payload(
    *,
    timestamp: str | None = "2026-05-20T12:00:00+00:00",
    parameter: str = "SeaLevel",
    value: str | None = "12.5",
) -> bytes:
    time_element = "<time />" if timestamp is None else f"<time>{timestamp}</time>"
    value_element = "<value />" if value is None else f"<value>{value}</value>"
    return (
        "<root><member><record><ignored>synthetic</ignored>"
        f"{time_element}<parameter>{parameter}</parameter>{value_element}"
        "</record></member></root>"
    ).encode()


def _parse_lightning(
    coordinator: FMIDataUpdateCoordinator,
    payload: bytes,
    now: datetime,
):
    coordinator_private = cast(Any, coordinator)
    return coordinator_private._FMIDataUpdateCoordinator__parse_lightning_payload(payload, now)


def test_lightning_success_payload_builds_aware_local_structures() -> None:
    coordinator = _coordinator()
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
    assert lightning_data[0].distance == 9.51
    assert lightning_data[0].bearing == 20.4
    assert lightning_data[0].direction == "N"
    assert not hasattr(lightning_data[0], "location")


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


def test_lightning_max_age_boundary_is_inclusive() -> None:
    now = datetime(2026, 5, 20, 12, 0, tzinfo=UTC)
    coordinator = _coordinator()
    cast(Any, coordinator)._lightning_state.max_age_minutes = 60
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


def test_lightning_malformed_timestamp_drops_only_invalid_row() -> None:
    coordinator = _coordinator()
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


@pytest.mark.parametrize(
    ("position", "reason"),
    [
        ("60.20 24.90 1779276600", "1 12.5 40.0"),
        ("91.0 24.90 1779276600", "1 12.5 40.0 1.2"),
        ("60.20 24.90 1779276600", "1.5 12.5 40.0 1.2"),
    ],
)
def test_lightning_malformed_rows_are_dropped(position: str, reason: str) -> None:
    """Reject incomplete rows, invalid coordinates, and fractional strike counts."""
    coordinator = _coordinator()
    payload = (
        f"<root><positions>{position}</positions>"
        f"<doubleOrNilReasonTupleList>{reason}</doubleOrNilReasonTupleList></root>"
    ).encode()

    assert (
        _parse_lightning(
            coordinator,
            payload,
            datetime(2026, 5, 20, 12, 0, tzinfo=UTC),
        )
        == []
    )


def test_lightning_out_of_range_epoch_is_dropped() -> None:
    """Isolate a finite numeric epoch that the platform cannot represent."""
    coordinator = _coordinator()
    payload = _lightning_payload([(60.20, 24.90, 1e300)])

    assert (
        _parse_lightning(
            coordinator,
            payload,
            datetime(2026, 5, 20, 12, 0, tzinfo=UTC),
        )
        == []
    )


def test_lightning_distance_failure_drops_only_the_invalid_row(monkeypatch) -> None:
    """Keep local geometry non-convergence inside the optional-source boundary."""
    coordinator = _coordinator()
    monkeypatch.setattr(integration, "lightning_geometry", lambda *_args: None)

    assert (
        _parse_lightning(
            coordinator,
            _lightning_payload([(60.20, 24.90, 1779276600)]),
            datetime(2026, 5, 20, 12, 0, tzinfo=UTC),
        )
        == []
    )


def test_lightning_geometry_failure_log_omits_strike_coordinates(
    monkeypatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Classify invalid geometry without copying FMI coordinates into logs."""
    coordinator = _coordinator()
    monkeypatch.setattr(integration, "lightning_geometry", lambda *_args: None)
    caplog.set_level(logging.WARNING)

    assert (
        _parse_lightning(
            coordinator,
            _lightning_payload([(60.201234, 24.901234, 1779276600)]),
            datetime(2026, 5, 20, 12, 0, tzinfo=UTC),
        )
        == []
    )

    assert "Skipping invalid lightning geometry" in caplog.text
    assert "60.201234" not in caplog.text
    assert "24.901234" not in caplog.text


def test_lightning_unequal_arrays_are_rejected() -> None:
    coordinator = _coordinator()

    with pytest.raises(OptionalSourceError, match="parallel arrays"):
        _parse_lightning(
            coordinator,
            load_text_fixture("lightning_unequal.xml").encode(),
            datetime(2026, 5, 28, 21, 0, tzinfo=UTC),
        )


def test_empty_lightning_payload_has_no_strikes() -> None:
    """Treat a valid XML response without either parallel array as empty data."""
    coordinator = _coordinator()

    assert (
        _parse_lightning(
            coordinator,
            b"<root />",
            datetime(2026, 5, 28, 21, 0, tzinfo=UTC),
        )
        == []
    )


def test_sea_level_ignores_unknown_parameter() -> None:
    """Ignore records outside the two explicitly understood FMI datums."""
    coordinator_private = cast(Any, _coordinator())

    mareo_data = coordinator_private._FMIDataUpdateCoordinator__parse_mareo_payload(
        _sea_level_payload(parameter="SyntheticUnsupportedDatum")
    )

    assert mareo_data.size() == 0


@pytest.mark.parametrize(
    ("timestamp", "value", "message"),
    [
        (None, "12.5", "invalid sea-level record values"),
        ("not-a-timestamp", "12.5", "invalid sea-level record timestamp"),
        ("2026-05-20T12:00:00", "12.5", "invalid sea-level record timestamp"),
        ("2026-05-20T12:00:00+00:00", "NaN", "invalid sea-level record value"),
    ],
)
def test_sea_level_rejects_invalid_values(
    timestamp: str | None,
    value: str,
    message: str,
) -> None:
    """Reject incomplete, naive, malformed, and non-finite sea-level records."""
    coordinator_private = cast(Any, _coordinator())

    with pytest.raises(OptionalSourceError, match=message):
        coordinator_private._FMIDataUpdateCoordinator__parse_mareo_payload(
            _sea_level_payload(timestamp=timestamp, value=value)
        )


def test_lightning_circular_radius_rejects_bbox_corner() -> None:
    """Use the square request bbox only as a prefilter for the true circle."""
    coordinator = _coordinator()
    bbox = integration.utils.get_bounding_box(
        coordinator.latitude,
        coordinator.longitude,
        half_side_in_km=coordinator.lightning_radius,
    )
    payload = _lightning_payload([(bbox.lat_max, bbox.lon_max, 1780000000)])

    assert (
        _parse_lightning(
            coordinator,
            payload,
            datetime.fromtimestamp(1780000300, UTC),
        )
        == []
    )


@pytest.mark.parametrize(
    ("longitude", "retained"),
    [
        (0.89831, True),
        (0.8983152841195215, True),
        (0.89832, False),
    ],
)
def test_lightning_circular_radius_is_inclusive(longitude: float, retained: bool) -> None:
    """Retain an exact 100 km result and reject the first tested point outside it."""
    coordinator = _coordinator()
    coordinator.latitude = 0.0
    coordinator.longitude = 0.0
    cast(Any, coordinator)._lightning_state.radius = 100
    now = datetime.fromtimestamp(1780000300, UTC)

    data = _parse_lightning(
        coordinator,
        _lightning_payload([(0.0, longitude, 1780000000)]),
        now,
    )

    assert bool(data) is retained
    if retained:
        assert data[0].distance <= 100.0


def test_lightning_retains_five_nearest_then_presents_newest_first() -> None:
    """Keep the established distance limit and presentation ordering."""
    coordinator = _coordinator()
    coordinator.latitude = 0.0
    coordinator.longitude = 0.0
    now = datetime.fromtimestamp(1780000600, UTC)
    rows = [
        (0.0, longitude, 1780000000 + index * 100)
        for index, longitude in enumerate((0.1, 0.2, 0.3, 0.4, 0.5, 0.6))
    ]

    data = _parse_lightning(coordinator, _lightning_payload(rows), now)

    assert len(data) == 5
    assert [item.time.timestamp() for item in data] == [
        1780000400,
        1780000300,
        1780000200,
        1780000100,
        1780000000,
    ]


def test_lightning_parser_is_deterministic_and_network_free() -> None:
    """Produce identical local records without address lookup or raw coordinates."""
    coordinator = _coordinator()
    payload = load_text_fixture("lightning_success.xml").encode()
    now = datetime.fromtimestamp(1780000600, UTC)

    first = _parse_lightning(coordinator, payload, now)
    second = _parse_lightning(coordinator, payload, now)

    assert first == second
    assert [item.direction for item in first] == ["N", "NW"]
    assert all(not hasattr(item, "location") for item in first)


def test_lightning_geometry_uses_each_coordinators_reference_point() -> None:
    """Calculate the same FMI group independently for two configured entries."""
    now = datetime.fromtimestamp(1780000300, UTC)
    payload = _lightning_payload([(60.20, 24.90, 1780000000)])
    helsinki = _coordinator()
    tampere = _coordinator()
    tampere.latitude = 61.50
    tampere.longitude = 23.76

    helsinki_data = _parse_lightning(helsinki, payload, now)
    tampere_data = _parse_lightning(tampere, payload, now)

    assert helsinki_data[0].direction == "NW"
    assert tampere_data[0].direction == "SE"
    assert helsinki_data[0].distance == 4.01
    assert tampere_data[0].distance > 100


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


async def test_optional_content_length_rejects_oversized_response_before_read() -> None:
    """Reject a declared oversized response without consuming its stream."""
    oversized = b"x" * (integration.const.AUX_HTTP_MAX_PAYLOAD_BYTES + 1)
    session = _FakeSession(oversized)
    coordinator = _coordinator(session=session)
    coordinator_private = cast(Any, coordinator)

    with pytest.raises(OptionalSourceError, match="exceeds size limit"):
        await coordinator_private._FMIDataUpdateCoordinator__async_update_mareo_data()

    assert session.response.content.offset == 0


async def test_optional_failure_clears_stale_data_and_success_recovers(monkeypatch) -> None:
    coordinator = _coordinator()
    coordinator._source_available = {}
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


async def test_successful_empty_lightning_data_marks_source_available() -> None:
    """Keep a valid empty lightning observation distinct from source failure."""
    coordinator = _coordinator()
    coordinator._source_available = {}

    async def empty_success() -> None:
        coordinator.lightning_data = []

    await coordinator._async_update_optional_source(
        "lightning",
        empty_success,
        "lightning_data",
        lambda data: data is not None,
    )

    assert coordinator.lightning_data == []
    assert coordinator.source_availability["lightning"] is True


async def test_optional_source_cancellation_propagates() -> None:
    """Never convert task cancellation into an optional-source outage."""
    coordinator = _coordinator()
    coordinator._source_available = {}
    coordinator.lightning_data = []

    async def cancel() -> None:
        raise CancelledError

    with pytest.raises(CancelledError):
        await coordinator._async_update_optional_source(
            "lightning",
            cancel,
            "lightning_data",
            lambda data: data is not None,
        )

    assert coordinator.lightning_data == []
    assert "lightning" not in coordinator.source_availability


def test_malformed_lightning_xml_is_rejected() -> None:
    coordinator = _coordinator()

    with pytest.raises(OptionalSourceError, match="invalid XML"):
        _parse_lightning(
            coordinator,
            load_text_fixture("lightning_malformed.xml").encode(),
            datetime(2026, 5, 28, 21, 0, tzinfo=UTC),
        )


@pytest.mark.parametrize(
    "payload",
    [
        b'<!DOCTYPE root [<!ENTITY value "unsafe">]><root>&value;</root>',
        (b'<!DOCTYPE root [<!ENTITY value SYSTEM "file:///etc/passwd">]><root>&value;</root>'),
    ],
)
def test_xml_entities_are_rejected(payload: bytes) -> None:
    """Never expand internal or external entities supplied by FMI XML."""
    coordinator = _coordinator()

    with pytest.raises(OptionalSourceError, match="invalid XML"):
        _parse_lightning(
            coordinator,
            payload,
            datetime(2026, 5, 28, 21, 0, tzinfo=UTC),
        )


def test_external_dtd_is_inert() -> None:
    """An external DTD declaration must not load or add content to the document."""
    coordinator = _coordinator()
    payload = b'<!DOCTYPE root SYSTEM "file:///etc/passwd"><root />'

    assert (
        _parse_lightning(
            coordinator,
            payload,
            datetime(2026, 5, 28, 21, 0, tzinfo=UTC),
        )
        == []
    )
