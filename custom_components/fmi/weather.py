"""Support for retrieving meteorological data from FMI (Finnish Meteorological Institute)."""

import math
from collections.abc import Callable
from datetime import UTC, date, datetime

import fmi_weather_client.models as fmi_models
import homeassistant.core as ha_core
from homeassistant.components.weather import (
    ATTR_FORECAST_CLOUD_COVERAGE,
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_HUMIDITY,
    ATTR_FORECAST_NATIVE_DEW_POINT,
    ATTR_FORECAST_NATIVE_PRECIPITATION,
    ATTR_FORECAST_NATIVE_PRESSURE,
    ATTR_FORECAST_NATIVE_TEMP,
    ATTR_FORECAST_NATIVE_TEMP_LOW,
    ATTR_FORECAST_NATIVE_WIND_GUST_SPEED,
    ATTR_FORECAST_NATIVE_WIND_SPEED,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    Forecast,
    WeatherEntity,
)
from homeassistant.components.weather.const import WeatherEntityFeature
from homeassistant.const import CONF_NAME
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import FMIDataUpdateCoordinator, const, utils

PARALLEL_UPDATES = 1

CONDITION_SEVERITY = {
    "clear-night": 0,
    "sunny": 1,
    "partlycloudy": 2,
    "cloudy": 3,
    "fog": 4,
    "rainy": 5,
    "snowy": 6,
    "snowy-rainy": 7,
    "pouring": 8,
    "lightning": 9,
    "lightning-rainy": 10,
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add an FMI weather entity from a config_entry."""
    name = config_entry.data[CONF_NAME]
    daily_mode = config_entry.options.get(const.CONF_DAILY_MODE, False)
    station_id = bool(config_entry.options.get(const.CONF_OBSERVATION_STATION, 0))

    domain_data = hass.data[const.DOMAIN][config_entry.entry_id]

    coordinator = domain_data[const.COORDINATOR]

    entity_list = [FMIWeatherEntity(name, coordinator)]
    if daily_mode:
        entity_list.append(FMIWeatherEntity(f"{name} (daily)", coordinator, daily_mode=True))
    if station_id:
        try:
            coordinator = domain_data.get(const.COORDINATOR_OBSERVATION)
            if coordinator is not None:
                entity_list.append(
                    FMIWeatherEntity(f"{name} (observation)", coordinator, station_id=station_id)
                )
        except (KeyError, AttributeError) as error:
            const.LOGGER.error("Unable to setup observation object! ERROR: %s", error)

    async_add_entities(entity_list, False)


class FMIWeatherEntity(CoordinatorEntity[FMIDataUpdateCoordinator], WeatherEntity):
    """Define an FMI Weather Entity."""

    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_HOURLY | WeatherEntityFeature.FORECAST_DAILY
    )

    def __init__(
        self,
        name,
        coordinator: FMIDataUpdateCoordinator,
        station_id: bool = False,
        daily_mode: bool = False,
    ):
        """Initialize FMI weather object."""
        self.logger = const.LOGGER.getChild("weather")
        super().__init__(coordinator)
        self._observation_mode = station_id
        self._attr_supported_features = (
            WeatherEntityFeature(0)
            if station_id
            else WeatherEntityFeature.FORECAST_HOURLY | WeatherEntityFeature.FORECAST_DAILY
        )
        self._data_func: Callable[[], fmi_models.Weather | None] = (
            coordinator.get_observation if station_id else coordinator.get_weather
        )
        _weather = self._data_func()
        _attr_name = [_weather.place if _weather else name]
        _attr_unique_id = [f"{coordinator.unique_id}"]
        _name_extra = ""
        if daily_mode:
            _attr_name.append("(daily)")
            _attr_unique_id.append("daily")
        elif station_id:
            _attr_name.append("(observation)")
            _attr_unique_id.append("observation")
            _name_extra = " Observation"
        self._attr_name = " ".join(_attr_name)
        self._attr_unique_id = "_".join(_attr_unique_id)
        self._attr_device_info = {
            "identifiers": {(const.DOMAIN, coordinator.unique_id)},
            "name": (_weather.place if _weather else name) + _name_extra,
            "manufacturer": const.MANUFACTURER,
            "entry_type": DeviceEntryType.SERVICE,
        }
        self._attr_should_poll = False
        self._attr_attribution = const.ATTRIBUTION
        # update initial values
        self.update_callback()

    @ha_core.callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.update_callback()
        self.async_write_ha_state()
        if self.supported_features:
            self.hass.async_create_task(self.async_update_listeners(None))

    def update_callback(self, *_, **__):
        """Update the entity attributes."""
        _fmi = self.coordinator
        _last_update_success = _fmi.last_update_success
        _weather = self._data_func()
        if _weather is None or not _last_update_success:
            self.logger.debug("%s: no data available from FMI", self._attr_name)
            return
        _time = dt_util.as_local(_weather.data.time)
        self.logger.debug(f"{self._attr_name}: updated: {_last_update_success} time {_time}")
        # Update the entity attributes
        self._attr_native_temperature_unit = self.__get_unit(_weather, "temperature")
        self._attr_native_pressure_unit = self.__get_unit(_weather, "pressure")
        self._attr_native_wind_speed_unit = self.__get_unit(_weather, "wind_speed")
        precipitation_unit = self.__get_unit(_weather, "precipitation_amount")
        self._attr_native_precipitation_unit = (
            "mm" if precipitation_unit in {"mm", "mm/h"} else precipitation_unit
        )
        self._attr_native_temperature = self.__get_value(_weather, "temperature")
        self._attr_humidity = self.__get_value(_weather, "humidity")
        self._attr_native_precipitation = self.__get_value(_weather, "precipitation_amount")
        self._attr_native_wind_speed = self.__get_value(_weather, "wind_speed")
        wind_gust = self.__get_value(_weather, "wind_gust")
        if wind_gust is None or math.isnan(wind_gust):
            wind_gust = self.__get_value(_weather, "wind_max")
        self._attr_native_wind_gust_speed = wind_gust
        self._attr_wind_bearing = self.__get_value(_weather, "wind_direction")
        self._attr_cloud_coverage = self.__get_value(_weather, "cloud_cover")
        self._attr_native_pressure = self.__get_value(_weather, "pressure")
        self._attr_native_dew_point = self.__get_value(_weather, "dew_point")
        self._attr_condition = utils.get_weather_symbol(_weather.data.symbol.value, _fmi.hass)

    def __get_value(self, _weather, name):
        if _weather is None:
            return None
        value = getattr(_weather.data if hasattr(_weather, "data") else _weather, name)
        if value is None or value.value is None or not math.isfinite(value.value):
            return None
        return value.value

    def __get_unit(self, _weather, name):
        if _weather is None:
            return None
        value = getattr(_weather.data, name)
        if value is None or not value.unit:
            return None
        return value.unit

    def _normalized_forecasts(self) -> list[fmi_models.WeatherData]:
        """Return unique timezone-aware samples in chronological order."""
        by_time: dict[datetime, fmi_models.WeatherData] = {}
        for forecast in self.coordinator.get_hourly_forecasts():
            if forecast.time.tzinfo is None:
                self.logger.warning("FMI: ignoring forecast with a timezone-naive timestamp")
                continue
            by_time[forecast.time.astimezone(UTC)] = forecast
        return [by_time[timestamp] for timestamp in sorted(by_time)]

    def _condition(self, forecast: fmi_models.WeatherData) -> str | None:
        condition = utils.get_weather_symbol(self.__get_value(forecast, "symbol"))
        return condition or None

    def _hourly_forecast(self) -> list[Forecast]:
        """Return normalized FMI samples using Home Assistant's hourly schema."""
        result: list[Forecast] = []
        for forecast in self._normalized_forecasts():
            cloud_coverage = self.__get_value(forecast, "cloud_cover")
            result.append(
                {
                    ATTR_FORECAST_TIME: forecast.time.astimezone(UTC).isoformat(),
                    ATTR_FORECAST_CONDITION: self._condition(forecast),
                    ATTR_FORECAST_NATIVE_TEMP: self.__get_value(forecast, "temperature"),
                    ATTR_FORECAST_NATIVE_PRECIPITATION: self.__get_value(
                        forecast, "precipitation_amount"
                    ),
                    ATTR_FORECAST_NATIVE_WIND_SPEED: self.__get_value(forecast, "wind_speed"),
                    ATTR_FORECAST_NATIVE_WIND_GUST_SPEED: self.__get_value(forecast, "wind_gust"),
                    ATTR_FORECAST_WIND_BEARING: self.__get_value(forecast, "wind_direction"),
                    ATTR_FORECAST_NATIVE_PRESSURE: self.__get_value(forecast, "pressure"),
                    ATTR_FORECAST_HUMIDITY: self.__get_value(forecast, "humidity"),
                    ATTR_FORECAST_CLOUD_COVERAGE: (
                        round(cloud_coverage) if cloud_coverage is not None else None
                    ),
                    ATTR_FORECAST_NATIVE_DEW_POINT: self.__get_value(forecast, "dew_point"),
                }
            )
        return result

    def _values(
        self,
        forecasts: list[fmi_models.WeatherData],
        name: str,
    ) -> list[float]:
        return [
            value
            for forecast in forecasts
            if (value := self.__get_value(forecast, name)) is not None
        ]

    @staticmethod
    def _mean(values: list[float]) -> float | None:
        return math.fsum(values) / len(values) if values else None

    def _daily_condition(self, forecasts: list[fmi_models.WeatherData]) -> str | None:
        conditions = [
            condition
            for forecast in forecasts
            if (condition := self._condition(forecast)) in CONDITION_SEVERITY
        ]
        return max(conditions, key=CONDITION_SEVERITY.__getitem__, default=None)

    def _daily_forecast(self) -> list[Forecast]:
        """Aggregate normalized samples by Home Assistant's local calendar day."""
        by_day: dict[date, list[fmi_models.WeatherData]] = {}
        for forecast in self._normalized_forecasts():
            local_date = dt_util.as_local(forecast.time).date()
            by_day.setdefault(local_date, []).append(forecast)

        result: list[Forecast] = []
        for local_date, forecasts in sorted(by_day.items()):
            temperatures = self._values(forecasts, "temperature")
            precipitation = self._values(forecasts, "precipitation_amount")
            wind_speeds = [
                (speed, forecast)
                for forecast in forecasts
                if (speed := self.__get_value(forecast, "wind_speed")) is not None
            ]
            wind_speed, wind_sample = max(
                wind_speeds,
                key=lambda item: item[0],
                default=(None, None),
            )
            cloud_coverage = self._mean(self._values(forecasts, "cloud_cover"))
            result.append(
                {
                    ATTR_FORECAST_TIME: dt_util.as_utc(
                        dt_util.start_of_local_day(local_date)
                    ).isoformat(),
                    ATTR_FORECAST_CONDITION: self._daily_condition(forecasts),
                    ATTR_FORECAST_NATIVE_TEMP: max(temperatures, default=None),
                    ATTR_FORECAST_NATIVE_TEMP_LOW: min(temperatures, default=None),
                    ATTR_FORECAST_NATIVE_PRECIPITATION: (
                        math.fsum(precipitation) if precipitation else None
                    ),
                    ATTR_FORECAST_NATIVE_WIND_SPEED: wind_speed,
                    ATTR_FORECAST_NATIVE_WIND_GUST_SPEED: max(
                        self._values(forecasts, "wind_gust"), default=None
                    ),
                    ATTR_FORECAST_WIND_BEARING: (
                        self.__get_value(wind_sample, "wind_direction")
                        if wind_sample is not None
                        else None
                    ),
                    ATTR_FORECAST_NATIVE_PRESSURE: self._mean(self._values(forecasts, "pressure")),
                    ATTR_FORECAST_HUMIDITY: self._mean(self._values(forecasts, "humidity")),
                    ATTR_FORECAST_CLOUD_COVERAGE: (
                        round(cloud_coverage) if cloud_coverage is not None else None
                    ),
                    ATTR_FORECAST_NATIVE_DEW_POINT: self._mean(
                        self._values(forecasts, "dew_point")
                    ),
                }
            )
        return result

    def _forecast(self, daily_mode: bool) -> list[Forecast]:
        """Return the requested forecast granularity from cached FMI data."""
        return self._daily_forecast() if daily_mode else self._hourly_forecast()

    async def async_forecast_hourly(self) -> list[Forecast] | None:
        """Return the hourly forecast in native units."""
        return self._hourly_forecast()

    async def async_forecast_twice_daily(self) -> list[Forecast] | None:
        """Return the daily forecast in native units."""
        raise NotImplementedError

    async def async_forecast_daily(self) -> list[Forecast] | None:
        """Return the daily forecast in native units."""
        return self._daily_forecast()
