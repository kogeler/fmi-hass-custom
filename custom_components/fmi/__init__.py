# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""The FMI (Finnish Meteorological Institute) component."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from asyncio import gather, timeout
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from threading import Lock
from time import monotonic
from typing import Any
from xml.parsers.expat import ExpatError

import fmi_weather_client.errors as fmi_erros
import fmi_weather_client.models as fmi_models
from aiohttp import ClientError as AiohttpClientError
from aiohttp import ClientSession, ClientTimeout
from geopy.distance import geodesic
from geopy.exc import GeocoderServiceError
from geopy.geocoders import Nominatim
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_OFFSET
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from requests.exceptions import RequestException

from . import const, utils
from . import fmi_client as fmi

LOGGER = const.LOGGER
PLATFORMS = ["sensor", "weather"]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(const.DOMAIN)  # pylint: disable=invalid-name
_NOMINATIM_RATE_LOCK = Lock()
_NOMINATIM_NEXT_REQUEST_AT = 0.0
_FMI_SOURCE_ERRORS = (
    fmi_erros.ClientError,
    fmi_erros.ServerError,
    RequestException,
    ET.ParseError,
    ExpatError,
    AttributeError,
    IndexError,
    KeyError,
    OSError,
    OverflowError,
    TypeError,
    ValueError,
)


class OptionalSourceError(RuntimeError):
    """Report a classified optional-source transport or payload failure."""


@dataclass(slots=True)
class FMIEntryRuntimeData:
    """Runtime state owned by one FMI config entry."""

    coordinator: FMIDataUpdateCoordinator
    observation_coordinator: FMIObservationUpdateCoordinator | None
    undo_update_listener: Callable[[], None]


type FMIConfigEntry = ConfigEntry[FMIEntryRuntimeData]


def _reserve_nominatim_request() -> bool:
    """Reserve one process-wide public Nominatim request without blocking a worker."""
    global _NOMINATIM_NEXT_REQUEST_AT  # pylint: disable=global-statement

    now = monotonic()
    with _NOMINATIM_RATE_LOCK:
        if now < _NOMINATIM_NEXT_REQUEST_AT:
            return False
        _NOMINATIM_NEXT_REQUEST_AT = now + const.NOMINATIM_REQUEST_INTERVAL_SECONDS
        return True


@dataclass(slots=True)
class _LightningState:
    """Keep optional lightning settings, data, and geocoder cache together."""

    enabled: bool
    radius: int
    max_age_minutes: int
    data: list[FMILightningStruct] | None = None
    geocode_cache: dict[tuple[float, float], str] = field(default_factory=dict)
    geolocator: Nominatim | None = None


@dataclass(frozen=True, slots=True)
class _LightningRawRow:
    """Numeric values decoded from one aligned FMI lightning row."""

    latitude: float
    longitude: float
    epoch_seconds: float
    strikes: float
    peak_current: float
    cloud_cover: float
    ellipse_major: float


@dataclass(frozen=True, slots=True)
class _LightningCandidate:
    """One age- and distance-validated lightning candidate."""

    time: datetime
    coordinates: tuple[float, float]
    distance: float
    strikes: int
    peak_current: float
    cloud_cover: float
    ellipse_major: float


def base_unique_id(latitude, longitude):
    """Return unique id for entries in configuration."""
    return f"{latitude}_{longitude}"


def legacy_entity_identity(latitude: float, longitude: float) -> str:
    """Return the exact v0.6.2 entity/device identity for coordinates."""
    return f"{latitude}:{longitude}"


def config_entry_unique_id(entry_id: str) -> str:
    """Return a coordinate-independent config-entry unique ID."""
    return f"fmi:{entry_id}"


async def async_migrate_entry(hass: HomeAssistant, config_entry: FMIConfigEntry) -> bool:
    """Migrate coordinate identity while retaining all existing entity unique IDs."""
    if config_entry.version > const.CONFIG_ENTRY_VERSION:
        return False
    if config_entry.version == const.CONFIG_ENTRY_VERSION:
        return True

    data = dict(config_entry.data)
    data.setdefault(
        const.CONF_ENTITY_IDENTITY,
        legacy_entity_identity(data[CONF_LATITUDE], data[CONF_LONGITUDE]),
    )
    stable_unique_id = config_entry_unique_id(config_entry.entry_id)
    collision = hass.config_entries.async_entry_for_domain_unique_id(
        const.DOMAIN,
        stable_unique_id,
    )
    unique_id = (
        config_entry.unique_id
        if collision is not None and collision.entry_id != config_entry.entry_id
        else stable_unique_id
    )
    hass.config_entries.async_update_entry(
        config_entry,
        data=data,
        unique_id=unique_id,
        version=const.CONFIG_ENTRY_VERSION,
    )
    return True


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up configured FMI."""
    _ = hass, config
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: FMIConfigEntry) -> bool:
    """Set up FMI as config entry."""
    websession = async_get_clientsession(hass)

    coordinator = FMIDataUpdateCoordinator(hass, websession, config_entry)
    coordinator_observation = None
    if config_entry.options.get(const.CONF_OBSERVATION_STATION, 0):
        coordinator_observation = FMIObservationUpdateCoordinator(hass, websession, config_entry)

    coordinators = [coordinator]
    if coordinator_observation is not None:
        coordinators.append(coordinator_observation)
    refresh_results = await gather(*(_async_first_refresh(item) for item in coordinators))

    if not any(refresh_results):
        last_exception = next(
            (item.last_exception for item in coordinators if item.last_exception is not None),
            None,
        )
        raise ConfigEntryNotReady("FMI current conditions are unavailable") from last_exception

    undo_listener = config_entry.add_update_listener(update_listener)

    config_entry.runtime_data = FMIEntryRuntimeData(
        coordinator=coordinator,
        observation_coordinator=coordinator_observation,
        undo_update_listener=undo_listener,
    )

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: FMIConfigEntry) -> bool:
    """Unload an FMI config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
    if not unload_ok:
        return False

    config_entry.runtime_data.undo_update_listener()

    return True


async def _async_first_refresh(coordinator: DataUpdateCoordinator) -> bool:
    """Refresh one source without making another source all-or-nothing."""
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        return False
    return coordinator.last_update_success


async def update_listener(hass: HomeAssistant, config_entry: FMIConfigEntry) -> None:
    """Update FMI listener."""
    await hass.config_entries.async_reload(config_entry.entry_id)


@dataclass(frozen=True, slots=True)
class FMILightningStruct:
    """One validated lightning strike group."""

    time: datetime
    location: str
    distance: float
    strikes: int
    peak_current: float
    cloud_cover: float
    ellipse_major: float


class FMIMareoStruct:
    """Validated sea-level data ordered by aware timestamp."""

    @dataclass(frozen=True, slots=True)
    class SeaLevelData:
        """One supported sea-level value."""

        time: datetime
        sea_level: float

    def __init__(self):
        """Initialize the sea height data."""
        self.sea_levels: list[FMIMareoStruct.SeaLevelData] = []

    def size(self) -> int:
        """Get the size of the sea level data."""
        return len(self.sea_levels)

    def get_values(self) -> list[SeaLevelData]:
        """Get the sea level values."""
        return list(self.sea_levels)

    def append(self, sea_level_data: SeaLevelData) -> None:
        """Append one validated sea-level value."""
        self.sea_levels.append(sea_level_data)

    def append_values(self, time_val: datetime, sea_level: float) -> None:
        """Append validated values as a typed sea-level record."""
        sea_level_data = FMIMareoStruct.SeaLevelData(time_val, sea_level)
        self.sea_levels.append(sea_level_data)


class FMIDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching FMI data API."""

    def __init__(
        self,
        hass: HomeAssistant,
        session: ClientSession,
        config_entry: FMIConfigEntry,
        update_interval=const.FORECAST_UPDATE_INTERVAL,
        unique_id_add="",
        name="",
    ):
        """Initialize."""
        self.logger = const.LOGGER.getChild("coordinator")

        self._hass = hass
        self._session: ClientSession = session
        self.latitude = latitude = config_entry.data[CONF_LATITUDE]
        self.longitude = longitude = config_entry.data[CONF_LONGITUDE]
        identity = config_entry.data.get(
            const.CONF_ENTITY_IDENTITY,
            legacy_entity_identity(latitude, longitude),
        )
        self.unique_id = str(identity) + unique_id_add

        _options = config_entry.options

        self.time_step = int(_options.get(CONF_OFFSET, const.FORECAST_OFFSET[0]))
        self.forecast_points = int(_options.get(const.CONF_FORECAST_DAYS, const.DAYS_DEFAULT)) * 24
        self.min_temperature = float(_options.get(const.CONF_MIN_TEMP, const.TEMP_MIN_DEFAULT))
        self.max_temperature = float(_options.get(const.CONF_MAX_TEMP, const.TEMP_MAX_DEFAULT))
        self.min_humidity = float(_options.get(const.CONF_MIN_HUMIDITY, const.HUMIDITY_MIN_DEFAULT))
        self.max_humidity = float(_options.get(const.CONF_MAX_HUMIDITY, const.HUMIDITY_MAX_DEFAULT))
        self.min_wind_speed = float(
            _options.get(const.CONF_MIN_WIND_SPEED, const.WIND_SPEED_MIN_DEFAULT)
        )
        self.max_wind_speed = float(
            _options.get(const.CONF_MAX_WIND_SPEED, const.WIND_SPEED_MAX_DEFAULT)
        )
        self.min_precip = float(
            _options.get(const.CONF_MIN_PRECIPITATION, const.PRECIPITATION_MIN_DEFAULT)
        )
        self.max_precip = float(
            _options.get(const.CONF_MAX_PRECIPITATION, const.PRECIPITATION_MAX_DEFAULT)
        )
        self.daily_mode = bool(_options.get(const.CONF_DAILY_MODE, const.DAILY_MODE_DEFAULT))
        self._lightning_state = _LightningState(
            enabled=bool(_options.get(const.CONF_LIGHTNING, const.LIGHTNING_DEFAULT)),
            radius=int(
                _options.get(const.CONF_LIGHTNING_DISTANCE, const.BOUNDING_BOX_HALF_SIDE_KM)
            ),
            max_age_minutes=int(
                _options.get(
                    const.CONF_LIGHTNING_MAX_AGE,
                    const.LIGHTNING_MAX_AGE_DEFAULT_MINUTES,
                )
            ),
        )

        # Observation data if the station id is set and valid
        self.observation: fmi_models.Weather | None = None
        # Current weather based on forecast for selected coordinates
        # Note: this is an estimation received from FMI
        self.current: fmi_models.Weather | None = None
        # Next day(s) forecasts
        self.forecast: fmi_models.Forecast | None = None

        # Best Time Attributes derived based on forecast weather data
        self.best_time: datetime | None = None
        self.best_temperature: float | None = None
        self.best_humidity: float | None = None
        self.best_wind_speed: float | None = None
        self.best_precipitation: float | None = None
        self.best_state: str | None = None

        # Mareo
        self.mareo_data: FMIMareoStruct | None = None
        self._source_available: dict[str, bool] = {}

        name = name if name else const.DOMAIN

        self.logger.debug("FMI %s: data will be updated every %s", name, update_interval)

        super().__init__(
            hass, self.logger, config_entry=config_entry, name=name, update_interval=update_interval
        )

    @property
    def lightning_mode(self) -> bool:
        """Return whether lightning retrieval is enabled."""
        return self._lightning_state.enabled

    @property
    def lightning_radius(self) -> int:
        """Return the configured lightning bounding-box radius."""
        return self._lightning_state.radius

    @property
    def lightning_max_age_minutes(self) -> int:
        """Return the inclusive maximum strike age in minutes."""
        return self._lightning_state.max_age_minutes

    @property
    def lightning_data(self) -> list[FMILightningStruct] | None:
        """Return the latest validated lightning groups."""
        return self._lightning_state.data

    @lightning_data.setter
    def lightning_data(self, value: list[FMILightningStruct] | None) -> None:
        """Replace lightning data, clearing stale values on failures."""
        self._lightning_state.data = value

    @property
    def source_availability(self) -> dict[str, bool]:
        """Return a copy of source health suitable for sanitized diagnostics."""
        return dict(self._source_available)

    def get_observation(self) -> fmi_models.Weather | None:
        """Return the current observation data."""
        return self.observation

    def get_weather(self) -> fmi_models.Weather | None:
        """Return the current weather data."""
        return self.current

    def get_forecasts(self) -> list[fmi_models.WeatherData]:
        """Return forecast data at the configured legacy interval."""
        forecasts = self.get_hourly_forecasts()
        if self.time_step <= 1:
            return forecasts
        return forecasts[:: self.time_step]

    def get_hourly_forecasts(self) -> list[fmi_models.WeatherData]:
        """Return every hourly sample needed by Home Assistant forecasts."""
        if self.forecast is None:
            return []
        return self.forecast.forecasts

    def get_current_place(self) -> str | None:
        """Return the current place."""
        if self.current is not None and hasattr(self.current, "place"):
            return self.current.place
        return None

    def _set_source_availability(self, source: str, available: bool, detail: str = "") -> None:
        """Log only source outage and recovery transitions."""
        previous = self._source_available.get(source)
        self._source_available[source] = available
        if previous is available:
            return
        if available:
            if previous is False:
                self.logger.info("FMI: %s source recovered", source)
            return
        suffix = f": {detail}" if detail else ""
        self.logger.warning("FMI: %s source unavailable%s", source, suffix)

    @staticmethod
    def _fmi_error_detail(error: Exception) -> str:
        """Classify an FMI error without exposing request or response content."""
        status_code = getattr(error, "status_code", None)
        if status_code is None:
            return type(error).__name__
        return f"HTTP {status_code}"

    @staticmethod
    def _finite_weather_value(source_data: object, name: str) -> float | None:
        """Return one finite FMI value from a possibly incomplete model."""
        wrapped = getattr(source_data, name, None)
        return utils.finite_float(getattr(wrapped, "value", None))

    def __update_best_weather_condition(self) -> None:
        weather = self.get_weather()
        if weather is None:
            return

        weather_data = getattr(weather, "data", None)
        self.best_state = const.BEST_CONDITION_NOT_AVAIL
        self.best_time = utils.as_local_aware_datetime(getattr(weather_data, "time", None))
        self.best_temperature = self._finite_weather_value(weather_data, "temperature")
        self.best_humidity = self._finite_weather_value(weather_data, "humidity")
        self.best_wind_speed = self._finite_weather_value(weather_data, "wind_speed")
        self.best_precipitation = self._finite_weather_value(weather_data, "precipitation_amount")

        current_date = dt_util.now().date()
        for forecast in self.get_forecasts():
            local_time = utils.as_local_aware_datetime(getattr(forecast, "time", None))
            if local_time is None or local_time.date() != current_date:
                continue

            symbol = self._finite_weather_value(forecast, "symbol")
            wind_speed = self._finite_weather_value(forecast, "wind_speed")

            if (
                symbol not in const.BEST_COND_SYMBOLS
                or wind_speed is None
                or wind_speed < self.min_wind_speed
                or wind_speed > self.max_wind_speed
            ):
                continue

            temperature = self._finite_weather_value(forecast, "temperature")
            if (
                temperature is None
                or temperature < self.min_temperature
                or temperature > self.max_temperature
            ):
                continue

            humidity = self._finite_weather_value(forecast, "humidity")
            if humidity is None or humidity < self.min_humidity or humidity > self.max_humidity:
                continue

            precipitation_amount = self._finite_weather_value(forecast, "precipitation_amount")
            if (
                precipitation_amount is None
                or precipitation_amount < self.min_precip
                or precipitation_amount > self.max_precip
            ):
                continue

            self.best_state = const.BEST_CONDITION_AVAIL

            if self.best_temperature is None or temperature > self.best_temperature:
                self.best_time = local_time
                self.best_temperature = temperature
                self.best_humidity = humidity
                self.best_wind_speed = wind_speed
                self.best_precipitation = precipitation_amount

    @staticmethod
    def __xml_rows(root: ET.Element, local_name: str) -> list[str]:
        """Return non-empty whitespace-normalized rows for an XML local name."""
        return [
            row
            for element in root.iter()
            if element.tag.rsplit("}", 1)[-1] == local_name and element.text
            for row in element.text.splitlines()
            if row.strip()
        ]

    @staticmethod
    def __parse_xml(payload: bytes, source: str) -> ET.Element:
        """Parse one bounded XML payload with a classified failure."""
        try:
            return ET.fromstring(payload)
        except ET.ParseError as error:
            raise OptionalSourceError(f"{source} invalid XML") from error

    def __lightning_location(
        self,
        coordinates: tuple[float, float],
        *,
        allow_request: bool,
    ) -> tuple[str, bool]:
        """Return a cached address or bounded raw-coordinate fallback."""
        cached = self._lightning_state.geocode_cache.get(coordinates)
        if cached is not None:
            return cached, False

        fallback = f"{coordinates[0]}, {coordinates[1]}"
        if not allow_request or not _reserve_nominatim_request():
            return fallback, False

        try:
            if self._lightning_state.geolocator is None:
                self._lightning_state.geolocator = Nominatim(user_agent=const.NOMINATIM_USER_AGENT)
            result = self._lightning_state.geolocator.reverse(
                coordinates,
                language="en",
                exactly_one=True,
                timeout=const.NOMINATIM_TIMEOUT_SECONDS,
            )
            location = result.address if result is not None else fallback
        except (AttributeError, GeocoderServiceError, TypeError, ValueError) as error:
            self.logger.warning(
                "Unable to reverse geocode a lightning location: %s",
                type(error).__name__,
            )
            location = fallback

        self._lightning_state.geocode_cache[coordinates] = location
        return location, True

    def __decode_lightning_row(
        self,
        position: str,
        reason: str,
    ) -> _LightningRawRow | None:
        """Decode aligned numeric fields without accepting missing or non-finite data."""
        raw_values = position.split() + reason.split()
        if len(raw_values) != 7:
            self.logger.warning("Skipping malformed lightning row")
            return None
        values: list[float] = []
        for raw_value in raw_values:
            value = utils.finite_float(raw_value)
            if value is None:
                self.logger.warning("Skipping malformed lightning values")
                return None
            values.append(value)
        row = _LightningRawRow(
            latitude=values[0],
            longitude=values[1],
            epoch_seconds=values[2],
            strikes=values[3],
            peak_current=values[4],
            cloud_cover=values[5],
            ellipse_major=values[6],
        )
        if (
            not -90 <= row.latitude <= 90
            or not -180 <= row.longitude <= 180
            or not row.strikes.is_integer()
            or row.strikes < 0
        ):
            self.logger.warning("Skipping malformed lightning values")
            return None
        return row

    def __lightning_candidate(
        self,
        row: _LightningRawRow,
        cutoff: datetime,
        now: datetime,
    ) -> _LightningCandidate | None:
        """Validate one strike timestamp and distance against the current update."""
        try:
            strike_time = datetime.fromtimestamp(row.epoch_seconds, UTC)
        except OverflowError, OSError, ValueError:
            self.logger.warning("Skipping invalid lightning timestamp")
            return None
        if strike_time < cutoff or strike_time > now:
            return None
        coordinates = (row.latitude, row.longitude)
        try:
            distance = geodesic(coordinates, (self.latitude, self.longitude)).km
        except AttributeError, TypeError, ValueError:
            self.logger.warning("Skipping invalid lightning coordinates %s", coordinates)
            return None
        return _LightningCandidate(
            time=strike_time,
            coordinates=coordinates,
            distance=round(distance, 2),
            strikes=int(row.strikes),
            peak_current=row.peak_current,
            cloud_cover=row.cloud_cover,
            ellipse_major=row.ellipse_major,
        )

    def __build_lightning_data(
        self,
        candidates: list[_LightningCandidate],
    ) -> list[FMILightningStruct]:
        """Resolve at most one new address and build immutable sensor records."""
        geocode_available = True
        lightning_data: list[FMILightningStruct] = []
        for candidate in candidates:
            location, attempted = self.__lightning_location(
                candidate.coordinates,
                allow_request=geocode_available,
            )
            geocode_available = geocode_available and not attempted
            lightning_data.append(
                FMILightningStruct(
                    time=candidate.time,
                    location=location,
                    distance=candidate.distance,
                    strikes=candidate.strikes,
                    peak_current=candidate.peak_current,
                    cloud_cover=candidate.cloud_cover,
                    ellipse_major=candidate.ellipse_major,
                )
            )
        return lightning_data

    def __parse_lightning_payload(
        self,
        payload: bytes,
        now: datetime,
    ) -> list[FMILightningStruct]:
        """Validate, age-filter, distance-limit, and label lightning rows."""
        root = self.__parse_xml(payload, "lightning")
        positions = self.__xml_rows(root, "positions")
        reasons = self.__xml_rows(root, "doubleOrNilReasonTupleList")
        if not positions and not reasons:
            return []
        if len(positions) != len(reasons):
            raise OptionalSourceError("lightning parallel arrays have unequal lengths")

        now = now.astimezone(UTC)
        cutoff = now - timedelta(minutes=self.lightning_max_age_minutes)
        candidates: list[_LightningCandidate] = []
        for position, reason in zip(positions, reasons, strict=True):
            row = self.__decode_lightning_row(position, reason)
            if row is None:
                continue
            candidate = self.__lightning_candidate(row, cutoff, now)
            if candidate is not None:
                candidates.append(candidate)

        candidates = sorted(candidates, key=lambda item: item.distance)[: const.LIGHTNING_LIMIT]
        candidates.sort(key=lambda item: item.time, reverse=True)
        return self.__build_lightning_data(candidates)

    def __parse_mareo_payload(self, payload: bytes) -> FMIMareoStruct:
        """Validate supported sea-level records and retain aware timestamps."""
        root = self.__parse_xml(payload, "sea-level")
        mareo_data = FMIMareoStruct()
        for member in root:
            try:
                record = member[0]
                raw_time = record[1].text
                parameter = record[2].text
                raw_value = record[3].text
            except IndexError as error:
                raise OptionalSourceError("invalid sea-level record shape") from error
            if parameter == "SeaLevelN2000":
                continue
            if parameter != "SeaLevel":
                continue
            if raw_time is None or raw_value is None:
                raise OptionalSourceError("invalid sea-level record values")
            try:
                timestamp = datetime.fromisoformat(raw_time)
            except ValueError as error:
                raise OptionalSourceError("invalid sea-level record timestamp") from error
            if timestamp.tzinfo is None:
                raise OptionalSourceError("invalid sea-level record timestamp")
            sea_level = utils.finite_float(raw_value)
            if sea_level is None:
                raise OptionalSourceError("invalid sea-level record value")
            mareo_data.append_values(timestamp.astimezone(UTC), sea_level)
        mareo_data.sea_levels.sort(key=lambda item: item.time)
        return mareo_data

    async def __fetch_optional_payload(self, source: str, url: str) -> bytes:
        """Fetch one optional payload with bounded HA-managed HTTP I/O."""
        request_timeout = ClientTimeout(
            total=const.AUX_HTTP_TOTAL_TIMEOUT_SECONDS,
            connect=const.AUX_HTTP_CONNECT_TIMEOUT_SECONDS,
            sock_connect=const.AUX_HTTP_CONNECT_TIMEOUT_SECONDS,
            sock_read=const.AUX_HTTP_READ_TIMEOUT_SECONDS,
        )
        try:
            async with self._session.get(url, timeout=request_timeout) as response:
                if not 200 <= response.status < 300:
                    category = "server" if response.status >= 500 else "client"
                    raise OptionalSourceError(f"{source} {category} error HTTP {response.status}")
                if (
                    response.content_length is not None
                    and response.content_length > const.AUX_HTTP_MAX_PAYLOAD_BYTES
                ):
                    raise OptionalSourceError(f"{source} response exceeds size limit")
                chunks: list[bytes] = []
                remaining = const.AUX_HTTP_MAX_PAYLOAD_BYTES + 1
                while remaining:
                    chunk = await response.content.read(min(64 * 1024, remaining))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    remaining -= len(chunk)
                payload = b"".join(chunks)
        except TimeoutError as error:
            raise OptionalSourceError(f"{source} request timed out") from error
        except AiohttpClientError as error:
            raise OptionalSourceError(
                f"{source} transport error: {type(error).__name__}"
            ) from error
        if len(payload) > const.AUX_HTTP_MAX_PAYLOAD_BYTES:
            raise OptionalSourceError(f"{source} response exceeds size limit")
        if not payload.strip():
            raise OptionalSourceError(f"{source} empty response")
        return payload

    async def __async_update_lightning_strikes(self) -> None:
        """Fetch and parse bounded lightning data without blocking the event loop."""
        now = dt_util.utcnow()
        start_time = now - timedelta(minutes=self.lightning_max_age_minutes)
        bbox = utils.get_bounding_box(
            self.latitude,
            self.longitude,
            half_side_in_km=self.lightning_radius,
        )
        url = (
            f"{const.LIGHTNING_GET_URL}starttime={start_time:%Y-%m-%dT%H:%M:%SZ}&"
            f"bbox={bbox.lon_min},{bbox.lat_min},{bbox.lon_max},{bbox.lat_max}&"
        )
        payload = await self.__fetch_optional_payload("lightning", url)
        self.lightning_data = await self._hass.async_add_executor_job(
            self.__parse_lightning_payload,
            payload,
            now,
        )

    async def __async_update_mareo_data(self) -> None:
        """Fetch and parse bounded sea-level data without blocking the event loop."""
        now = dt_util.utcnow()
        url = (
            f"{const.MAREO_GET_URL}latlon={self.latitude},{self.longitude}&"
            f"starttime={now:%Y-%m-%dT%H:%M:%SZ}&"
        )
        payload = await self.__fetch_optional_payload("sea-level", url)
        self.mareo_data = await self._hass.async_add_executor_job(
            self.__parse_mareo_payload,
            payload,
        )

    async def _fetch_forecast_weather(self):
        """Fetch current weather data based on estimation (forecast)."""
        try:
            data = await fmi.async_weather_by_coordinates(self.latitude, self.longitude)
        except _FMI_SOURCE_ERRORS as error:
            self._set_source_availability("forecast current", False, self._fmi_error_detail(error))
        else:
            if data is not None:
                self._set_source_availability("forecast current", True)
                return data
            self._set_source_availability("forecast current", False, "no data returned")

        place_name = self.config_entry.title if self.config_entry is not None else ""
        if not place_name:
            return None
        try:
            data = await fmi.async_observation_by_place(place_name)
        except _FMI_SOURCE_ERRORS as error:
            self._set_source_availability("place observation", False, self._fmi_error_detail(error))
            return None
        if data is None:
            self._set_source_availability("place observation", False, "no data returned")
            return None
        self._set_source_availability("place observation", True)
        return data

    async def _fetch_forecast(self):
        """Fetch current forecast data."""
        self.forecast = None
        if not self.forecast_points:
            return
        try:
            forecast = await fmi.async_forecast_by_coordinates(
                self.latitude, self.longitude, 1, self.forecast_points
            )
        except _FMI_SOURCE_ERRORS as error:
            self._set_source_availability("forecast", False, self._fmi_error_detail(error))
            return
        if forecast is None or not forecast.forecasts:
            self._set_source_availability("forecast", False, "no data returned")
            return
        self.forecast = forecast
        self._set_source_availability("forecast", True)

    async def _async_update_optional_source(
        self,
        source: str,
        update_func: Callable[[], Awaitable[None]],
        data_attribute: str,
        data_available: Callable[[Any], bool],
    ) -> None:
        """Keep an optional source failure from disabling current weather."""
        try:
            await update_func()
        except Exception as error:  # pylint: disable=broad-exception-caught
            setattr(self, data_attribute, None)
            detail = str(error) if isinstance(error, OptionalSourceError) else type(error).__name__
            self._set_source_availability(source, False, detail)
            return
        self._set_source_availability(
            source,
            data_available(getattr(self, data_attribute)),
            "no data returned",
        )

    async def _async_update_data(self):
        """Update data via Open API."""

        try:
            async with timeout(const.TIMEOUT_FMI_INTEG_IN_SEC):
                self.logger.debug("FMI: fetch latest forecast data")
                weather_data = await self._fetch_forecast_weather()
                if weather_data is None:
                    self.current = None
                    self.forecast = None
                    raise UpdateFailed("FMI current conditions are unavailable")
                self.current = weather_data

                await self._fetch_forecast()

                # Update best time parameters
                await self._hass.async_add_executor_job(self.__update_best_weather_condition)
                self.logger.debug("FMI: Best Conditions updated")
        except TimeoutError as error:
            self.current = None
            self.forecast = None
            self._set_source_availability("primary update", False, "request timed out")
            raise UpdateFailed(error) from error
        except UpdateFailed as error:
            raise UpdateFailed(error) from error

        self._set_source_availability("primary update", True)

        if self.lightning_mode and self.lightning_radius:
            await self._async_update_optional_source(
                "lightning",
                self.__async_update_lightning_strikes,
                "lightning_data",
                bool,
            )

        await self._async_update_optional_source(
            "sea level",
            self.__async_update_mareo_data,
            "mareo_data",
            lambda data: bool(data and data.size()),
        )

        return {"current": self.current, "forecast": self.forecast}


class FMIObservationUpdateCoordinator(FMIDataUpdateCoordinator):
    def __init__(
        self,
        hass: HomeAssistant,
        session: ClientSession,
        config_entry: FMIConfigEntry,
        update_interval=const.OBSERVATION_UPDATE_INTERVAL,
    ):

        self.observation_station_id = int(
            config_entry.options.get(const.CONF_OBSERVATION_STATION, 0)
        )
        if not self.observation_station_id:
            raise AttributeError("observation not configured!")

        name = f"{const.DOMAIN} Observation"

        super().__init__(
            hass, session, config_entry, update_interval, unique_id_add="_observation", name=name
        )

    async def _fetch_observation(self):
        """Fetch the latest obsevation data from specified station."""
        if not self.observation_station_id:
            return None
        try:
            observation = await fmi.async_observation_by_station_id(self.observation_station_id)
        except _FMI_SOURCE_ERRORS as error:
            self._set_source_availability(
                "station observation", False, self._fmi_error_detail(error)
            )
            return None
        if observation is None:
            self._set_source_availability("station observation", False, "no data returned")
            return None
        self._set_source_availability("station observation", True)
        return observation

    async def _async_update_data(self):
        """Update observation data via Open API."""
        self.logger.debug(
            "FMI: Updating observation data for station %d", self.observation_station_id
        )
        try:
            async with timeout(const.TIMEOUT_FMI_INTEG_IN_SEC):
                observation = await self._fetch_observation()
                if observation is None:
                    self.observation = None
                    raise UpdateFailed("FMI station observation is unavailable")
                self.observation = observation
        except (TimeoutError, UpdateFailed) as error:
            self.observation = None
            if isinstance(error, TimeoutError):
                self._set_source_availability("station observation", False, "request timed out")
            raise UpdateFailed(error) from error
        return {"observation": self.observation}
