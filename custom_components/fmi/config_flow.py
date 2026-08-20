# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Config flow for the Finnish Meteorological Institute integration."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any
from uuid import uuid4
from xml.parsers.expat import ExpatError

import voluptuous as vol
from fmi_weather_client.errors import ClientError, ServerError
from homeassistant import config_entries
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE, CONF_NAME, CONF_OFFSET
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import LocationSelector, TextSelector
from requests.exceptions import RequestException

from . import const
from . import fmi_client as fmi


class CannotConnectError(Exception):
    """Report that FMI could not validate a location."""


class InvalidFMIResponseError(Exception):
    """Report an unexpected but recognized FMI response failure."""


class _ValidatedLocationSelector(LocationSelector):
    """Retain the standard map UI while enforcing a finite WGS84 point."""

    def __call__(self, data: Any) -> dict[str, float]:
        if isinstance(data, Mapping) and any(
            isinstance(data.get(key), bool) for key in (CONF_LATITUDE, CONF_LONGITUDE)
        ):
            raise vol.Invalid("location coordinates must be numbers")
        location = super().__call__(data)
        latitude = location[CONF_LATITUDE]
        longitude = location[CONF_LONGITUDE]
        if not math.isfinite(latitude) or not -90 <= latitude <= 90:
            raise vol.Invalid("latitude must be finite and between -90 and 90")
        if not math.isfinite(longitude) or not -180 <= longitude <= 180:
            raise vol.Invalid("longitude must be finite and between -180 and 180")
        return location


async def validate_user_config(data: dict[str, Any]) -> str:
    """Validate coordinates with the same asynchronous FMI boundary as runtime."""
    try:
        result = await fmi.async_weather_by_coordinates(
            data[CONF_LATITUDE],
            data[CONF_LONGITUDE],
        )
    except (ClientError, RequestException, ServerError) as error:
        raise CannotConnectError from error
    except (
        AttributeError,
        ExpatError,
        IndexError,
        KeyError,
        OverflowError,
        SyntaxError,
        TypeError,
        ValueError,
    ) as error:
        raise InvalidFMIResponseError from error
    if result is None:
        raise CannotConnectError
    weather = result.weather if isinstance(result, fmi.CurrentWeatherResult) else result
    place = weather.place
    if not isinstance(place, str) or not (place := place.strip()):
        raise InvalidFMIResponseError
    return place


def _same_location(entry: config_entries.ConfigEntry, data: dict[str, Any]) -> bool:
    """Return whether an entry already owns the submitted coordinates."""
    return float(entry.data[CONF_LATITUDE]) == float(data[CONF_LATITUDE]) and float(
        entry.data[CONF_LONGITUDE]
    ) == float(data[CONF_LONGITUDE])


def _location_is_configured(
    hass: HomeAssistant,
    data: dict[str, Any],
    *,
    exclude_entry_id: str | None = None,
) -> bool:
    """Check the mutable location rather than the stable config unique ID."""
    return any(
        entry.entry_id != exclude_entry_id and _same_location(entry, data)
        for entry in hass.config_entries.async_entries(const.DOMAIN)
    )


def _location_schema(
    latitude: float,
    longitude: float,
    *,
    include_name: bool,
) -> vol.Schema:
    """Build the setup or reconfigure standard-map form."""
    fields: dict[vol.Marker, Any] = {}
    if include_name:
        fields[vol.Required(CONF_NAME, default=const.DEFAULT_NAME)] = str
    fields[
        vol.Required(
            CONF_LOCATION,
            default={CONF_LATITUDE: latitude, CONF_LONGITUDE: longitude},
        )
    ] = _ValidatedLocationSelector()
    return vol.Schema(fields)


def _coordinate_data(user_input: dict[str, Any]) -> dict[str, Any]:
    """Flatten transient selector data into the existing stored-data shape."""
    location = user_input[CONF_LOCATION]
    data = {
        CONF_LATITUDE: location[CONF_LATITUDE],
        CONF_LONGITUDE: location[CONF_LONGITUDE],
    }
    if CONF_NAME in user_input:
        data[CONF_NAME] = user_input[CONF_NAME]
    return data


def _place_schema(
    *,
    include_name: bool,
    name: str = const.DEFAULT_NAME,
    place: str = "",
) -> vol.Schema:
    """Build a transient FMI place-name form."""
    fields: dict[vol.Marker, Any] = {}
    if include_name:
        fields[vol.Required(CONF_NAME, default=name)] = str
    fields[vol.Required(const.CONF_PLACE_QUERY, default=place)] = TextSelector()
    return vol.Schema(fields)


_OPTION_RANGE_PAIRS = (
    (const.CONF_MIN_TEMP, const.CONF_MAX_TEMP),
    (const.CONF_MIN_HUMIDITY, const.CONF_MAX_HUMIDITY),
    (const.CONF_MIN_WIND_SPEED, const.CONF_MAX_WIND_SPEED),
    (const.CONF_MIN_PRECIPITATION, const.CONF_MAX_PRECIPITATION),
)


def _has_invalid_option_range(data: Mapping[str, Any]) -> bool:
    """Return whether any submitted Best-time minimum exceeds its maximum."""
    return any(
        float(data[minimum]) > float(data[maximum]) for minimum, maximum in _OPTION_RANGE_PAIRS
    )


class FMIConfigFlowHandler(config_entries.ConfigFlow, domain=const.DOMAIN):
    """Handle initial setup and location reconfiguration."""

    VERSION = const.CONFIG_ENTRY_VERSION
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL
    _pending_name: str | None = None
    _place_resolution: fmi.PlaceResolution

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Offer the two complete location-selection paths."""
        _ = user_input
        return self.async_show_menu(
            step_id="user",
            menu_options=["map", "place"],
        )

    async def async_step_map(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Create or move an FMI entry from the standard location selector."""
        errors: dict[str, str] = {}
        if user_input is not None:
            result, errors = await self._async_finish_location(user_input)
            if result is not None:
                return result

        if self.source == config_entries.SOURCE_RECONFIGURE:
            entry = self._get_reconfigure_entry()
            latitude = entry.data[CONF_LATITUDE]
            longitude = entry.data[CONF_LONGITUDE]
        else:
            latitude = self.hass.config.latitude
            longitude = self.hass.config.longitude
        return self.async_show_form(
            step_id="map",
            data_schema=_location_schema(
                latitude,
                longitude,
                include_name=self.source != config_entries.SOURCE_RECONFIGURE,
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Offer both paths while retaining the selected entry's identity."""
        _ = user_input
        return self.async_show_menu(
            step_id="reconfigure",
            menu_options=["map", "place"],
        )

    async def async_step_place(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Resolve a free-text place through FMI before map confirmation."""
        errors: dict[str, str] = {}
        name = const.DEFAULT_NAME
        place_query = ""
        if user_input is not None:
            if CONF_NAME in user_input:
                name = user_input[CONF_NAME]
            place_query = user_input[const.CONF_PLACE_QUERY].strip()
            if not place_query:
                errors[const.CONF_PLACE_QUERY] = "place_required"
            else:
                try:
                    resolution = await fmi.async_resolve_place(place_query)
                except ClientError:
                    errors["base"] = "place_not_found"
                except RequestException, ServerError:
                    errors["base"] = "cannot_connect"
                except (
                    AttributeError,
                    ExpatError,
                    IndexError,
                    KeyError,
                    OverflowError,
                    SyntaxError,
                    TypeError,
                    ValueError,
                ):
                    const.LOGGER.error("Unexpected response resolving an FMI place")
                    errors["base"] = "unknown"
                else:
                    if resolution is None:
                        errors["base"] = "place_not_found"
                    else:
                        self._pending_name = name
                        self._place_resolution = resolution
                        return await self.async_step_place_confirm()

        return self.async_show_form(
            step_id="place",
            data_schema=_place_schema(
                include_name=self.source != config_entries.SOURCE_RECONFIGURE,
                name=name,
                place=place_query,
            ),
            errors=errors,
        )

    async def async_step_place_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Confirm or adjust an FMI-resolved point before the common write boundary."""
        resolution = self._place_resolution
        errors: dict[str, str] = {}
        if user_input is not None:
            final_input = dict(user_input)
            if self.source != config_entries.SOURCE_RECONFIGURE:
                final_input[CONF_NAME] = self._pending_name or const.DEFAULT_NAME
            result, errors = await self._async_finish_location(final_input)
            if result is not None:
                return result

        return self.async_show_form(
            step_id="place_confirm",
            data_schema=_location_schema(
                resolution.latitude,
                resolution.longitude,
                include_name=False,
            ),
            errors=errors,
            description_placeholders={"place": resolution.place},
        )

    async def _async_finish_location(
        self,
        user_input: dict[str, Any],
    ) -> tuple[config_entries.ConfigFlowResult | None, dict[str, str]]:
        """Validate and persist one normalized final point for either path."""
        data = _coordinate_data(user_input)
        entry = (
            self._get_reconfigure_entry()
            if self.source == config_entries.SOURCE_RECONFIGURE
            else None
        )
        exclude_entry_id = entry.entry_id if entry is not None else None
        if _location_is_configured(
            self.hass,
            data,
            exclude_entry_id=exclude_entry_id,
        ):
            return self.async_abort(reason="already_configured"), {}
        try:
            place = await validate_user_config(data)
        except CannotConnectError:
            return None, {"base": "cannot_connect"}
        except InvalidFMIResponseError:
            const.LOGGER.error("Unexpected response validating an FMI location")
            return None, {"base": "unknown"}
        if _location_is_configured(
            self.hass,
            data,
            exclude_entry_id=exclude_entry_id,
        ):
            return self.async_abort(reason="already_configured"), {}
        if entry is not None:
            return (
                self.async_update_and_abort(
                    entry,
                    title=place,
                    data_updates={
                        CONF_LATITUDE: data[CONF_LATITUDE],
                        CONF_LONGITUDE: data[CONF_LONGITUDE],
                    },
                ),
                {},
            )

        identity = f"fmi:{uuid4().hex}"
        await self.async_set_unique_id(identity)
        entry_data = dict(data)
        entry_data[const.CONF_ENTITY_IDENTITY] = identity
        return self.async_create_entry(title=place, data=entry_data), {}

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> FMIOptionsFlowHandler:
        """Return the FMI options flow."""
        _ = config_entry
        return FMIOptionsFlowHandler()


class FMIOptionsFlowHandler(config_entries.OptionsFlow):
    """Manage FMI forecast and optional-source settings."""

    @property
    def config_entry(self) -> config_entries.ConfigEntry:
        """Return the config entry linked to this options flow."""
        return self.hass.config_entries.async_get_known_entry(self.handler)

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Open the existing options form."""
        _ = user_input
        return await self.async_step_user()

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Store user-selected FMI options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if not _has_invalid_option_range(user_input):
                return self.async_create_entry(title="FMI Options", data=user_input)
            errors["base"] = "invalid_range"

        values = user_input if user_input is not None else self.config_entry.options
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        const.CONF_FORECAST_DAYS,
                        default=values.get(const.CONF_FORECAST_DAYS, const.DAYS_DEFAULT),
                    ): vol.In(const.DAYS_RANGE),
                    vol.Optional(
                        CONF_OFFSET,
                        default=values.get(
                            CONF_OFFSET,
                            const.FORECAST_OFFSET[0],
                        ),
                    ): vol.In(const.FORECAST_OFFSET),
                    vol.Optional(
                        const.CONF_MIN_HUMIDITY,
                        default=values.get(
                            const.CONF_MIN_HUMIDITY,
                            const.HUMIDITY_MIN_DEFAULT,
                        ),
                    ): vol.In(const.HUMIDITY_RANGE),
                    vol.Optional(
                        const.CONF_MAX_HUMIDITY,
                        default=values.get(
                            const.CONF_MAX_HUMIDITY,
                            const.HUMIDITY_MAX_DEFAULT,
                        ),
                    ): vol.In(const.HUMIDITY_RANGE),
                    vol.Optional(
                        const.CONF_MIN_TEMP,
                        default=values.get(const.CONF_MIN_TEMP, const.TEMP_MIN_DEFAULT),
                    ): vol.In(const.TEMP_RANGE),
                    vol.Optional(
                        const.CONF_MAX_TEMP,
                        default=values.get(const.CONF_MAX_TEMP, const.TEMP_MAX_DEFAULT),
                    ): vol.In(const.TEMP_RANGE),
                    vol.Optional(
                        const.CONF_MIN_WIND_SPEED,
                        default=values.get(
                            const.CONF_MIN_WIND_SPEED,
                            const.WIND_SPEED_MIN_DEFAULT,
                        ),
                    ): vol.In(const.WIND_SPEED),
                    vol.Optional(
                        const.CONF_MAX_WIND_SPEED,
                        default=values.get(
                            const.CONF_MAX_WIND_SPEED,
                            const.WIND_SPEED_MAX_DEFAULT,
                        ),
                    ): vol.In(const.WIND_SPEED),
                    vol.Optional(
                        const.CONF_MIN_PRECIPITATION,
                        default=values.get(
                            const.CONF_MIN_PRECIPITATION,
                            const.PRECIPITATION_MIN_DEFAULT,
                        ),
                    ): cv.small_float,
                    vol.Optional(
                        const.CONF_MAX_PRECIPITATION,
                        default=values.get(
                            const.CONF_MAX_PRECIPITATION,
                            const.PRECIPITATION_MAX_DEFAULT,
                        ),
                    ): cv.small_float,
                    vol.Optional(
                        const.CONF_DAILY_MODE,
                        default=values.get(
                            const.CONF_DAILY_MODE,
                            const.DAILY_MODE_DEFAULT,
                        ),
                    ): cv.boolean,
                    vol.Optional(
                        const.CONF_LIGHTNING,
                        default=values.get(
                            const.CONF_LIGHTNING,
                            const.LIGHTNING_DEFAULT,
                        ),
                    ): cv.boolean,
                    vol.Optional(
                        const.CONF_LIGHTNING_DISTANCE,
                        default=values.get(
                            const.CONF_LIGHTNING_DISTANCE,
                            const.BOUNDING_BOX_HALF_SIDE_KM,
                        ),
                    ): cv.positive_int,
                    vol.Optional(
                        const.CONF_LIGHTNING_MAX_AGE,
                        default=values.get(
                            const.CONF_LIGHTNING_MAX_AGE,
                            const.LIGHTNING_MAX_AGE_DEFAULT_MINUTES,
                        ),
                    ): vol.All(
                        cv.positive_int,
                        vol.Range(
                            min=const.LIGHTNING_MAX_AGE_MIN_MINUTES,
                            max=const.LIGHTNING_MAX_AGE_MAX_MINUTES,
                        ),
                    ),
                    vol.Optional(
                        const.CONF_OBSERVATION_STATION,
                        default=values.get(const.CONF_OBSERVATION_STATION, 0),
                    ): cv.positive_int,
                }
            ),
            errors=errors,
        )
