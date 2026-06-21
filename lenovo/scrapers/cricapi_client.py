import os
import httpx
from datetime import date, datetime, timezone
from dotenv import load_dotenv
from utils.logger import log
from utils.timezone import determine_match_status

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

CRICAPI_KEY = os.getenv("CRICAPI_KEY", "")
BASE_URL = "https://api.cricapi.com/v1"
REQUEST_TIMEOUT = 30.0

# Fuzzy name map for tier1 nations
NATION_ALIASES = {
    "india": "India",
    "ind": "India",
    "australia": "Australia",
    "aus": "Australia",
    "england": "England",
    "eng": "England",
    "pakistan": "Pakistan",
    "pak": "Pakistan",
    "south africa": "South Africa",
    "sa": "South Africa",
    "rsa": "South Africa",
    "proteas": "South Africa",
    "new zealand": "New Zealand",
    "nz": "New Zealand",
    "west indies": "West Indies",
    "wi": "West Indies",
    "windies": "West Indies",
    "sri lanka": "Sri Lanka",
    "sl": "Sri Lanka",
    "bangladesh": "Bangladesh",
    "ban": "Bangladesh",
    "zimbabwe": "Zimbabwe",
    "zim": "Zimbabwe",
    "afghanistan": "Afghanistan",
    "afg": "Afghanistan",
    "ireland": "Ireland",
    "ire": "Ireland",
    "india women": "India",
    "australia women": "Australia",
    "england women": "England",
    "pakistan women": "Pakistan",
    "south africa women": "South Africa",
    "new zealand women": "New Zealand",
    "west indies women": "West Indies",
    "sri lanka women": "Sri Lanka",
    "bangladesh women": "Bangladesh",
    "zimbabwe women": "Zimbabwe",
    "afghanistan women": "Afghanistan",
    "ireland women": "Ireland",
}


def _normalize_team(name: str) -> str:
    """Normalize a team name to standard form."""
    if not name:
        return ""
    cleaned = name.strip()
    for suffix in [" Women", " Men", " women", " men"]:
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)]
            break
    lookup = cleaned.lower().strip()
    return NATION_ALIASES.get(lookup, cleaned)


def _is_tier1(team_name: str, tier1_nations: list) -> bool:
    """Check if a team is a tier-1 nation using fuzzy matching."""
    normalized = _normalize_team(team_name)
    return normalized in tier1_nations


def _api_get(endpoint: str, params: dict = None) -> dict | None:
    """Make a GET request to CricAPI."""
    params = params or {}
    params["apikey"] = CRICAPI_KEY
    url = f"{BASE_URL}/{endpoint}"
    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") == "failure":
                log.warning(f"CricAPI {endpoint} returned failure: {data.get('reason', 'unknown')}")
                return None
            return data
    except httpx.TimeoutException:
        log.error(f"CricAPI {endpoint} timed out")
        return None
    except Exception as e:
        log.error(f"CricAPI {endpoint} error: {e}")
        return None


def get_current_matches() -> list:
    """Get currently active matches from CricAPI."""
    data = _api_get("currentMatches")
    if not data:
        return []
    return data.get("data", []) or []


def get_upcoming_matches() -> list:
    """Get upcoming matches from CricAPI."""
    data = _api_get("matches")
    if not data:
        return []
    return data.get("data", []) or []


def get_match_scorecard(match_id: str) -> dict | None:
    """Get match scorecard by CricAPI match ID."""
    data = _api_get("match_scorecard", {"id": match_id})
    if not data:
        return None
    return data.get("data", None)


def get_player_info(player_id: str) -> dict | None:
    """Get player info by CricAPI player ID."""
    data = _api_get("players_info", {"id": player_id})
    if not data:
        return None
    return data.get("data", None)


def get_series_info(series_id: str) -> dict | None:
    """Get series info by CricAPI series ID."""
    data = _api_get("series_info", {"id": series_id})
    if not data:
        return None
    return data.get("data", None)


def search_series(search_query: str) -> list:
    """Search for cricket series matching query."""
    data = _api_get("series", {"search": search_query})
    if not data:
        return []
    return data.get("data", []) or []


def _parse_match_date(match_data: dict) -> date | None:
    """Parse date from CricAPI match data."""
    date_str = match_data.get("date") or match_data.get("dateTimeGMT", "")[:10]
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _detect_gender(match_data: dict) -> str:
    """Detect gender from match data. Defaults to 'men'."""
    name = (match_data.get("name", "") + " " + match_data.get("series", "")).lower()
    if "women" in name or "wodi" in name or "wt20i" in name:
        return "women"
    return "men"


def _detect_format(match_data: dict) -> str | None:
    """Detect match format from CricAPI data."""
    match_type = (match_data.get("matchType", "")).upper()
    name = match_data.get("name", "").upper()
    series = match_data.get("series", "").upper()

    if match_type in ("ODI", "T20I", "T20", "TEST"):
        if match_type == "T20":
            return "T20I"
        return match_type

    combined = name + " " + series
    if "T20I" in combined or "T20 INT" in combined:
        return "T20I"
    if "ODI" in combined:
        return "ODI"
    if "T20" in combined:
        return "T20I"

    return None


def filter_international_fixtures(
    raw_matches: list,
    target_date: date,
    tier1_nations: list,
) -> list:
    """
    Filter CricAPI matches to international ODI/T20I fixtures between tier-1 nations.
    Returns list of dicts ready for upsert_match.
    """
    results = []
    seen = set()

    for m in raw_matches:
        match_date = _parse_match_date(m)
        if match_date != target_date:
            continue

        fmt = _detect_format(m)
        if fmt not in ("ODI", "T20I"):
            continue

        teams = m.get("teams", [])
        if len(teams) < 2:
            team_info = m.get("teamInfo", [])
            teams = [t.get("name", "") for t in team_info] if team_info else []
        if len(teams) < 2:
            continue

        team_a_raw, team_b_raw = teams[0], teams[1]
        team_a = _normalize_team(team_a_raw)
        team_b = _normalize_team(team_b_raw)

        if not (_is_tier1(team_a_raw, tier1_nations) and _is_tier1(team_b_raw, tier1_nations)):
            continue

        gender = _detect_gender(m)
        dedup_key = tuple(sorted([team_a, team_b]) + [str(match_date), fmt, gender])
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        match_time_utc = m.get("dateTimeGMT")
        status = determine_match_status(match_time_utc, fmt)
        competition = m.get("series", "") or m.get("name", "")

        results.append({
            "sport_type": "international",
            "gender": gender,
            "competition": competition,
            "match_format": fmt,
            "team_a": team_a,
            "team_b": team_b,
            "venue": m.get("venue", ""),
            "match_date": match_date,
            "match_time_utc": match_time_utc,
            "match_status": status,
            "cricapi_match_id": m.get("id"),
        })

    log.info(f"Filtered {len(results)} international fixtures for {target_date}")
    return results


def filter_mlc_fixtures(
    raw_matches: list,
    target_date: date,
    mlc_teams: list,
    active_months: list = None,
) -> list:
    """
    Filter CricAPI matches to MLC fixtures. Active during months specified in config.
    Returns list of dicts ready for upsert_match.
    """
    if active_months is None:
        active_months = [7]

    if target_date.month not in active_months:
        log.debug(f"MLC filter skipped — month {target_date.month} not in active months {active_months}")
        return []

    results = []
    seen = set()
    mlc_lower = {t.lower() for t in mlc_teams}

    for m in raw_matches:
        match_date = _parse_match_date(m)
        if match_date != target_date:
            continue

        series = (m.get("series", "") + " " + m.get("name", "")).lower()
        if "major league cricket" not in series and "mlc" not in series:
            continue

        teams = m.get("teams", [])
        if len(teams) < 2:
            team_info = m.get("teamInfo", [])
            teams = [t.get("name", "") for t in team_info] if team_info else []
        if len(teams) < 2:
            continue

        team_a, team_b = teams[0].strip(), teams[1].strip()

        dedup_key = tuple(sorted([team_a, team_b]) + [str(match_date)])
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        match_time_utc = m.get("dateTimeGMT")
        status = determine_match_status(match_time_utc, "MLC T20")
        competition = m.get("series", "Major League Cricket 2026")

        results.append({
            "sport_type": "mlc",
            "gender": "men",
            "competition": competition,
            "match_format": "MLC T20",
            "team_a": team_a,
            "team_b": team_b,
            "venue": m.get("venue", ""),
            "match_date": match_date,
            "match_time_utc": match_time_utc,
            "match_status": status,
            "cricapi_match_id": m.get("id"),
        })

    log.info(f"Filtered {len(results)} MLC fixtures for {target_date}")
    return results
