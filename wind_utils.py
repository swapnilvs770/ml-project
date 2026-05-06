import requests
import pandas as pd


def get_location_coords(location_name: str):
    """Geocode a location name to lat/lon using Open-Meteo Geocoding API."""
    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {
        "name": location_name,
        "count": 1,
        "language": "en",
        "format": "json"
    }
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    if not data.get("results"):
        raise ValueError(f"Location '{location_name}' not found.")

    result = data["results"][0]
    return result["latitude"], result["longitude"], result.get("name", location_name)


def get_wind_forecast(lat: float, lon: float):
    """Fetch hourly wind forecast from Open-Meteo."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ["windspeed_10m", "winddirection_10m", "temperature_2m"],
        "forecast_days": 7,
        "timezone": "auto"
    }
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    hourly = data["hourly"]
    df = pd.DataFrame({
        "time": pd.to_datetime(hourly["time"]),
        "wind_speed_kmh": hourly["windspeed_10m"],
        "wind_direction": hourly["winddirection_10m"],
        "temperature_c": hourly["temperature_2m"]
    })

    # Convert wind speed from km/h to m/s
    df["wind_speed_ms"] = df["wind_speed_kmh"] / 3.6

    return df


def extrapolate_wind_speed(wind_speed_10m_ms: float, hub_height_m: float, alpha: float = 0.14) -> float:
    """
    Extrapolate wind speed from 10m reference height to turbine hub height
    using the wind shear power law: v_h = v_ref * (h / h_ref)^alpha
    """
    if wind_speed_10m_ms <= 0:
        return 0.0
    reference_height = 10.0
    return wind_speed_10m_ms * ((hub_height_m / reference_height) ** alpha)


def calculate_wind_power(wind_speed_ms: float, rated_power_kw: float = 2000) -> float:
    """
    Estimate wind turbine power output using a simplified power curve.
    Models a standard 2MW onshore turbine.
    """
    cut_in = 3.0      # m/s
    rated = 12.0      # m/s
    cut_out = 25.0    # m/s

    if wind_speed_ms < cut_in or wind_speed_ms >= cut_out:
        return 0.0

    if wind_speed_ms >= rated:
        return rated_power_kw

    # Cubic approximation between cut-in and rated speed
    power = rated_power_kw * ((wind_speed_ms**3 - cut_in**3) / (rated**3 - cut_in**3))
    return round(power, 2)
