import httpx
import logging

logger = logging.getLogger(__name__)

# Basic hardcoded coordinates for MVP (We will dynamically geocode venues later)
VENUE_COORDS = {
    "default": {"lat": 39.7392, "lon": -104.9903} # Denver fallback
}

async def get_venue_weather(venue_name: str) -> dict:
    coords = VENUE_COORDS.get(venue_name, VENUE_COORDS["default"])
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": coords["lat"], "longitude": coords["lon"],
        "hourly": "temperature_2m,precipitation_probability,relativehumidity_2m",
        "timezone": "auto"
    }
    
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            res = await client.get(url, params=params)
            res.raise_for_status()
            data = res.json()
            
            # Simple Dew Factor Logic (High humidity = heavy dew)
            humidity = data.get("hourly", {}).get("relativehumidity_2m", [])
            high_humidity = any(h > 80 for h in humidity[:12]) if humidity else False
            
            return {
                "temperature_trend": data.get("hourly", {}).get("temperature_2m", [])[:3],
                "rain_risk": max(data.get("hourly", {}).get("precipitation_probability", [0])[:12]),
                "dew_factor_expected": high_humidity
            }
        except Exception as e:
            logger.error(f"Weather API failed for {venue_name}: {e}")
            return {}