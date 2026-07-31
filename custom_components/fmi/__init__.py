"""The FMI (Finnish Meteorological Institute) component."""

import time
import xml.etree.ElementTree as ET
from asyncio import gather, timeout
from datetime import date, datetime, timedelta

import fmi_weather_client.errors as fmi_erros
import fmi_weather_client.models as fmi_models
import requests
from dateutil import tz
from geopy.distance import geodesic
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
from geopy.geocoders import Nominatim
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_OFFSET
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import const, utils
from . import fmi_client as fmi

LOGGER = const.LOGGER
PLATFORMS = ["sensor", "weather"]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(const.DOMAIN)  # pylint: disable=invalid-name


def base_unique_id(latitude, longitude):
    """Return unique id for entries in configuration."""
    return f"{latitude}_{longitude}"


def legacy_entity_identity(latitude: float, longitude: float) -> str:
    """Return the exact v0.6.2 entity/device identity for coordinates."""
    return f"{latitude}:{longitude}"


def config_entry_unique_id(entry_id: str) -> str:
    """Return a coordinate-independent config-entry unique ID."""
    return f"fmi:{entry_id}"


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
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
    _ = config
    hass.data.setdefault(const.DOMAIN, {})
    return True


async def async_setup_entry(hass, config_entry) -> bool:
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

    hass.data[const.DOMAIN][config_entry.entry_id] = {
        const.COORDINATOR: coordinator,
        const.COORDINATOR_OBSERVATION: coordinator_observation,
        const.UNDO_UPDATE_LISTENER: undo_listener,
    }

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass, config_entry):
    """Unload an FMI config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
    if not unload_ok:
        return False

    hass.data[const.DOMAIN][config_entry.entry_id][const.UNDO_UPDATE_LISTENER]()
    hass.data[const.DOMAIN].pop(config_entry.entry_id)

    return True


async def _async_first_refresh(coordinator: DataUpdateCoordinator) -> bool:
    """Refresh one source without making another source all-or-nothing."""
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        return False
    return coordinator.last_update_success


async def update_listener(hass, config_entry):
    """Update FMI listener."""
    await hass.config_entries.async_reload(config_entry.entry_id)


class FMILightningStruct:
    """Lightning data structure"""

    def __init__(
        self, time_val, location, distance, strikes, peak_current, cloud_cover, ellipse_major
    ):
        """Initialize the lightning parameters."""
        # self.time = time_val
        _time = datetime.fromisoformat(time_val)
        self.time = _time.strftime("%Y-%m-%d %H:%M")
        self.location = location
        self.distance = float(f"{float(distance):.2f}")
        self.strikes = int(strikes)
        self.peak_current = float(peak_current)
        self.cloud_cover = float(cloud_cover)
        self.ellipse_major = float(ellipse_major)


class FMIMareoStruct:
    """Mareo data structure"""

    class SeaLevelData:
        def __init__(self, time_val: str, sea_level: float):
            """Initialize the sea level data."""
            _time = datetime.fromisoformat(time_val)
            self.time = _time.strftime("%Y-%m-%d %H:%M")
            self.sea_level = float(sea_level)

    def __init__(self):
        """Initialize the sea height data."""
        self.sea_levels: list[FMIMareoStruct.SeaLevelData] = []

    def size(self) -> int:
        """Get the size of the sea level data."""
        return len(self.sea_levels)

    def get_values(self) -> list[SeaLevelData]:
        """Get the sea level values."""
        return list(self.sea_levels)

    def append(self, sea_level_data: SeaLevelData):
        """Clear the sea level data."""
        self.sea_levels.append(sea_level_data)

    def append_values(self, time_val, sea_level):
        """Clear the sea level data."""
        sea_level_data = FMIMareoStruct.SeaLevelData(time_val, sea_level)
        self.sea_levels.append(sea_level_data)


class FMIDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching FMI data API."""

    def __init__(
        self,
        hass: HomeAssistant,
        session,
        config_entry,
        update_interval=const.FORECAST_UPDATE_INTERVAL,
        unique_id_add="",
        name="",
    ):
        """Initialize."""
        _ = session

        self.logger = const.LOGGER.getChild("coordinator")

        self._hass = hass
        self.latitude = latitude = config_entry.data[CONF_LATITUDE]
        self.longitude = longitude = config_entry.data[CONF_LONGITUDE]
        identity = config_entry.data.get(
            const.CONF_ENTITY_IDENTITY,
            legacy_entity_identity(latitude, longitude),
        )
        self.unique_id = str(identity) + unique_id_add

        self.logger.debug(f"Using latitude: {latitude} and longitude: {longitude}")

        _options: dict = config_entry.options

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
        self.lightning_mode = bool(_options.get(const.CONF_LIGHTNING, const.LIGHTNING_DEFAULT))
        self.lightning_radius = int(
            _options.get(const.CONF_LIGHTNING_DISTANCE, const.BOUNDING_BOX_HALF_SIDE_KM)
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

        # Lightning strikes
        self.lightning_data: list[FMILightningStruct] | None = None

        # Mareo
        self.mareo_data: FMIMareoStruct | None = None
        self._source_available: dict[str, bool] = {}

        name = name if name else const.DOMAIN

        self.logger.debug(f"FMI {name}: Data will be updated every {update_interval} min")

        super().__init__(
            hass, self.logger, config_entry=config_entry, name=name, update_interval=update_interval
        )

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
        """Return useful FMI error details because upstream exceptions stringify empty."""
        status_code = getattr(error, "status_code", None)
        message = getattr(error, "message", None) or getattr(error, "body", None) or str(error)
        if status_code is None:
            return message
        return f"HTTP {status_code}: {message}"

    def __update_best_weather_condition(self):

        _weather = self.get_weather()

        if _weather is None:
            return

        _forecasts = self.get_forecasts()

        curr_date = date.today()

        # Init values
        self.best_state = const.BEST_CONDITION_NOT_AVAIL
        self.best_time = _weather.data.time.astimezone(tz.tzlocal())
        self.best_temperature = _weather.data.temperature.value
        self.best_humidity = _weather.data.humidity.value
        self.best_wind_speed = _weather.data.wind_speed.value
        self.best_precipitation = _weather.data.precipitation_amount.value

        for forecast in _forecasts:
            local_time = forecast.time.astimezone(tz.tzlocal())

            if local_time.day == curr_date.day + 1:
                # Tracking best conditions for only this day
                break

            if (
                forecast.symbol.value not in const.BEST_COND_SYMBOLS
                or (wind_speed := forecast.wind_speed.value) is None
                or wind_speed < self.min_wind_speed
                or wind_speed > self.max_wind_speed
            ):
                continue

            temperature = forecast.temperature.value
            if (
                temperature is None
                or temperature < self.min_temperature
                or temperature > self.max_temperature
            ):
                continue

            if (
                (humidity := forecast.humidity.value) is None
                or humidity < self.min_humidity
                or humidity > self.max_humidity
            ):
                continue

            if (
                (precipitation_amount := forecast.precipitation_amount.value) is None
                or precipitation_amount < self.min_precip
                or precipitation_amount > self.max_precip
            ):
                continue

            # What more can you ask for?
            # Compare with temperature value already stored and
            # update if necessary

            self.best_state = const.BEST_CONDITION_AVAIL

            if self.best_temperature is None or temperature > self.best_temperature:
                self.best_time = local_time
                self.best_temperature = temperature
                self.best_humidity = forecast.humidity.value
                self.best_wind_speed = forecast.wind_speed.value
                self.best_precipitation = forecast.precipitation_amount.value

    def __lightning_strikes_postions(self, loc_list: list, text: str, timeout_time: float):
        home_cords = (self.latitude, self.longitude)
        val_list = text.lstrip().split("\n")

        for loc_index, val in enumerate(val_list):
            if not val:
                continue

            val_split = val.split(" ")
            lightning_coords = (float(val_split[0]), float(val_split[1]))
            distance = 0

            try:
                distance = geodesic(lightning_coords, home_cords).km
            except AttributeError, ValueError:
                self.logger.error(
                    f"Unable to find distance between {lightning_coords} and {home_cords}"
                )

            add_tuple = (val_split[0], val_split[1], val_split[2], distance, loc_index)
            loc_list.append(add_tuple)

            if time.time() > timeout_time:
                break

    def __lightning_strikes_reasons_list(self, loc_list: list, text: str, timeout_time: float):
        val_list = text.lstrip().split("\n")

        for index, val in enumerate(val_list):
            if not val:
                continue

            val_split = val.split(" ")
            exist_tuple = loc_list[index]

            if index != exist_tuple[4]:
                self.logger.debug("Record mismatch - aborting query")
                break

            loc_list[index] = (
                exist_tuple[0],
                exist_tuple[1],
                exist_tuple[2],
                exist_tuple[3],
                val_split[0],
                val_split[1],
                val_split[2],
                val_split[3],
            )

            if time.time() > timeout_time:
                break

    def __get_lightning_url(self):
        """Generate URL and fetch data from FMI for lightning sensors."""

        start_time = datetime.today() - timedelta(days=const.LIGHTNING_DAYS_LIMIT)
        # Format datetime to string accepted as path parameter in REST
        start_time = start_time.strftime("starttime=%Y-%m-%dT%H:%M:%SZ")

        # Get Bounding Box coords
        bbox_coords = utils.get_bounding_box(
            self.latitude, self.longitude, half_side_in_km=self.lightning_radius
        )
        bbox_uri_param = (
            "bbox="
            f"{bbox_coords.lon_min},{bbox_coords.lat_min},"
            f"{bbox_coords.lon_max},{bbox_coords.lat_max}"
        )

        base_url = const.LIGHTNING_GET_URL + start_time + "&" + bbox_uri_param + "&"
        self.logger.debug(f"FMI: Lightning URI - {base_url}")

        # Fetch data
        response = requests.get(base_url, timeout=const.TIMEOUT_LIGHTNING_PULL_IN_SECS)
        return ET.fromstring(response.content)

    def __update_lightning_strikes(self):
        self.logger.debug("FMI: Lightning started")

        loc_time_list = []
        root = self.__get_lightning_url()
        _timeout = time.time() + (const.LIGHTNING_LOOP_TIMEOUT_IN_SECS * 1000)

        for child in root.iter():
            if not child.text:
                continue
            if child.tag.find("positions") > 0:
                self.__lightning_strikes_postions(loc_time_list, child.text, _timeout)

            elif child.tag.find("doubleOrNilReasonTupleList") > 0:
                self.__lightning_strikes_reasons_list(loc_time_list, child.text, _timeout)

        # First sort for closes entries and filter to limit
        loc_time_list = sorted(loc_time_list, key=lambda item: item[3])

        self.logger.debug(f"FMI - Coords retrieved for Lightning Data- {len(loc_time_list)}")

        loc_time_list = loc_time_list[: const.LIGHTNING_LIMIT]

        # Second Sort based on date
        loc_time_list = sorted(loc_time_list, key=(lambda item: item[2]), reverse=True)

        geolocator = Nominatim(user_agent="fmi_hassio_sensor")

        # Reverse geocoding
        op_tuples = []
        for v in loc_time_list:
            location = str(v[0]) + ", " + str(v[1])
            loc_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(v[2])))
            try:
                location = geolocator.reverse(location, language="en", timeout=5).address
            except (AttributeError, ValueError, GeocoderUnavailable, GeocoderTimedOut) as e:
                self.logger.error(
                    f"Unable to reverse geocode for address-{location}. Got error-{e}"
                )

            # Time, Location, Distance, Strikes, Peak Current, Cloud Cover, Ellipse Major
            op = FMILightningStruct(
                time_val=loc_time,
                location=location,
                distance=v[3],
                strikes=v[4],
                peak_current=v[5],
                cloud_cover=v[6],
                ellipse_major=v[7],
            )
            op_tuples.append(op)
        self.lightning_data = op_tuples
        self.logger.debug("FMI: Lightning ended")

    # Update mareo data
    def __update_mareo_data(self):
        """Get the latest mareograph forecast data from FMI and update the states."""

        self.logger.debug("FMI: mareo started")
        # Format datetime to string accepted as path parameter in REST
        start_time = datetime.today().strftime("starttime=%Y-%m-%dT%H:%M:%SZ")

        # Format location to string accepted as path parameter in REST
        loc_string = "latlon=" + str(self.latitude) + "," + str(self.longitude)

        base_mareo_url = const.MAREO_GET_URL + loc_string + "&" + start_time + "&"
        self.logger.debug("FMI: Using Mareo URL: %s", base_mareo_url)

        # Fetch data
        response_mareo = requests.get(base_mareo_url, timeout=const.TIMEOUT_MAREO_PULL_IN_SECS)

        root_mareo: list = ET.fromstring(response_mareo.content)

        self.mareo_data = mareo_data = FMIMareoStruct()

        # for n in range(len(root_mareo)):
        for index, mareo in enumerate(root_mareo):
            try:
                if mareo[0][2].text == "SeaLevel":
                    mareo_data.append_values(mareo[0][1].text, mareo[0][3].text)
                elif mareo[0][2].text == "SeaLevelN2000":
                    continue
                else:
                    self.logger.debug("Sealevel forecast unsupported record: %s", mareo[0][2].text)
                    continue
            except IndexError:
                self.logger.debug(
                    "Sealevel forecast records not in expected format "
                    f"for index - {index} of locstring - {loc_string}"
                )

        if mareo_data.size():
            self.logger.debug("FMI: Mareo data updated")
        else:
            self.logger.debug("FMI: Mareo data not updated. No data available")

    async def _fetch_forecast_weather(self):
        """Fetch current weather data based on estimation (forecast)."""
        try:
            data = await fmi.async_weather_by_coordinates(self.latitude, self.longitude)
        except (fmi_erros.ClientError, fmi_erros.ServerError) as error:
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
        except (fmi_erros.ClientError, fmi_erros.ServerError) as error:
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
        except (fmi_erros.ClientError, fmi_erros.ServerError) as error:
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
        update_func,
        data_attribute: str,
        data_available,
    ) -> None:
        """Keep an optional source failure from disabling current weather."""
        try:
            await self._hass.async_add_executor_job(update_func)
        except Exception as error:  # pylint: disable=broad-exception-caught
            setattr(self, data_attribute, None)
            self._set_source_availability(source, False, str(error) or type(error).__name__)
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
                self.__update_lightning_strikes,
                "lightning_data",
                bool,
            )

        await self._async_update_optional_source(
            "sea level",
            self.__update_mareo_data,
            "mareo_data",
            lambda data: bool(data and data.size()),
        )

        return {"current": self.current, "forecast": self.forecast}


class FMIObservationUpdateCoordinator(FMIDataUpdateCoordinator):
    def __init__(
        self,
        hass: HomeAssistant,
        session,
        config_entry,
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
        except (fmi_erros.ClientError, fmi_erros.ServerError) as error:
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
