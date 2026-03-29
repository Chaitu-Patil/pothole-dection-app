import pvlib
import pandas as pd
from datetime import datetime, timezone


def get_sun_elevation(lat: float, lon: float, timestamp: datetime) -> float:
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    times = pd.DatetimeIndex([timestamp])
    location = pvlib.location.Location(latitude=lat, longitude=lon)
    solar_position = location.get_solarposition(times)

    elevation = solar_position["elevation"].iloc[0]
    return float(elevation)


def is_lighting_adequate(elevation: float) -> bool:
    return 20.0 <= elevation <= 70.0
