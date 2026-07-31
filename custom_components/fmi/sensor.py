# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Support FMI sensor entities."""

from __future__ import annotations

import enum
import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import fmi_weather_client.models as fmi_models
import homeassistant.const as ha_const
from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify

from . import FMIDataUpdateCoordinator, const, utils


class SensorType(enum.IntEnum):
    """Identify the existing FMI sensor values."""

    PLACE = enum.auto()
    WEATHER = enum.auto()
    TEMPERATURE = enum.auto()
    WIND_SPEED = enum.auto()
    WIND_DIR = enum.auto()
    WIND_GUST = enum.auto()
    HUMIDITY = enum.auto()
    CLOUDS = enum.auto()
    RAIN = enum.auto()
    TIME_FORECAST = enum.auto()
    TIME = enum.auto()
    LIGHTNING = enum.auto()
    SEA_LEVEL = enum.auto()


@dataclass(frozen=True, kw_only=True)
class FMISensorEntityDescription(SensorEntityDescription):
    """Describe an FMI sensor while preserving its legacy identity suffix."""

    sensor_type: SensorType
    legacy_name: str


# Pylint does not merge inherited Home Assistant dataclass fields into this constructor.
# pylint: disable=unexpected-keyword-arg
SENSOR_DESCRIPTIONS = (
    FMISensorEntityDescription(
        key="place",
        translation_key="place",
        name="Place",
        icon="mdi:city-variant",
        sensor_type=SensorType.PLACE,
        legacy_name="Place",
    ),
    FMISensorEntityDescription(
        key="condition",
        translation_key="condition",
        name="Condition",
        sensor_type=SensorType.WEATHER,
        legacy_name="Condition",
    ),
    FMISensorEntityDescription(
        key="temperature",
        translation_key="temperature",
        name="Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=ha_const.UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        sensor_type=SensorType.TEMPERATURE,
        legacy_name="Temperature",
    ),
    FMISensorEntityDescription(
        key="wind_speed",
        translation_key="wind_speed",
        name="Wind speed",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=ha_const.UnitOfSpeed.METERS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:weather-windy",
        sensor_type=SensorType.WIND_SPEED,
        legacy_name="Wind Speed",
    ),
    FMISensorEntityDescription(
        key="wind_direction",
        translation_key="wind_direction",
        name="Wind direction",
        icon="mdi:weather-windy",
        sensor_type=SensorType.WIND_DIR,
        legacy_name="Wind Direction",
    ),
    FMISensorEntityDescription(
        key="wind_gust",
        translation_key="wind_gust",
        name="Wind gust",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=ha_const.UnitOfSpeed.METERS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:weather-windy",
        sensor_type=SensorType.WIND_GUST,
        legacy_name="Wind Gust",
    ),
    FMISensorEntityDescription(
        key="humidity",
        translation_key="humidity",
        name="Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=ha_const.PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water",
        sensor_type=SensorType.HUMIDITY,
        legacy_name="Humidity",
    ),
    FMISensorEntityDescription(
        key="cloud_coverage",
        translation_key="cloud_coverage",
        name="Cloud coverage",
        native_unit_of_measurement=ha_const.PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:weather-cloudy",
        sensor_type=SensorType.CLOUDS,
        legacy_name="Cloud Coverage",
    ),
    FMISensorEntityDescription(
        key="rain",
        translation_key="rain",
        name="Rain",
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        native_unit_of_measurement=ha_const.UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:weather-pouring",
        sensor_type=SensorType.RAIN,
        legacy_name="Rain",
    ),
    FMISensorEntityDescription(
        key="forecast_time",
        translation_key="forecast_time",
        name="Time",
        icon="mdi:av-timer",
        sensor_type=SensorType.TIME_FORECAST,
        legacy_name="Time",
    ),
    FMISensorEntityDescription(
        key="best_time_of_day",
        translation_key="best_time_of_day",
        name="Best time of day",
        icon="mdi:av-timer",
        sensor_type=SensorType.TIME,
        legacy_name="Best Time Of Day",
    ),
)

LIGHTNING_DESCRIPTION = FMISensorEntityDescription(
    key="lightning_strikes",
    translation_key="lightning_strikes",
    name="Lightning strikes",
    icon="mdi:weather-lightning",
    sensor_type=SensorType.LIGHTNING,
    legacy_name="Lightning Strikes",
)

SEA_LEVEL_DESCRIPTION = FMISensorEntityDescription(
    key="sea_level",
    translation_key="sea_level",
    name="Sea level",
    device_class=SensorDeviceClass.DISTANCE,
    native_unit_of_measurement=ha_const.UnitOfLength.CENTIMETERS,
    state_class=SensorStateClass.MEASUREMENT,
    icon="mdi:waves",
    sensor_type=SensorType.SEA_LEVEL,
    legacy_name="Sea Level",
)
# pylint: enable=unexpected-keyword-arg

PARALLEL_UPDATES = 1


def _sensor_unique_id(
    coordinator: FMIDataUpdateCoordinator,
    client_name: str,
    description: FMISensorEntityDescription,
) -> str:
    """Return the unchanged v0.6.2 sensor unique ID."""
    return (
        f"{coordinator.unique_id}_{client_name.replace(' ', '_')}_"
        f"{description.legacy_name.replace(' ', '_')}"
    )


@callback
def _async_migrate_legacy_entity_ids(
    hass: HomeAssistant,
    coordinator: FMIDataUpdateCoordinator,
    client_name: str,
) -> None:
    """Rename only exact legacy generated IDs; preserve custom IDs and collisions."""
    registry = er.async_get(hass)
    place = coordinator.get_current_place() or client_name
    for description in SENSOR_DESCRIPTIONS:
        unique_id = _sensor_unique_id(coordinator, client_name, description)
        entity_id = registry.async_get_entity_id(SENSOR_DOMAIN, const.DOMAIN, unique_id)
        legacy_entity_id = f"{SENSOR_DOMAIN}.{slugify(description.legacy_name)}"
        if entity_id != legacy_entity_id:
            continue
        target_entity_id = f"{SENSOR_DOMAIN}.{slugify(f'{place} {description.legacy_name}')}"
        if target_entity_id == entity_id or registry.async_get(target_entity_id) is not None:
            continue
        registry.async_update_entity(entity_id, new_entity_id=target_entity_id)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up FMI sensors for a config entry."""
    name = config_entry.data[ha_const.CONF_NAME]
    lightning_mode = config_entry.options.get(const.CONF_LIGHTNING, False)
    coordinator: FMIDataUpdateCoordinator = hass.data[const.DOMAIN][config_entry.entry_id][
        const.COORDINATOR
    ]

    _async_migrate_legacy_entity_ids(hass, coordinator, name)
    entity_list: list[_BaseSensorClass] = [
        FMIBestConditionSensor(name, coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    ]
    if lightning_mode:
        entity_list.append(FMILightningStrikesSensor(name, coordinator, LIGHTNING_DESCRIPTION))
    entity_list.append(FMIMareoSensor(name, coordinator, SEA_LEVEL_DESCRIPTION))
    async_add_entities(entity_list, False)


class _BaseSensorClass(CoordinatorEntity[FMIDataUpdateCoordinator], SensorEntity):
    """Common lifecycle, identity, and device context for FMI sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        name: str,
        coordinator: FMIDataUpdateCoordinator,
        description: FMISensorEntityDescription,
    ) -> None:
        """Initialize an FMI sensor."""
        super().__init__(coordinator)
        self.logger = const.LOGGER.getChild("sensor")
        self.client_name = name
        self.entity_description = description
        self.type = description.sensor_type
        self._attr_unique_id = _sensor_unique_id(coordinator, name, description)
        place = coordinator.get_current_place() or name
        self._attr_device_info = DeviceInfo(
            identifiers={(const.DOMAIN, coordinator.unique_id)},
            name=place,
            manufacturer=const.MANUFACTURER,
            entry_type=DeviceEntryType.SERVICE,
        )
        self._attr_attribution = const.ATTRIBUTION
        self._attr_should_poll = False
        self._attr_native_value = None
        self._attr_extra_state_attributes: dict[str, Any] = {}
        self.update()

    @property
    def available(self) -> bool:
        """Report unavailable when this sensor has no valid source value."""
        return super().available and self.native_value is not None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated coordinator data."""
        self.update_callback()
        self.async_write_ha_state()

    def update_callback(self, *_: Any, **__: Any) -> None:
        """Update the entity attributes."""
        weather = self.coordinator.get_weather()
        if weather is None:
            self._attr_native_value = None
            return
        local_time = utils.as_local_aware_datetime(getattr(weather.data, "time", None))
        self.logger.debug(
            "%s: updated: %s time %s",
            self.name,
            self.coordinator.last_update_success,
            local_time,
        )
        self.update()

    def update(self) -> None:
        """Update a sensor value."""
        raise NotImplementedError("Required update method is not implemented")


class FMIBestConditionSensor(_BaseSensorClass):
    """Expose current or configured-interval FMI weather values."""

    def __init__(
        self,
        name: str,
        coordinator: FMIDataUpdateCoordinator,
        description: FMISensorEntityDescription,
    ) -> None:
        """Initialize a weather value sensor."""
        self.update_state_func: Callable[[fmi_models.WeatherData], None] = {
            SensorType.WEATHER: self.__update_weather,
            SensorType.TEMPERATURE: self.__update_temperature,
            SensorType.WIND_SPEED: self.__update_wind_speed,
            SensorType.WIND_DIR: self.__update_wind_direction,
            SensorType.WIND_GUST: self.__update_wind_gust,
            SensorType.HUMIDITY: self.__update_humidity,
            SensorType.CLOUDS: self.__update_clouds,
            SensorType.RAIN: self.__update_rain,
            SensorType.TIME_FORECAST: self.__update_forecast_time,
            SensorType.TIME: self.__update_time,
        }.get(description.sensor_type, self.__update_dummy)
        super().__init__(name, coordinator, description)

    @staticmethod
    def get_wind_direction_string(wind_direction_in_deg: float | None) -> str | None:
        """Return the compass direction for a valid degree value."""
        if (
            wind_direction_in_deg is None
            or wind_direction_in_deg < 0
            or wind_direction_in_deg > 360
        ):
            return None
        if wind_direction_in_deg <= 23 or wind_direction_in_deg > 338:
            return "N"
        if wind_direction_in_deg <= 68:
            return "NE"
        if wind_direction_in_deg <= 113:
            return "E"
        if wind_direction_in_deg <= 158:
            return "SE"
        if wind_direction_in_deg <= 203:
            return "S"
        if wind_direction_in_deg <= 248:
            return "SW"
        if wind_direction_in_deg <= 293:
            return "W"
        return "NW"

    @staticmethod
    def _finite_value(source_data: fmi_models.WeatherData, *names: str) -> float | None:
        for name in names:
            wrapped = getattr(source_data, name, None)
            value = getattr(wrapped, "value", None)
            if value is None:
                continue
            try:
                number = float(value)
            except TypeError, ValueError:
                continue
            if math.isfinite(number):
                return number
        return None

    def __convert_float(self, source_data: fmi_models.WeatherData, *names: str) -> None:
        self._attr_native_value = self._finite_value(source_data, *names)

    def __update_dummy(self, source_data: fmi_models.WeatherData) -> None:
        _ = source_data
        self._attr_native_value = None

    def __update_forecast_time(self, source_data: fmi_models.WeatherData) -> None:
        local_time = utils.as_local_aware_datetime(getattr(source_data, "time", None))
        self._attr_native_value = local_time.strftime("%H:%M") if local_time is not None else None

    def __update_weather(self, source_data: fmi_models.WeatherData) -> None:
        symbol = self._finite_value(source_data, "symbol")
        self._attr_native_value = utils.get_weather_symbol(symbol) or None

    def __update_temperature(self, source_data: fmi_models.WeatherData) -> None:
        self.__convert_float(source_data, "temperature")

    def __update_wind_speed(self, source_data: fmi_models.WeatherData) -> None:
        self.__convert_float(source_data, "wind_speed")

    def __update_wind_direction(self, source_data: fmi_models.WeatherData) -> None:
        self._attr_native_value = self.get_wind_direction_string(
            self._finite_value(source_data, "wind_direction")
        )

    def __update_wind_gust(self, source_data: fmi_models.WeatherData) -> None:
        self.__convert_float(source_data, "wind_gust", "wind_max")

    def __update_humidity(self, source_data: fmi_models.WeatherData) -> None:
        self.__convert_float(source_data, "humidity")

    def __update_clouds(self, source_data: fmi_models.WeatherData) -> None:
        self.__convert_float(source_data, "cloud_cover")

    def __update_rain(self, source_data: fmi_models.WeatherData) -> None:
        self.__convert_float(source_data, "precipitation_amount")

    def __update_time(self, source_data: fmi_models.WeatherData) -> None:
        _ = source_data
        self._attr_native_value = (
            self.coordinator.best_time.strftime("%H:%M")
            if self.coordinator.best_time is not None
            else None
        )

    def update(self) -> None:
        """Update the weather sensor state."""
        weather = self.coordinator.get_weather()
        if weather is None:
            self._attr_native_value = None
            self._attr_extra_state_attributes = {}
            return

        self._attr_extra_state_attributes = {
            ha_const.ATTR_LOCATION: weather.place,
            ha_const.ATTR_TIME: self.coordinator.best_time,
            ha_const.ATTR_TEMPERATURE: self.coordinator.best_temperature,
            const.ATTR_HUMIDITY: self.coordinator.best_humidity,
            const.ATTR_PRECIPITATION: self.coordinator.best_precipitation,
            const.ATTR_WIND_SPEED: self.coordinator.best_wind_speed,
        }
        if self.type == SensorType.PLACE:
            self._attr_native_value = weather.place
            return

        source_data: fmi_models.WeatherData | None
        if self.coordinator.time_step == 1:
            source_data = weather.data
        else:
            forecasts = self.coordinator.get_forecasts()
            if not forecasts:
                self._attr_native_value = None
                return
            source_data = forecasts[1 if len(forecasts) > 1 and dt_util.now().minute >= 30 else 0]
        self.update_state_func(source_data)


class FMILightningStrikesSensor(_BaseSensorClass):
    """Expose the latest FMI lightning strike group."""

    def __init__(
        self,
        name: str,
        coordinator: FMIDataUpdateCoordinator,
        description: FMISensorEntityDescription,
    ) -> None:
        """Initialize lightning state with FMI and OpenStreetMap attribution."""
        super().__init__(name, coordinator, description)
        self._attr_attribution = f"{const.ATTRIBUTION}; {const.OPENSTREETMAP_ATTRIBUTION}"

    def update(self) -> None:
        """Update the lightning sensor state."""
        data = self.coordinator.lightning_data
        if not data:
            self._attr_native_value = None
            self._attr_extra_state_attributes = {}
            return
        self._attr_native_value = data[0].location
        self._attr_extra_state_attributes = {
            ha_const.ATTR_LOCATION: data[0].location,
            ha_const.ATTR_TIME: data[0].time,
            const.ATTR_DISTANCE: data[0].distance,
            const.ATTR_STRIKES: data[0].strikes,
            const.ATTR_PEAK_CURRENT: data[0].peak_current,
            const.ATTR_CLOUD_COVER: data[0].cloud_cover,
            const.ATTR_ELLIPSE_MAJOR: data[0].ellipse_major,
            "OBSERVATIONS": [
                {
                    ha_const.ATTR_LOCATION: strike.location,
                    ha_const.ATTR_TIME: strike.time,
                    const.ATTR_DISTANCE: strike.distance,
                    const.ATTR_STRIKES: strike.strikes,
                    const.ATTR_PEAK_CURRENT: strike.peak_current,
                    const.ATTR_CLOUD_COVER: strike.cloud_cover,
                    const.ATTR_ELLIPSE_MAJOR: strike.ellipse_major,
                }
                for strike in data[1:]
            ],
        }


class FMIMareoSensor(_BaseSensorClass):
    """Expose the latest FMI sea-water level."""

    def update(self) -> None:
        """Update the sea-level sensor state."""
        mareo = self.coordinator.mareo_data
        if mareo is None or not mareo.size():
            self._attr_native_value = None
            self._attr_extra_state_attributes = {}
            return
        values = mareo.get_values()
        self._attr_native_value = values[0].sea_level
        self._attr_extra_state_attributes = {
            ha_const.ATTR_TIME: values[0].time,
            "FORECASTS": [{"time": item.time, "height": item.sea_level} for item in values[1:]],
        }
