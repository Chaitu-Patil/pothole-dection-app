import requests


OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Rough average daily traffic volumes by road type (vehicles/day)
# Used as a fallback when no traffic count data is available
DEFAULT_TRAFFIC = {
    "motorway": 50000,
    "trunk": 30000,
    "primary": 15000,
    "secondary": 8000,
    "tertiary": 3000,
    "residential": 500,
    "unclassified": 300,
    "unknown": 1000,
}

# Speed limits in mph by road type (used as fallback if not tagged)
DEFAULT_SPEED_MPH = {
    "motorway": 65,
    "trunk": 55,
    "primary": 45,
    "secondary": 35,
    "tertiary": 25,
    "residential": 20,
    "unclassified": 20,
    "unknown": 25,
}


def get_road_data(lat: float, lon: float, radius_m: int = 30) -> dict:
    query = f"""
    [out:json][timeout:10];
    way(around:{radius_m},{lat},{lon})[highway];
    out tags 1;
    """

    try:
        response = requests.post(OVERPASS_URL, data={"data": query}, timeout=12)
        response.raise_for_status()
        data = response.json()

        if not data.get("elements"):
            return _fallback_road_data("unknown")

        road = data["elements"][0]["tags"]
        road_type = road.get("highway", "unknown")

        # Parse speed limit if tagged (OSM stores as "50" or "50 mph")
        maxspeed_raw = road.get("maxspeed", "")
        speed_mph = _parse_speed(maxspeed_raw, road_type)

        traffic = DEFAULT_TRAFFIC.get(road_type, DEFAULT_TRAFFIC["unknown"])
        road_name = road.get("name", road_type.replace("_", " ").title())

        return {
            "success": True,
            "road_name": road_name,
            "road_type": road_type,
            "speed_limit_mph": speed_mph,
            "daily_traffic": traffic,
        }

    except requests.exceptions.Timeout:
        return _fallback_road_data("unknown", error="Road data request timed out")
    except Exception as e:
        return _fallback_road_data("unknown", error=str(e))


def _parse_speed(maxspeed_raw: str, road_type: str) -> int:
    if not maxspeed_raw:
        return DEFAULT_SPEED_MPH.get(road_type, 25)
    try:
        # Handle "50 mph" or "80 km/h" formats
        parts = maxspeed_raw.strip().split()
        value = int(parts[0])
        if len(parts) > 1 and "km" in parts[1]:
            value = int(value * 0.621371)  # convert kph to mph
        return value
    except (ValueError, IndexError):
        return DEFAULT_SPEED_MPH.get(road_type, 25)


def _fallback_road_data(road_type: str, error: str = None) -> dict:
    return {
        "success": False,
        "road_type": road_type,
        "speed_limit_mph": DEFAULT_SPEED_MPH[road_type],
        "daily_traffic": DEFAULT_TRAFFIC[road_type],
        "error": error,
    }
