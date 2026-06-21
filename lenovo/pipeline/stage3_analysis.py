import os
import sys
import asyncio
from datetime import date
from utils.logger import log
from utils.timezone import now_mdt
from database.queries import (
    log_stage_start,
    log_stage_done,
    log_stage_failed,
    get_todays_matches,
    get_processed_data,
    save_ai_analysis,
)
from utils.mac_mini_client import analyze, health_check


async def run_stage3(today: date) -> bool:
    stage_id = log_stage_start(today, "stage3_analysis")
    log.info(f"=== Stage 3: AI Analysis for {today} ===")

    try:
        # First, run a health check on the Mac Mini AI Service
        log.info("Checking Mac Mini AI Service health...")
        if not health_check():
            error_msg = "Mac Mini AI Service health check failed. Skipping analysis."
            log.error(error_msg)
            log_stage_failed(stage_id, error_msg)
            return False

        matches = get_todays_matches(today)
        if not matches:
            log.info("No matches found for today to analyze.")
            log_stage_done(stage_id, 0, "No matches today")
            return True

        matches_processed = 0
        for match in matches:
            mid = match["id"]
            team_a = match["team_a"]
            team_b = match["team_b"]
            log.info(f"Starting analysis for Match {mid}: {team_a} vs {team_b}")

            processed = get_processed_data(mid)
            if not processed:
                log.warning(f"No processed data found for Match {mid} ({team_a} vs {team_b}). Skipping.")
                continue

            # Convert datetime to ISO format string
            match_time_utc_str = None
            if match.get("match_time_utc"):
                match_time_utc_str = match["match_time_utc"].isoformat()

            payload = {
                "match_format": match["match_format"],
                "competition": match["competition"],
                "gender": match["gender"],
                "sport_type": match["sport_type"],
                "team_a": team_a,
                "team_b": team_b,
                "venue": match.get("venue"),
                "match_status": match.get("match_status", "PREVIEW"),
                "match_time_utc": match_time_utc_str,
                "recent_form_a": processed.get("recent_form_a"),
                "recent_form_b": processed.get("recent_form_b"),
                "h2h_record": processed.get("h2h_record"),
                "squad_a": processed.get("squad_a"),
                "squad_b": processed.get("squad_b"),
                "injury_news": processed.get("injury_news"),
                "venue_stats": processed.get("venue_stats"),
                "pitch_report": processed.get("pitch_report"),
                "weather": processed.get("weather"),
                "tournament_context": processed.get("tournament_context"),
                "player_stats_a": processed.get("player_stats_a"),
                "player_stats_b": processed.get("player_stats_b"),
            }

            # Call analyze with 1 retry on failure
            result = None
            for attempt in range(1, 3):
                log.info(f"Calling analyze endpoint for {team_a} vs {team_b} (attempt {attempt}/2)")
                result = analyze(payload)
                if result and result.get("success"):
                    break
                log.warning(f"Attempt {attempt} failed for {team_a} vs {team_b}")
                if attempt == 1:
                    await asyncio.sleep(5)

            if result and result.get("success"):
                save_ai_analysis(
                    match_id=mid,
                    model_used=result.get("model_used", "Qwen2.5-14B-Instruct-4bit"),
                    strengths_a=result.get("strengths_a", []),
                    strengths_b=result.get("strengths_b", []),
                    weaknesses_a=result.get("weaknesses_a", []),
                    weaknesses_b=result.get("weaknesses_b", []),
                    key_decider_factors=result.get("key_decider_factors", []),
                    h2h_synthesis=result.get("h2h_synthesis", ""),
                    match_context=result.get("match_context", ""),
                    weather_note=result.get("weather_note"),
                    predicted_winner=result.get("predicted_winner"),
                    pick_reasoning=result.get("pick_reasoning"),
                )
                log.info(f"Successfully saved AI analysis for Match {mid}: {team_a} vs {team_b}")
                matches_processed += 1
            else:
                log.error(f"Failed to generate analysis for Match {mid} after retry.")

        log_stage_done(stage_id, matches_processed, f"Analyzed {matches_processed}/{len(matches)} matches")
        return True

    except Exception as e:
        error_msg = f"Stage 3 failed with error: {str(e)}"
        log.exception(error_msg)
        log_stage_failed(stage_id, error_msg)
        return False


if __name__ == "__main__":
    from datetime import date
    asyncio.run(run_stage3(date.today()))