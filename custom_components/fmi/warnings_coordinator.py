# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT
# Contracts: docs/contracts/WARNINGS.md, docs/contracts/RUNTIME.md,
# docs/contracts/AVAILABILITY.md, docs/contracts/OPTIONAL_SOURCES.md

"""Independent bounded CAP retrieval and local time transitions."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import partial
from typing import Any

from aiohttp import ClientError, ClientSession
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from . import const
from .optional_http import OptionalSourceError, async_optional_payload
from .warnings_client import (
    FMIWarning,
    WarningPayloadError,
    WarningSnapshot,
    parse_warning_feed,
)

WARNING_INTERVAL = timedelta(minutes=5)
WARNING_MAX_AGE = timedelta(minutes=15)
WARNING_ATTRIBUTES_MAX_BYTES = 128 * 1024
WARNING_LOCALES = {"en": "en-GB", "fi": "fi-FI", "sv": "sv-FI"}
FAILURE_REASONS = frozenset(
    {
        "invalid_snapshot",
        "unrecognized_feed",
        "geometry_too_complex",
        "timeout",
        "transport",
        "redirect",
        "http_server",
        "http_client",
        "response_too_large",
        "empty_response",
        "publication_rollback",
        "attributes_too_large",
        "stale_retrieval",
        "unexpected",
    }
)


def warning_language(selected: str, configured: str) -> str:
    """Resolve entry content language separately from frontend translations."""
    base = (configured if selected == "auto" else selected).replace("_", "-").lower().split("-")[0]
    return base if base in WARNING_LOCALES else "en"


async def async_fetch_warning_payload(session: ClientSession, language: str) -> bytes:
    """Read one fixed HTTPS endpoint with decoded-size and wall-clock bounds."""
    locale = WARNING_LOCALES[language]
    url = f"https://alerts.fmi.fi/cap/feed/atom_{locale}.xml"
    try:
        return await async_optional_payload(
            session,
            "warnings",
            url,
            const.WARNING_MAX_PAYLOAD_BYTES,
            allow_redirects=False,
            expected_status=200,
            total_timeout=const.WARNING_HTTP_TOTAL_TIMEOUT_SECONDS,
        )
    except OptionalSourceError as error:
        raise WarningPayloadError("warning transport failed", reason=error.reason) from None


def _rank(warning: FMIWarning) -> int:
    return {None: -1, "red": 0, "orange": 1, "yellow": 2, "green": 3}[warning.color]


@dataclass(frozen=True, slots=True)
class WarningState:
    """One complete dashboard-facing projection of a checked source snapshot."""

    active: tuple[FMIWarning, ...]
    upcoming: tuple[FMIWarning, ...]
    updated: datetime
    fetched: datetime
    language: str

    @property
    def level(self) -> str:
        """Return an enum value without treating unclassified as an all-clear."""
        if not self.active:
            return "none"
        return self.active[0].color or "unclassified"

    def attributes(self) -> dict[str, Any]:
        """Expose detached localized text without source polygons or owner identity."""
        return {
            "warnings": [warning.as_attributes() for warning in self.active],
            "upcoming_warnings": [warning.as_attributes() for warning in self.upcoming],
            "upcoming_count": len(self.upcoming),
            "feed_updated": self.updated.isoformat(),
            "requested_language": self.language,
        }


class FMIWarningsCoordinator(DataUpdateCoordinator[WarningState | None]):
    """Own one entry's warning state without depending on its weather availability."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry | None,
        latitude: float,
        longitude: float,
        language: str,
    ) -> None:
        super().__init__(
            hass,
            const.LOGGER.getChild("warnings"),
            config_entry=entry,
            name="FMI warnings",
            update_interval=WARNING_INTERVAL,
        )
        self.latitude = latitude
        self.longitude = longitude
        self.language = language
        self._session = async_get_clientsession(hass)
        self._source: tuple[WarningSnapshot, datetime] | None = None
        self._accepted: tuple[datetime, datetime] | None = None
        self._cancel_boundary: Callable[[], None] | None = None
        self._timer_generation = 0
        self._closed = False
        self.failure_reason: str | None = None

    @property
    def source_availability(self) -> dict[str, bool]:
        """Return a detached health-only mapping for diagnostics."""
        return {"warnings": self.last_update_success and self.data is not None}

    @property
    def last_successful_refresh(self) -> str | None:
        """Return the retrieval time of the last accepted publication for diagnostics."""
        return self._accepted[1].isoformat() if self._accepted is not None else None

    @callback
    def _cancel_timer(self) -> None:
        self._timer_generation += 1
        if self._cancel_boundary is not None:
            self._cancel_boundary()
            self._cancel_boundary = None

    @callback
    def _clear(self) -> None:
        self._cancel_timer()
        self._source = None
        self.data = None

    def _projection(self, now: datetime, source: tuple[WarningSnapshot, datetime]) -> WarningState:
        snapshot, fetched = source
        active = tuple(
            sorted(
                (item for item in snapshot.warnings if item.onset <= now < item.expires),
                key=lambda item: (_rank(item), item.onset, item.identifier),
            )
        )
        upcoming = tuple(
            sorted(
                (item for item in snapshot.warnings if now < item.onset),
                key=lambda item: (item.onset, _rank(item), item.identifier),
            )
        )
        return WarningState(active, upcoming, snapshot.updated, fetched, self.language)

    @callback
    def _schedule_boundary(self, now: datetime, source: tuple[WarningSnapshot, datetime]) -> None:
        self._cancel_timer()
        snapshot, fetched = source
        boundaries = [fetched + WARNING_MAX_AGE]
        boundaries.extend(
            moment
            for item in snapshot.warnings
            for moment in (item.onset, item.expires)
            if moment > now
        )
        generation = self._timer_generation
        self._cancel_boundary = async_track_point_in_utc_time(
            self.hass, partial(self._run_boundary, generation), min(boundaries)
        )

    @callback
    def _run_boundary(self, generation: int, scheduled: datetime) -> None:
        if generation == self._timer_generation:
            self._boundary(scheduled)

    @callback
    def _boundary(self, _scheduled: datetime) -> None:
        self._cancel_boundary = None
        source = self._source
        if source is None:
            return
        now = dt_util.utcnow()
        if now >= source[1] + WARNING_MAX_AGE:
            self._clear()
            self.last_update_success = False
            self.failure_reason = "stale_retrieval"
            self.logger.warning("FMI warnings source unavailable (stale_retrieval)")
        else:
            self.data = self._projection(now, source)
            self._schedule_boundary(now, source)
        self.async_update_listeners()

    def _is_rollback(self, snapshot: WarningSnapshot, now: datetime) -> bool:
        """Reject older publications only within the freshness window of the newest one."""
        accepted = self._accepted
        return (
            accepted is not None
            and snapshot.updated < accepted[0]
            and now < accepted[1] + WARNING_MAX_AGE
        )

    def _accept(self, snapshot: WarningSnapshot) -> WarningState:
        now = dt_util.utcnow()
        if self._is_rollback(snapshot, now):
            if self._source is None:
                raise WarningPayloadError(
                    "warning publication moved backwards", reason="publication_rollback"
                )
            self.logger.debug("Keeping the newer FMI warnings publication")
            return self._projection(now, self._source)
        source = (snapshot, now)
        result = self._projection(now, source)
        if (
            len(json.dumps(result.attributes(), ensure_ascii=False).encode())
            > WARNING_ATTRIBUTES_MAX_BYTES
        ):
            raise WarningPayloadError(
                "warning attributes exceed size limit", reason="attributes_too_large"
            )
        self._source = source
        self._accepted = (snapshot.updated, now)
        self.failure_reason = None
        self._schedule_boundary(now, source)
        return result

    def _fail(self, reason: str, detail: str = "") -> UpdateFailed:
        self._clear()
        self.failure_reason = reason if reason in FAILURE_REASONS else "invalid_snapshot"
        return UpdateFailed(f"FMI warnings source unavailable ({self.failure_reason}){detail}")

    async def _async_update_data(self) -> WarningState | None:
        try:
            payload = await async_fetch_warning_payload(self._session, self.language)
            snapshot = await self.hass.async_add_executor_job(
                parse_warning_feed, payload, self.latitude, self.longitude, self.language
            )
            return None if self._closed else self._accept(snapshot)
        except WarningPayloadError as error:
            raise self._fail(error.reason) from None
        except TimeoutError:
            raise self._fail("timeout") from None
        except ClientError:
            raise self._fail("transport") from None
        except Exception as error:  # pylint: disable=broad-exception-caught
            raise self._fail("unexpected", f": {type(error).__name__}") from None

    async def async_shutdown(self) -> None:
        """Remove local callbacks as well as the managed network schedule."""
        self._closed = True
        self._clear()
        await super().async_shutdown()
