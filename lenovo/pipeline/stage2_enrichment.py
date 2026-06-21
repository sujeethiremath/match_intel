from datetime import date
from utils.logger import log
from utils.mac_mini_client import extract
from database.queries import (
    log_stage_start, log_stage_done, log_stage_failed,
    get_todays_matches, log_raw_data, upsert_processed_data,
)
from scrapers.exa_client import (
    search_cricket_h2h,
    search_team_form,
    search_venue_stats,
    search_injury_news,
    search_pitch_report,
    search_tournament_context,
)
from scrapers.weather_client import get_weather


def _enrich_h2h(match: dict) -> dict | None:
    """Fetch and extract head-to-head data."""
    mid = match["id"]
    team_a, team_b = match["team_a"], match["team_b"]
    fmt = match["match_format"]

    raw = search_cricket_h2h(team_a, team_b, fmt)
    log_raw_data(mid, "exa", "h2h", {"text": raw}, success=raw is not None,
                 error_msg=None if raw else "No Exa results")
    if not raw:
        return None

    sport_ctx = f"cricket {fmt} {match['gender']}"
    extracted = extract("h2h", sport_ctx, raw, team_a, team_b)
    return extracted


def _enrich_team_form(match: dict, team_key: str) -> dict | None:
    """Fetch and extract recent form for one team."""
    mid = match["id"]
    team = match[team_key]
    fmt = match["match_format"]
    gender = match["gender"]

    raw = search_team_form(team, fmt, gender)
    log_raw_data(mid, "exa", f"team_form_{team_key}", {"text": raw},
                 success=raw is not None, error_msg=None if raw else "No Exa results")
    if not raw:
        return None

    sport_ctx = f"cricket {fmt} {gender}"
    extracted = extract("team_form", sport_ctx, raw, match["team_a"], match["team_b"])
    return extracted


def _enrich_venue_stats(match: dict) -> dict | None:
    """Fetch and extract venue statistics."""
    mid = match["id"]
    venue = match.get("venue", "")
    if not venue:
        return None

    raw = search_venue_stats(venue, match["team_a"], match["team_b"])
    log_raw_data(mid, "exa", "venue_stats", {"text": raw},
                 success=raw is not None, error_msg=None if raw else "No Exa results")
    if not raw:
        return None

    sport_ctx = f"cricket {match['match_format']} {match['gender']}"
    extracted = extract("venue_stats", sport_ctx, raw, match["team_a"], match["team_b"])
    return extracted


def _enrich_injury_news(match: dict) -> dict | None:
    """Fetch and extract injury news for both teams combined."""
    mid = match["id"]
    gender = match["gender"]

    raw_a = search_injury_news(match["team_a"], gender)
    raw_b = search_injury_news(match["team_b"], gender)

    combined_raw = ""
    if raw_a:
        combined_raw += f"--- {match['team_a']} ---\n{raw_a}\n\n"
    if raw_b:
        combined_raw += f"--- {match['team_b']} ---\n{raw_b}"

    log_raw_data(mid, "exa", "injury_news", {"text": combined_raw},
                 success=bool(combined_raw.strip()),
                 error_msg=None if combined_raw.strip() else "No injury news found")

    if not combined_raw.strip():
        return None

    sport_ctx = f"cricket {match['match_format']} {gender}"
    extracted = extract("injury_news", sport_ctx, combined_raw, match["team_a"], match["team_b"])
    return extracted


def _enrich_pitch_report(match: dict) -> str | None:
    """Fetch and extract pitch report."""
    mid = match["id"]
    venue = match.get("venue", "")
    if not venue:
        return None

    raw = search_pitch_report(venue, match["match_format"])
    log_raw_data(mid, "exa", "pitch_report", {"text": raw},
                 success=raw is not None, error_msg=None if raw else "No Exa results")
    if not raw:
        return None

    sport_ctx = f"cricket {match['match_format']} {match['gender']}"
    extracted = extract("pitch_report", sport_ctx, raw, match["team_a"], match["team_b"])
    if extracted and isinstance(extracted, dict):
        return extracted.get("pitch_report", extracted.get("summary", str(extracted)))
    return str(extracted) if extracted else None


def _enrich_tournament_context(match: dict) -> dict | None:
    """Fetch and extract tournament context."""
    mid = match["id"]
    competition = match.get("competition", "")
    if not competition:
        return None

    raw = search_tournament_context(competition, match["team_a"], match["team_b"])
    log_raw_data(mid, "exa", "tournament_context", {"text": raw},
                 success=raw is not None, error_msg=None if raw else "No Exa results")
    if not raw:
        return None

    sport_ctx = f"cricket {match['match_format']} {match['gender']}"
    extracted = extract("tournament_context", sport_ctx, raw, match["team_a"], match["team_b"])
    return extracted


def _enrich_weather(match: dict) -> dict | None:
    """Fetch weather data directly from Open-Meteo."""
    mid = match["id"]
    venue = match.get("venue", "")
    match_date_str = str(match["match_date"])

    weather = get_weather(venue, match_date_str)
    log_raw_data(mid, "open-meteo", "weather", weather,
                 success=weather is not None,
                 error_msg=None if weather else "Weather unavailable")
    return weather


def run_stage2(today: date) -> bool:
    """
    Stage 2: Data Enrichment.
    For each match today, run 7-8 independent enrichment tasks.
    Each task has its own error handling — one failure doesn't block others.
    
    Returns True on success, False on failure.
    """
    stage_id = log_stage_start(today, "stage2_enrichment")
    log.info(f"=== Stage 2: Data Enrichment for {today} ===")

    try:
        matches = get_todays_matches(today)
        if not matches:
            log.info("No matches to enrich")
            log_stage_done(stage_id, 0, "No matches found")
            return True

        log.info(f"Enriching {len(matches)} matches")
        enriched_count = 0

        for match in matches:
            mid = match["id"]
            label = f"{match['team_a']} vs {match['team_b']} ({match['match_format']}"
            log.info(f"\n--- Enriching: {label}) ---")

            update_fields = {}

            # 1. H2H
            try:
                h2h = _enrich_h2h(match)
                if h2h:
                    update_fields["h2h_record"] = h2h
                    log.info(f"  [H2H] OK")
                else:
                    log.warning(f"  [H2H] No data")
            except Exception as e:
                log.error(f"  [H2H] Error: {e}")

            # 2. Team A Form
            try:
                form_a = _enrich_team_form(match, "team_a")
                if form_a:
                    update_fields["recent_form_a"] = form_a
                    log.info(f"  [Form A] OK")
                else:
                    log.warning(f"  [Form A] No data")
            except Exception as e:
                log.error(f"  [Form A] Error: {e}")

            # 3. Team B Form
            try:
                form_b = _enrich_team_form(match, "team_b")
                if form_b:
                    update_fields["recent_form_b"] = form_b
                    log.info(f"  [Form B] OK")
                else:
                    log.warning(f"  [Form B] No data")
            except Exception as e:
                log.error(f"  [Form B] Error: {e}")

            # 4. Venue Stats
            try:
                venue = _enrich_venue_stats(match)
                if venue:
                    update_fields["venue_stats"] = venue
                    log.info(f"  [Venue] OK")
                else:
                    log.warning(f"  [Venue] No data")
            except Exception as e:
                log.error(f"  [Venue] Error: {e}")

            # 5. Injury News
            try:
                injuries = _enrich_injury_news(match)
                if injuries:
                    update_fields["injury_news"] = injuries
                    log.info(f"  [Injuries] OK")
                else:
                    log.warning(f"  [Injuries] No data")
            except Exception as e:
                log.error(f"  [Injuries] Error: {e}")

            # 6. Pitch Report
            try:
                pitch = _enrich_pitch_report(match)
                if pitch:
                    update_fields["pitch_report"] = pitch
                    log.info(f"  [Pitch] OK")
                else:
                    log.warning(f"  [Pitch] No data")
            except Exception as e:
                log.error(f"  [Pitch] Error: {e}")

            # 7. Tournament Context
            try:
                context = _enrich_tournament_context(match)
                if context:
                    update_fields["tournament_context"] = context
                    log.info(f"  [Context] OK")
                else:
                    log.warning(f"  [Context] No data")
            except Exception as e:
                log.error(f"  [Context] Error: {e}")

            # 8. Weather (direct, no Mac Mini needed)
            try:
                weather = _enrich_weather(match)
                if weather:
                    update_fields["weather"] = weather
                    log.info(f"  [Weather] OK")
                else:
                    log.warning(f"  [Weather] No data")
            except Exception as e:
                log.error(f"  [Weather] Error: {e}")

            # Save all collected data
            if update_fields:
                try:
                    upsert_processed_data(mid, **update_fields)
                    enriched_count += 1
                    log.info(f"  Saved {len(update_fields)} fields for match {mid}")
                except Exception as e:
                    log.error(f"  Failed to save processed data for match {mid}: {e}")
            else:
                log.warning(f"  No data collected for match {mid}")

        log_stage_done(stage_id, enriched_count, f"Enriched {enriched_count}/{len(matches)} matches")
        log.info(f"Stage 2 complete: {enriched_count}/{len(matches)} matches enriched")
        return True

    except Exception as e:
        log.error(f"Stage 2 failed: {e}")
        log_stage_failed(stage_id, str(e))
        return False
