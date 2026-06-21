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

        notes = f"intl={len(intl_fixtures)}, mlc={len(mlc_fixtures)}"
        log_stage_done(stage_id, match_count, notes)
        log.info(f"Stage 1 complete: {match_count} matches upserted")
        return True

    except Exception as e:
        log.error(f"Stage 1 failed: {e}")
        log_stage_failed(stage_id, str(e))
        return False
