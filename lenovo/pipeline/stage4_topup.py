import os
import sys
from datetime import date
from utils.logger import log
from utils.timezone import determine_match_status
from database.queries import (
    log_stage_start,
    log_stage_done,
    log_stage_failed,
    get_todays_matches,
    update_match_status,
    get_processed_data,
    upsert_processed_data,
    log_raw_data,
)
from scrapers.cricapi_client import get_match_scorecard
from scrapers.exa_client import search_confirmed_lineup
from utils.mac_mini_client import extract, health_check


def run_stage4(today: date) -> bool:
    stage_id = log_stage_start(today, "stage4_topup")
    log.info(f"=== Stage 4: Top-Up Scrape & Lineup Discovery for {today} ===")

    try:
        matches = get_todays_matches(today)
        if not matches:
            log.info("No matches found for today to top-up.")
            log_stage_done(stage_id, 0, "No matches today")
            return True

        # Check Mac Mini AI Service health for extraction
        ai_available = health_check(retries=2, interval=5)
        if not ai_available:
            log.warning("Mac Mini AI Service unavailable. Lineup extraction will be skipped, but status updates will proceed.")

        matches_processed = 0
        for match in matches:
            mid = match["id"]
            team_a = match["team_a"]
            team_b = match["team_b"]
            cricapi_id = match.get("cricapi_match_id")
            fmt = match["match_format"]
            gender = match["gender"]
            status = match["match_status"]

            log.info(f"Top-up processing for Match {mid}: {team_a} vs {team_b} (Current status: {status})")

            # 1. Update match status from CricAPI scorecard if available
            new_status = status
            if cricapi_id:
                try:
                    log.info(f"Fetching CricAPI scorecard for match ID {cricapi_id}...")
                    scorecard = get_match_scorecard(cricapi_id)
                    if scorecard:
                        log_raw_data(mid, "cricapi", "scorecard", scorecard, success=True)
                        
                        # CricAPI status flags
                        match_started = scorecard.get("matchStarted", False)
                        match_ended = scorecard.get("matchEnded", False)
                        status_info = scorecard.get("status", "").lower()

                        if match_ended or "won by" in status_info or "match drawn" in status_info or "no result" in status_info:
                            new_status = "COMPLETED"
                        elif match_started:
                            new_status = "IN_PROGRESS"
                        else:
                            new_status = "PREVIEW"

                        if new_status != status:
                            log.info(f"Updating status for Match {mid} from {status} to {new_status}")
                            update_match_status(mid, new_status)
                            status = new_status
                    else:
                        log_raw_data(mid, "cricapi", "scorecard", None, success=False, error_msg="No scorecard returned")
                except Exception as e:
                    log.error(f"Failed to fetch/parse scorecard from CricAPI for Match {mid}: {e}")
                    log_raw_data(mid, "cricapi", "scorecard", None, success=False, error_msg=str(e))

            # 2. Search and extract confirmed lineups if AI is available and status is not COMPLETED
            if ai_available and status in ("PREVIEW", "IN_PROGRESS"):
                existing = get_processed_data(mid) or {}
                squad_a = existing.get("squad_a") or {}
                squad_b = existing.get("squad_b") or {}

                sport_ctx = f"cricket {fmt} {gender}"

                # Team A lineup
                log.info(f"Searching confirmed lineup for {team_a}...")
                raw_a = search_confirmed_lineup(team_a, str(today), team_b)
                log_raw_data(mid, "exa", "lineup_a", {"text": raw_a}, success=raw_a is not None)
                if raw_a:
                    extracted_a = extract("lineup", sport_ctx, raw_a, team_a, team_b)
                    if extracted_a and extracted_a.get("success"):
                        data = extracted_a.get("data", {})
                        squad_a["playing_xi"] = data.get("playing_xi", [])
                        squad_a["notable_inclusions"] = data.get("notable_inclusions", [])
                        squad_a["notable_omissions"] = data.get("notable_omissions", [])
                        log.info(f"Extracted confirmed playing XI for {team_a}")
                    else:
                        log.warning(f"Failed to extract lineup for {team_a}")

                # Team B lineup
                log.info(f"Searching confirmed lineup for {team_b}...")
                raw_b = search_confirmed_lineup(team_b, str(today), team_a)
                log_raw_data(mid, "exa", "lineup_b", {"text": raw_b}, success=raw_b is not None)
                if raw_b:
                    extracted_b = extract("lineup", sport_ctx, raw_b, team_a, team_b)
                    if extracted_b and extracted_b.get("success"):
                        data = extracted_b.get("data", {})
                        squad_b["playing_xi"] = data.get("playing_xi", [])
                        squad_b["notable_inclusions"] = data.get("notable_inclusions", [])
                        squad_b["notable_omissions"] = data.get("notable_omissions", [])
                        log.info(f"Extracted confirmed playing XI for {team_b}")
                    else:
                        log.warning(f"Failed to extract lineup for {team_b}")

                # Save updated squads back to database
                upsert_processed_data(
                    match_id=mid,
                    squad_a=squad_a,
                    squad_b=squad_b,
                )

            matches_processed += 1

        log_stage_done(stage_id, matches_processed, f"Topped-up {matches_processed}/{len(matches)} matches")
        return True

    except Exception as e:
        error_msg = f"Stage 4 failed with error: {str(e)}"
        log.exception(error_msg)
        log_stage_failed(stage_id, error_msg)
        return False


if __name__ == "__main__":
    from datetime import date
    run_stage4(date.today())
