import httpx
import logging
from datetime import date

logger = logging.getLogger(__name__)

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
# Core international/qualifier slugs we care about
COMPETITIONS = [
    "fifa.world",           # World Cup
    "fifa.worldq.eu",       # UEFA Qualifiers
    "fifa.worldq.conmebol", # CONMEBOL Qualifiers
    "fifa.worldq.concacaf", # CONCACAF Qualifiers
    "fifa.worldq.afc",      # AFC Qualifiers
]

async def get_todays_fixtures(target_date: date) -> list:
    """Fetches football fixtures from ESPN for our target competitions."""
    # ESPN API format requires YYYYMMDD
    date_str = target_date.isoformat().replace("-", "")
    fixtures = []
    
    async with httpx.AsyncClient(timeout=15) as client:
        for slug in COMPETITIONS:
            url = f"{ESPN_BASE}/{slug}/scoreboard"
            params = {"dates": date_str}
            
            try:
                res = await client.get(url, params=params)
                if res.status_code != 200:
                    continue
                    
                data = res.json()
                events = data.get("events", [])
                
                for event in events:
                    comps = event.get("competitions", [{}])[0]
                    competitors = comps.get("competitors", [])
                    if len(competitors) < 2:
                        continue
                        
                    # ESPN maps home/away, we map Team A/B
                    team_a = competitors[0].get("team", {}).get("displayName", "")
                    team_b = competitors[1].get("team", {}).get("displayName", "")
                    venue = comps.get("venue", {}).get("fullName", "TBC")
                    competition_name = data.get("leagues", [{}])[0].get("name", "International Match")
                    
                    fixtures.append({
                        "team_a": team_a,
                        "team_b": team_b,
                        "competition": competition_name,
                        "gender": "men", # Fallback default for main streams
                        "venue": venue,
                        "match_time_utc": event.get("date"),
                        "match_format": "World Cup / Qualifier" if "world" in slug else "International",
                        "match_status": "PREVIEW"
                    })
            except Exception as e:
                logger.warning(f"ESPN API scrape failed for competition slug {slug}: {e}")
                continue
                
    logger.info(f"ESPN Football found {len(fixtures)} fixtures for {target_date.isoformat()}")
    return fixtures