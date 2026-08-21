# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Report privacy-safe contracts from the locked runtime reference packages."""

from __future__ import annotations

from importlib.metadata import version

import fmi_weather_client as fmi
from fmi_weather_client import models
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.weather import (
    ATTR_FORECAST_NATIVE_APPARENT_TEMP,
    ATTR_FORECAST_PRECIPITATION_PROBABILITY,
    Forecast,
)


def main() -> None:
    """Print deterministic package contracts without performing network I/O."""
    parameters = fmi.http._create_params(  # noqa: SLF001
        models.RequestType.FORECAST,
        60,
        1,
        lat=0.0,
        lon=0.0,
    )["parameters"]
    print(f"homeassistant={version('homeassistant')}")
    print(f"fmi-weather-client={version('fmi-weather-client')}")
    print(f"weather_data_fields={','.join(models.WeatherData._fields)}")
    print(f"forecast_parameters={parameters}")
    print(f"forecast_apparent_temperature_key={ATTR_FORECAST_NATIVE_APPARENT_TEMP}")
    print(f"forecast_precipitation_probability_key={ATTR_FORECAST_PRECIPITATION_PROBABILITY}")
    print(
        "forecast_precipitation_probability_type="
        f"{Forecast.__annotations__['precipitation_probability']}"
    )
    print(f"atmospheric_pressure_device_class={SensorDeviceClass.ATMOSPHERIC_PRESSURE.value}")


if __name__ == "__main__":
    main()
