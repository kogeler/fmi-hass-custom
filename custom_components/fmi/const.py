"""Constants for the FMI Weather and Sensor integrations."""

import logging
from datetime import timedelta

LOGGER = logging.getLogger(__package__)

DOMAIN = "fmi"
NAME = "FMI"
MANUFACTURER = "Finnish Meteorological Institute"
CONFIG_ENTRY_VERSION = 2
TIMEOUT_FMI_INTEG_IN_SEC = 40
AUX_HTTP_TOTAL_TIMEOUT_SECONDS = 5
AUX_HTTP_CONNECT_TIMEOUT_SECONDS = 2
AUX_HTTP_READ_TIMEOUT_SECONDS = 3
AUX_HTTP_MAX_PAYLOAD_BYTES = 2 * 1024 * 1024

COORDINATOR = "coordinator"
COORDINATOR_OBSERVATION = "coordinator_observation"
FORECAST_UPDATE_INTERVAL = timedelta(minutes=30)
OBSERVATION_UPDATE_INTERVAL = timedelta(minutes=10)
UNDO_UPDATE_LISTENER = "undo_update_listener"

CONF_FORECAST_DAYS = "forecast_days"
CONF_MIN_HUMIDITY = "min_relative_humidity"
CONF_MAX_HUMIDITY = "max_relative_humidity"
CONF_MIN_TEMP = "min_temperature"
CONF_MAX_TEMP = "max_temperature"
CONF_MIN_WIND_SPEED = "min_wind_speed"
CONF_MAX_WIND_SPEED = "max_wind_speed"
CONF_MIN_PRECIPITATION = "min_precipitation"
CONF_MAX_PRECIPITATION = "max_precipitation"
CONF_DAILY_MODE = "daily_mode"
CONF_LIGHTNING = "lightning_sensor"
CONF_LIGHTNING_DISTANCE = "lightning_radius"
CONF_LIGHTNING_MAX_AGE = "lightning_max_age_minutes"
CONF_OBSERVATION_STATION = "observation_station_id"
CONF_ENTITY_IDENTITY = "entity_identity"

HUMIDITY_RANGE = list(range(1, 101))
HUMIDITY_MIN_DEFAULT = 30
HUMIDITY_MAX_DEFAULT = 70
TEMP_RANGE = list(range(-40, 50))
TEMP_MIN_DEFAULT = 10
TEMP_MAX_DEFAULT = 30
WIND_SPEED = list(range(0, 31))
WIND_SPEED_MIN_DEFAULT = 0
WIND_SPEED_MAX_DEFAULT = 25
DAYS_RANGE = list(range(0, 11))  # 0 to 10 days, 0 = disable forecast
DAYS_DEFAULT = 4  # default to 4 days
PRECIPITATION_MIN_DEFAULT = 0.0
PRECIPITATION_MAX_DEFAULT = 0.2
DAILY_MODE_DEFAULT = False
LIGHTNING_DEFAULT = False
LIGHTNING_MAX_AGE_MIN_MINUTES = 1
LIGHTNING_MAX_AGE_MAX_MINUTES = 24 * 60
LIGHTNING_MAX_AGE_DEFAULT_MINUTES = LIGHTNING_MAX_AGE_MAX_MINUTES

FORECAST_OFFSET = [1, 2, 3, 4, 6, 8, 12, 24]  # Based on API test runs
DEFAULT_NAME = "FMI"

ATTR_DISTANCE = "distance"
ATTR_STRIKES = "strikes"
ATTR_PEAK_CURRENT = "peak_current"
ATTR_CLOUD_COVER = "cloud_cover"
ATTR_ELLIPSE_MAJOR = "ellipse_major"
ATTR_FORECAST = CONF_FORECAST = "forecast"
ATTR_HUMIDITY = "relative_humidity"
ATTR_WIND_SPEED = "wind_speed"
ATTR_PRECIPITATION = "precipitation"

ATTRIBUTION = "Weather Data provided by FMI"

BEST_COND_SYMBOLS = [1, 2, 21, 3, 31, 32, 41, 42, 51, 52, 91, 92]
BEST_CONDITION_AVAIL = "available"
BEST_CONDITION_NOT_AVAIL = "not_available"

# Constants for Lightning strikes
BOUNDING_BOX_HALF_SIDE_KM = 200
LIGHTNING_LIMIT = 5
NOMINATIM_REQUEST_INTERVAL_SECONDS = 15.0
NOMINATIM_TIMEOUT_SECONDS = 3
NOMINATIM_USER_AGENT = "fmi-hass-custom/1.0 (+https://github.com/kogeler/fmi-hass-custom)"
OPENSTREETMAP_ATTRIBUTION = "Address data © OpenStreetMap contributors"

URL_FMI_BASE = (
    "https://opendata.fmi.fi/wfs?service=WFS&version=2.0.0&request=getFeature&storedquery_id="
)

LIGHTNING_QUERY_ID = "fmi::observations::lightning::multipointcoverage"
LIGHTNING_GET_URL = f"{URL_FMI_BASE}{LIGHTNING_QUERY_ID}&timestep=3600&"

MAREO_QUERY_ID = "fmi::forecast::sealevel::point::simple"
MAREO_GET_URL = f"{URL_FMI_BASE}{MAREO_QUERY_ID}&timestep=30&"

# MAREO_OBS_QUERY_ID = "fmi::observations::mareograph::simple"
# MAREO_OBS_GET_URL = f"{URL_FMI_BASE}{MAREO_OBS_QUERY_ID}&fmisid=132310&timestep=30"

# MAREO_SEA_TEMP_QUERY_ID = "fmi::forecast::oaas::sealevel::point::simple"
# MAREO_SEA_TEMP_GET_URL = f"{URL_FMI_BASE}{MAREO_OBS_QUERY_ID}&timestep=30" \
#     "&latlon=60.0,24.0&starttime=2021-04-11T13:24:00Z"
#

# FMI Weather Visibility Constants
FMI_WEATHER_SYMBOL_MAP = {
    0: "clear-night",  # custom value 0 - not defined by FMI
    1: "sunny",  # "Clear",
    2: "partlycloudy",  # "Partially Clear",
    21: "rainy",  # "Light Showers",
    22: "pouring",  # "Showers",
    23: "pouring",  # "Strong Rain Showers",
    3: "cloudy",  # "Cloudy",
    31: "rainy",  # "Weak rains",
    32: "rainy",  # "Rains",
    33: "pouring",  # "Heavy Rains",
    41: "snowy-rainy",  # "Weak Snow",
    42: "cloudy",  # "Cloudy",
    43: "snowy",  # "Strong Snow",
    51: "snowy",  # "Light Snow",
    52: "snowy",  # "Snow",
    53: "snowy",  # "Heavy Snow",
    61: "lightning",  # "Thunderstorms",
    62: "lightning-rainy",  # "Strong Thunderstorms",
    63: "lightning",  # "Thunderstorms",
    64: "lightning-rainy",  # "Strong Thunderstorms",
    71: "rainy",  # "Weak Sleet",
    72: "rainy",  # "Sleet",
    73: "pouring",  # "Heavy Sleet",
    81: "rainy",  # "Light Sleet",
    82: "rainy",  # "Sleet",
    83: "pouring",  # "Heavy Sleet",
    91: "fog",  # "Fog",
    92: "fog",  # "Fog"
}
