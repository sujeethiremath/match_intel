import httpx
import os
import logging
from datetime import date
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

CRICAPI_KEY = os.getenv("CRICAPI_KEY")
CRICAPI_BASE = "https://api.cricapi.com/v1"

async def get_todays_fixtures(target_date: date) -> list:
    """Fetches matches from CricAPI and filters for the target date."""
    target_date_str = target_date.isoformat()
    url = f"{CRICAPI_BASE}/matches"
    params = {"apikey": CRICAPI_KEY, "offset": 0}
    
    fixtures = []
    
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            res = await client.get(url, params=params)
            res.raise_for_status()
            data = res.json()
            
            if data.get("status") != "success":
                logger.error(f"CricAPI Error: {data.get('reason')}")
                return []
                
            matches = data.get("data", [])
            for m in matches:
                # Filter for today's matches
                if target_date_str in str(m.get("date", "")):
                    teams = m.get("teams", [])
                    if len(teams) < 2:
                        continue
                        
                    # Basic tier filtering - we only want international ODI/T20
                    match_type = str(m.get("matchType", "")).upper()
                    if match_type not in ["ODI", "T20", "T20I"]:
                        continue

                    fixtures.append({
                        "team_a": teams[0],
                        "team_b": teams[1],
                        "competition": m.get("series_id", "International Series"),
                        "gender": "women" if "women" in m.get("name", "").lower() else "men",
                        "venue": m.get("venue", "TBC"),
                        "match_time_utc": m.get("dateTimeGMT"),
                        "match_format": match_type,
                        "match_status": "PREVIEW"
                    })
                    
            logger.info(f"CricAPI found {len(fixtures)} international fixtures for {target_date_str}")
            return fixtures
            
        except Exception as e:
            logger.error(f"Failed to fetch fixtures from CricAPI: {e}")
            return []