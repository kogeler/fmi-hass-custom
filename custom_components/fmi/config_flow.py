# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Config flow for the Finnish Meteorological Institute integration."""

from __future__ import annotations

from typing import Any
from uuid import uuid4
from xml.etree.ElementTree import ParseError

import voluptuous as vol
from fmi_weather_client.errors import ClientError, ServerError
from homeassistant import config_entries
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME, CONF_OFFSET
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from requests.exceptions import RequestException

from . import const
from . import fmi_client as fmi


class CannotConnectError(Exception):
    """Report that FMI could not validate a location."""


class InvalidFMIResponseError(Exception):
    """Report an unexpected but recognized FMI response failure."""


async def validate_user_config(data: dict[str, Any]) -> str:
    """Validate coordinates with the same asynchronous FMI boundary as runtime."""
    try:
        weather = await fmi.async_weather_by_coordinates(
            data[CONF_LATITUDE],
            data[CONF_LONGITUDE],
        )
    except (ClientError, RequestException, ServerError) as error:
        raise CannotConnectError from error
    except (AttributeError, KeyError, OverflowError, ParseError, TypeError, ValueError) as error:
        raise InvalidFMIResponseError from error
    if weather is None:
        raise CannotConnectError
    return weather.place


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
    """Build the setup or reconfigure coordinate form."""
    fields: dict[vol.Marker, Any] = {}
    if include_name:
        fields[vol.Required(CONF_NAME, default=const.DEFAULT_NAME)] = str
    fields[vol.Required(CONF_LATITUDE, default=latitude)] = cv.latitude
    fields[vol.Required(CONF_LONGITUDE, default=longitude)] = cv.longitude
    return vol.Schema(fields)


class FMIConfigFlowHandler(config_entries.ConfigFlow, domain=const.DOMAIN):
    """Handle initial setup and location reconfiguration."""

    VERSION = const.CONFIG_ENTRY_VERSION
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Create an FMI entry for a validated unique location."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if _location_is_configured(self.hass, user_input):
                return self.async_abort(reason="already_configured")
            try:
                place = await validate_user_config(user_input)
            except CannotConnectError:
                errors["base"] = "cannot_connect"
            except InvalidFMIResponseError:
                const.LOGGER.exception("Unexpected error validating an FMI location")
                errors["base"] = "unknown"
            else:
                if _location_is_configured(self.hass, user_input):
                    return self.async_abort(reason="already_configured")
                identity = f"fmi:{uuid4().hex}"
                await self.async_set_unique_id(identity)
                entry_data = dict(user_input)
                entry_data[const.CONF_ENTITY_IDENTITY] = identity
                return self.async_create_entry(title=place, data=entry_data)

        return self.async_show_form(
            step_id="user",
            data_schema=_location_schema(
                self.hass.config.latitude,
                self.hass.config.longitude,
                include_name=True,
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Move an existing entry while retaining its immutable identity."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            if _location_is_configured(
                self.hass,
                user_input,
                exclude_entry_id=entry.entry_id,
            ):
                return self.async_abort(reason="already_configured")
            try:
                place = await validate_user_config(user_input)
            except CannotConnectError:
                errors["base"] = "cannot_connect"
            except InvalidFMIResponseError:
                const.LOGGER.exception("Unexpected error validating an FMI location")
                errors["base"] = "unknown"
            else:
                return self.async_update_and_abort(
                    entry,
                    title=place,
                    data_updates={
                        CONF_LATITUDE: user_input[CONF_LATITUDE],
                        CONF_LONGITUDE: user_input[CONF_LONGITUDE],
                    },
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_location_schema(
                entry.data[CONF_LATITUDE],
                entry.data[CONF_LONGITUDE],
                include_name=False,
            ),
            errors=errors,
        )

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
        if user_input is not None:
            return self.async_create_entry(title="FMI Options", data=user_input)

        options = self.config_entry.options
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        const.CONF_FORECAST_DAYS,
                        default=options.get(const.CONF_FORECAST_DAYS, const.DAYS_DEFAULT),
                    ): vol.In(const.DAYS_RANGE),
                    vol.Optional(
                        CONF_OFFSET,
                        default=options.get(
                            CONF_OFFSET,
                            const.FORECAST_OFFSET[0],
                        ),
                    ): vol.In(const.FORECAST_OFFSET),
                    vol.Optional(
                        const.CONF_MIN_HUMIDITY,
                        default=options.get(
                            const.CONF_MIN_HUMIDITY,
                            const.HUMIDITY_MIN_DEFAULT,
                        ),
                    ): vol.In(const.HUMIDITY_RANGE),
                    vol.Optional(
                        const.CONF_MAX_HUMIDITY,
                        default=options.get(
                            const.CONF_MAX_HUMIDITY,
                            const.HUMIDITY_MAX_DEFAULT,
                        ),
                    ): vol.In(const.HUMIDITY_RANGE),
                    vol.Optional(
                        const.CONF_MIN_TEMP,
                        default=options.get(const.CONF_MIN_TEMP, const.TEMP_MIN_DEFAULT),
                    ): vol.In(const.TEMP_RANGE),
                    vol.Optional(
                        const.CONF_MAX_TEMP,
                        default=options.get(const.CONF_MAX_TEMP, const.TEMP_MAX_DEFAULT),
                    ): vol.In(const.TEMP_RANGE),
                    vol.Optional(
                        const.CONF_MIN_WIND_SPEED,
                        default=options.get(
                            const.CONF_MIN_WIND_SPEED,
                            const.WIND_SPEED_MIN_DEFAULT,
                        ),
                    ): vol.In(const.WIND_SPEED),
                    vol.Optional(
                        const.CONF_MAX_WIND_SPEED,
                        default=options.get(
                            const.CONF_MAX_WIND_SPEED,
                            const.WIND_SPEED_MAX_DEFAULT,
                        ),
                    ): vol.In(const.WIND_SPEED),
                    vol.Optional(
                        const.CONF_MIN_PRECIPITATION,
                        default=options.get(
                            const.CONF_MIN_PRECIPITATION,
                            const.PRECIPITATION_MIN_DEFAULT,
                        ),
                    ): cv.small_float,
                    vol.Optional(
                        const.CONF_MAX_PRECIPITATION,
                        default=options.get(
                            const.CONF_MAX_PRECIPITATION,
                            const.PRECIPITATION_MAX_DEFAULT,
                        ),
                    ): cv.small_float,
                    vol.Optional(
                        const.CONF_DAILY_MODE,
                        default=options.get(
                            const.CONF_DAILY_MODE,
                            const.DAILY_MODE_DEFAULT,
                        ),
                    ): cv.boolean,
                    vol.Optional(
                        const.CONF_LIGHTNING,
                        default=options.get(
                            const.CONF_LIGHTNING,
                            const.LIGHTNING_DEFAULT,
                        ),
                    ): cv.boolean,
                    vol.Optional(
                        const.CONF_LIGHTNING_DISTANCE,
                        default=options.get(
                            const.CONF_LIGHTNING_DISTANCE,
                            const.BOUNDING_BOX_HALF_SIDE_KM,
                        ),
                    ): cv.positive_int,
                    vol.Optional(
                        const.CONF_OBSERVATION_STATION,
                        default=options.get(const.CONF_OBSERVATION_STATION, 0),
                    ): cv.positive_int,
                }
            ),
        )
