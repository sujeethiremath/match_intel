import os
import yaml
from datetime import date
from utils.logger import log
from database.queries import log_stage_start, log_stage_done, log_stage_failed, upsert_match
from scrapers.cricapi_client import (
    get_current_matches,
    get_upcoming_matches,
    filter_international_fixtures,
    filter_mlc_fixtures,
    search_series,
    get_series_info,
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(BASE_DIR, "config.yaml"), "r") as f:
    _cfg = yaml.safe_load(f)

TIER1_NATIONS = _cfg["cricket"]["tier1_nations"]
MLC_TEAMS = _cfg["cricket"]["leagues"]["mlc"]["teams"]
MLC_ACTIVE_MONTHS = _cfg["cricket"]["leagues"]["mlc"].get("active_months", [7])

# Major ICC tournament keywords to search for via series search
ICC_TOURNAMENT_KEYWORDS = [
    "ICC Women's T20 World Cup",
    "ICC Men's T20 World Cup",
    "ICC Women's Cricket World Cup",
    "ICC Cricket World Cup",
    "ICC Champions Trophy",
    "ICC World Test Championship",
]


def run_stage1(today: date) -> bool:
    """
    Stage 1: Fixture Discovery.
    Calls CricAPI for current + upcoming matches, filters to international + MLC,
    and upserts each match into the database.
    
    Returns True on success, False on failure.
    """
    stage_id = log_stage_start(today, "stage1_fixtures")
    log.info(f"=== Stage 1: Fixture Discovery for {today} ===")

    try:
        # Fetch from both endpoints for better coverage
        log.info("Fetching current matches from CricAPI...")
        current = get_current_matches()
        log.info(f"Got {len(current)} current matches")

        log.info("Fetching upcoming matches from CricAPI...")
        upcoming = get_upcoming_matches()
        log.info(f"Got {len(upcoming)} upcoming matches")

        # Combine and deduplicate by CricAPI ID
        all_matches = []
        seen_ids = set()
        for m in current + upcoming:
            mid = m.get("id", "")
            if mid and mid not in seen_ids:
                seen_ids.add(mid)
                all_matches.append(m)
            elif not mid:
                all_matches.append(m)

        # Fetch MLC series matches if MLC is active
        if today.month in MLC_ACTIVE_MONTHS:
            log.info("MLC is active. Searching for Major League Cricket series ID...")
            try:
                series_list = search_series("Major League Cricket")
                mlc_series_id = None
                for s in series_list:
                    if str(today.year) in s.get("name", ""):
                        mlc_series_id = s.get("id")
                        log.info(f"Found MLC Series: '{s.get('name')}' (ID: {mlc_series_id})")
                        break
                
                if mlc_series_id:
                    series_data = get_series_info(mlc_series_id)
                    if series_data and "matchList" in series_data:
                        mlc_raw_matches = series_data["matchList"]
                        log.info(f"Retrieved {len(mlc_raw_matches)} matches for MLC series {mlc_series_id}")
                        for m in mlc_raw_matches:
                            mid = m.get("id", "")
                            if mid and mid not in seen_ids:
                                seen_ids.add(mid)
                                all_matches.append(m)
                            elif not mid:
                                all_matches.append(m)
            except Exception as e:
                log.error(f"Failed to fetch MLC series matches: {e}")

        # Fetch ICC tournament matches (Women's T20 WC, Men's T20 WC, etc.)
        log.info("Searching for active ICC tournament series...")
        for keyword in ICC_TOURNAMENT_KEYWORDS:
            try:
                series_list = search_series(keyword)
                for s in series_list:
                    sname = s.get("name", "")
                    if str(today.year) in sname:
                        s_id = s.get("id")
                        log.info(f"Found ICC series: '{sname}' (ID: {s_id})")
                        series_data = get_series_info(s_id)
                        if series_data and "matchList" in series_data:
                            icc_raw = series_data["matchList"]
                            log.info(f"  Retrieved {len(icc_raw)} matches from '{sname}'")
                            for m in icc_raw:
                                mid = m.get("id", "")
                                if mid and mid not in seen_ids:
                                    seen_ids.add(mid)
                                    all_matches.append(m)
                                elif not mid:
                                    all_matches.append(m)
            except Exception as e:
                log.error(f"Failed to fetch ICC series '{keyword}': {e}")

        log.info(f"Combined {len(all_matches)} unique matches to filter")

        # Filter international fixtures
        intl_fixtures = filter_international_fixtures(all_matches, today, TIER1_NATIONS)

        # Filter MLC fixtures (configuration-driven active months)
        mlc_fixtures = filter_mlc_fixtures(all_matches, today, MLC_TEAMS, MLC_ACTIVE_MONTHS)

        all_fixtures = intl_fixtures + mlc_fixtures
        log.info(f"Total fixtures for {today}: {len(all_fixtures)} (intl={len(intl_fixtures)}, mlc={len(mlc_fixtures)})")

        # Upsert each match
        match_count = 0
        for fixture in all_fixtures:
            try:
                match_id = upsert_match(**fixture)
                match_count += 1
                log.info(
                    f"  Upserted: {fixture['team_a']} vs {fixture['team_b']} "
                    f"({fixture['match_format']}, {fixture['gender']}) -> id={match_id}"
                )
            except Exception as e:
                log.error(f"  Failed to upsert {fixture['team_a']} vs {fixture['team_b']}: {e}")

        # --- FALLBACK TO SEARXNG DISCOVERY ---
        if match_count == 0:
            log.warning("No fixtures found via CricAPI. Falling back to SearXNG discovery...")
            search_fixtures = discover_fixtures_via_search(today)
            for fixture in search_fixtures:
                try:
                    f_dict = fixture if isinstance(fixture, dict) else fixture.dict()
                    match_id = upsert_match(**f_dict)
                    match_count += 1
                    log.info(
                        f"  [SearXNG Fallback] Upserted: {f_dict['team_a']} vs {f_dict['team_b']} "
                        f"({f_dict['match_format']}, {f_dict['gender']}) -> id={match_id}"
                    )
                except Exception as e:
                    log.error(f"  Failed to upsert search fixture {fixture}: {e}")

        notes = f"intl={len(intl_fixtures)}, mlc={len(mlc_fixtures)} (fallback_used={match_count > 0 and len(all_fixtures) == 0})"
        log_stage_done(stage_id, match_count, notes)
        log.info(f"Stage 1 complete: {match_count} matches upserted")
        return True

    except Exception as e:
        log.error(f"Stage 1 failed: {e}")
        log_stage_failed(stage_id, str(e))
        return False


def discover_fixtures_via_search(today: date) -> list:
    """
    Search SearXNG for matches on today's date, and call Mac Mini to parse them.
    """
    from scrapers.search_client import search
    from utils.mac_mini_client import parse_fixtures
    
    date_str = today.strftime("%Y-%m-%d")
    queries = [
        f"cricket matches playing today {date_str}",
        f"Major League Cricket matches today {date_str}",
        f"international cricket matches today {date_str}"
    ]
    
    combined_results = []
    for query in queries:
        log.info(f"Searching SearXNG for: '{query}'")
        res = search(query, num_results=6)
        if res:
            combined_results.append(res)
            
    if not combined_results:
        log.warning("No search results returned from SearXNG for today's matches.")
        return []
        
    search_text = "\n\n=== NEXT QUERY RESULT ===\n\n".join(combined_results)
    
    log.info("Sending search snippets to Mac Mini for fixture parsing...")
    parse_result = parse_fixtures(date_str, search_text)
    if not parse_result or not parse_result.get("success"):
        log.error(f"Failed to parse fixtures via Mac Mini: {parse_result.get('error') if parse_result else 'No response'}")
        return []
        
    fixtures = parse_result.get("fixtures", [])
    log.info(f"Mac Mini parsed {len(fixtures)} fixtures from search results")
    return fixtures
