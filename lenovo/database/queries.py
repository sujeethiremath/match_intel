import json
from datetime import date, datetime, timezone
from database.connection import DBContext
from utils.logger import log


# ─── Pipeline Run Logging ────────────────────────────────────────────────────

def log_stage_start(run_date: date, stage_name: str) -> int:
    """Insert a new pipeline_runs row with status RUNNING. Returns the row id."""
    with DBContext() as (cur, conn):
        cur.execute(
            """INSERT INTO pipeline_runs (run_date, stage_name, status, started_at)
               VALUES (%s, %s, 'RUNNING', NOW())
               RETURNING id""",
            (run_date, stage_name),
        )
        row_id = cur.fetchone()[0]
        log.debug(f"Pipeline stage '{stage_name}' started, id={row_id}")
        return row_id


def log_stage_done(stage_id: int, matches_processed: int, notes: str = None):
    """Mark a pipeline stage as DONE."""
    with DBContext() as (cur, conn):
        cur.execute(
            """UPDATE pipeline_runs
               SET status = 'DONE', completed_at = NOW(),
                   matches_processed = %s, notes = %s
               WHERE id = %s""",
            (matches_processed, notes, stage_id),
        )
        log.debug(f"Pipeline stage {stage_id} completed ({matches_processed} matches)")


def log_stage_failed(stage_id: int, error_log: str):
    """Mark a pipeline stage as FAILED."""
    with DBContext() as (cur, conn):
        cur.execute(
            """UPDATE pipeline_runs
               SET status = 'FAILED', completed_at = NOW(), error_log = %s
               WHERE id = %s""",
            (error_log, stage_id),
        )
        log.error(f"Pipeline stage {stage_id} failed: {error_log[:200]}")


# ─── Match Operations ────────────────────────────────────────────────────────

def upsert_match(
    sport_type: str,
    gender: str,
    competition: str,
    match_format: str,
    team_a: str,
    team_b: str,
    venue: str,
    match_date: date,
    match_time_utc=None,
    match_status: str = "PREVIEW",
    cricapi_match_id: str = None,
) -> int:
    """Insert or update a match. Returns the match id."""
    with DBContext() as (cur, conn):
        cur.execute(
            """INSERT INTO matches
               (sport_type, gender, competition, match_format,
                team_a, team_b, venue, match_date, match_time_utc,
                match_status, cricapi_match_id)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (team_a, team_b, match_date, match_format, gender)
               DO UPDATE SET
                   venue = COALESCE(EXCLUDED.venue, matches.venue),
                   match_time_utc = COALESCE(EXCLUDED.match_time_utc, matches.match_time_utc),
                   match_status = EXCLUDED.match_status,
                   competition = COALESCE(EXCLUDED.competition, matches.competition),
                   cricapi_match_id = COALESCE(EXCLUDED.cricapi_match_id, matches.cricapi_match_id)
               RETURNING id""",
            (
                sport_type, gender, competition, match_format,
                team_a, team_b, venue, match_date, match_time_utc,
                match_status, cricapi_match_id,
            ),
        )
        match_id = cur.fetchone()[0]
        log.debug(f"Upserted match {match_id}: {team_a} vs {team_b} on {match_date}")
        return match_id


def get_todays_matches(match_date: date) -> list:
    """Get all matches for a given date."""
    with DBContext() as (cur, conn):
        cur.execute(
            """SELECT id, sport_type, gender, competition, match_format,
                      team_a, team_b, venue, match_date, match_time_utc,
                      match_status, cricapi_match_id
               FROM matches
               WHERE match_date = %s
               ORDER BY match_time_utc ASC NULLS LAST""",
            (match_date,),
        )
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        return [dict(zip(columns, row)) for row in rows]


def update_match_status(match_id: int, new_status: str):
    """Update the match_status field."""
    with DBContext() as (cur, conn):
        cur.execute(
            "UPDATE matches SET match_status = %s WHERE id = %s",
            (new_status, match_id),
        )


# ─── Raw Data Logging ────────────────────────────────────────────────────────

def log_raw_data(
    match_id: int,
    source: str,
    data_type: str,
    raw_content,
    success: bool = True,
    error_msg: str = None,
):
    """Log a raw scraped data entry."""
    content_json = raw_content if isinstance(raw_content, dict) else {"text": str(raw_content) if raw_content else None}
    with DBContext() as (cur, conn):
        cur.execute(
            """INSERT INTO raw_scraped_data
               (match_id, source, data_type, raw_content, success, error_msg, fetched_at)
               VALUES (%s, %s, %s, %s, %s, %s, NOW())""",
            (match_id, source, data_type, json.dumps(content_json), success, error_msg),
        )


# ─── Processed Match Data ────────────────────────────────────────────────────

def upsert_processed_data(match_id: int, **kwargs):
    """
    Insert or update processed_match_data for a match.
    Uses COALESCE so existing non-null fields are preserved unless explicitly overwritten.
    
    Allowed kwargs: recent_form_a, recent_form_b, h2h_record, squad_a, squad_b,
                    injury_news, venue_stats, pitch_report, weather,
                    tournament_context, player_stats_a, player_stats_b
    """
    jsonb_fields = [
        "recent_form_a", "recent_form_b", "h2h_record", "squad_a", "squad_b",
        "injury_news", "venue_stats", "weather", "tournament_context",
        "player_stats_a", "player_stats_b",
    ]
    text_fields = ["pitch_report"]

    # Serialize JSONB fields
    params = {}
    for field in jsonb_fields:
        val = kwargs.get(field)
        if val is not None:
            params[field] = json.dumps(val) if isinstance(val, (dict, list)) else val
        else:
            params[field] = None

    for field in text_fields:
        params[field] = kwargs.get(field)

    with DBContext() as (cur, conn):
        cur.execute(
            """INSERT INTO processed_match_data
               (match_id, recent_form_a, recent_form_b, h2h_record,
                squad_a, squad_b, injury_news, venue_stats, pitch_report,
                weather, tournament_context, player_stats_a, player_stats_b, processed_at)
               VALUES (
                   %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
               )
               ON CONFLICT (match_id) DO UPDATE SET
                   recent_form_a     = COALESCE(EXCLUDED.recent_form_a, processed_match_data.recent_form_a),
                   recent_form_b     = COALESCE(EXCLUDED.recent_form_b, processed_match_data.recent_form_b),
                   h2h_record        = COALESCE(EXCLUDED.h2h_record, processed_match_data.h2h_record),
                   squad_a           = COALESCE(EXCLUDED.squad_a, processed_match_data.squad_a),
                   squad_b           = COALESCE(EXCLUDED.squad_b, processed_match_data.squad_b),
                   injury_news       = COALESCE(EXCLUDED.injury_news, processed_match_data.injury_news),
                   venue_stats       = COALESCE(EXCLUDED.venue_stats, processed_match_data.venue_stats),
                   pitch_report      = COALESCE(EXCLUDED.pitch_report, processed_match_data.pitch_report),
                   weather           = COALESCE(EXCLUDED.weather, processed_match_data.weather),
                   tournament_context= COALESCE(EXCLUDED.tournament_context, processed_match_data.tournament_context),
                   player_stats_a    = COALESCE(EXCLUDED.player_stats_a, processed_match_data.player_stats_a),
                   player_stats_b    = COALESCE(EXCLUDED.player_stats_b, processed_match_data.player_stats_b),
                   processed_at      = NOW()""",
            (
                match_id,
                params["recent_form_a"], params["recent_form_b"], params["h2h_record"],
                params["squad_a"], params["squad_b"], params["injury_news"],
                params["venue_stats"], params["pitch_report"], params["weather"],
                params["tournament_context"], params["player_stats_a"], params["player_stats_b"],
            ),
        )
        log.debug(f"Upserted processed data for match {match_id}")


def get_processed_data(match_id: int) -> dict | None:
    """Get processed match data for a specific match."""
    with DBContext() as (cur, conn):
        cur.execute(
            """SELECT recent_form_a, recent_form_b, h2h_record,
                      squad_a, squad_b, injury_news, venue_stats,
                      pitch_report, weather, tournament_context,
                      player_stats_a, player_stats_b, processed_at
               FROM processed_match_data
               WHERE match_id = %s""",
            (match_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        columns = [desc[0] for desc in cur.description]
        return dict(zip(columns, row))


# ─── AI Analysis ──────────────────────────────────────────────────────────────

def save_ai_analysis(
    match_id: int,
    model_used: str,
    strengths_a,
    strengths_b,
    weaknesses_a,
    weaknesses_b,
    key_decider_factors,
    h2h_synthesis: str,
    match_context: str,
    weather_note: str = None,
    predicted_winner: str = None,
    pick_reasoning: str = None,
):
    """Insert or update AI analysis for a match."""
    def to_json(val):
        if val is None:
            return None
        if isinstance(val, (dict, list)):
            return json.dumps(val)
        return val

    with DBContext() as (cur, conn):
        cur.execute(
            """INSERT INTO ai_analysis
               (match_id, model_used, strengths_a, strengths_b,
                weaknesses_a, weaknesses_b, key_decider_factors,
                h2h_synthesis, match_context, weather_note,
                predicted_winner, pick_reasoning,
                analysis_complete, analyzed_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, NOW())
               ON CONFLICT (match_id) DO UPDATE SET
                   model_used          = EXCLUDED.model_used,
                   strengths_a         = EXCLUDED.strengths_a,
                   strengths_b         = EXCLUDED.strengths_b,
                   weaknesses_a        = EXCLUDED.weaknesses_a,
                   weaknesses_b        = EXCLUDED.weaknesses_b,
                   key_decider_factors  = EXCLUDED.key_decider_factors,
                   h2h_synthesis       = EXCLUDED.h2h_synthesis,
                   match_context       = EXCLUDED.match_context,
                   weather_note        = EXCLUDED.weather_note,
                   predicted_winner    = EXCLUDED.predicted_winner,
                   pick_reasoning       = EXCLUDED.pick_reasoning,
                   analysis_complete   = TRUE,
                   analyzed_at         = NOW()""",
            (
                match_id, model_used,
                to_json(strengths_a), to_json(strengths_b),
                to_json(weaknesses_a), to_json(weaknesses_b),
                to_json(key_decider_factors),
                h2h_synthesis, match_context, weather_note,
                predicted_winner, pick_reasoning,
            ),
        )
        log.info(f"Saved AI analysis for match {match_id}")


# ─── Email Operations ────────────────────────────────────────────────────────

def get_full_match_data_for_email(match_date: date) -> list:
    """
    Get all matches with their processed data and analysis for email compilation.
    Returns a list of dicts with all joined data.
    """
    with DBContext() as (cur, conn):
        cur.execute(
            """SELECT
                   m.id, m.sport_type, m.gender, m.competition, m.match_format,
                   m.team_a, m.team_b, m.venue, m.match_date, m.match_time_utc,
                   m.match_status,
                   p.recent_form_a, p.recent_form_b, p.h2h_record,
                   p.squad_a, p.squad_b, p.injury_news, p.venue_stats,
                   p.pitch_report, p.weather, p.tournament_context,
                   p.player_stats_a, p.player_stats_b,
                   a.model_used, a.strengths_a, a.strengths_b,
                   a.weaknesses_a, a.weaknesses_b,
                   a.key_decider_factors, a.h2h_synthesis,
                   a.match_context, a.weather_note,
                   a.predicted_winner, a.pick_reasoning,
                   COALESCE(a.analysis_complete, false) as analysis_complete
               FROM matches m
               LEFT JOIN processed_match_data p ON m.id = p.match_id
               LEFT JOIN ai_analysis a ON m.id = a.match_id
               WHERE m.match_date = %s
               ORDER BY m.match_time_utc ASC NULLS LAST""",
            (match_date,),
        )
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        return [dict(zip(columns, row)) for row in rows]


def create_email_log(run_date: date, recipient: str) -> int:
    """Create a pending email log entry. Returns the log id."""
    with DBContext() as (cur, conn):
        cur.execute(
            """INSERT INTO email_log (run_date, recipient, status)
               VALUES (%s, %s, 'PENDING')
               RETURNING id""",
            (run_date, recipient),
        )
        return cur.fetchone()[0]


def mark_email_sent(log_id: int, matches_included: int, html_snapshot: str = None):
    """Mark an email log entry as SENT."""
    with DBContext() as (cur, conn):
        cur.execute(
            """UPDATE email_log
               SET status = 'SENT', sent_at = NOW(),
                   matches_included = %s, html_snapshot = %s
               WHERE id = %s""",
            (matches_included, html_snapshot, log_id),
        )


def mark_email_failed(log_id: int, error: str):
    """Mark an email log entry as FAILED."""
    with DBContext() as (cur, conn):
        cur.execute(
            """UPDATE email_log
               SET status = 'FAILED', error_message = %s
               WHERE id = %s""",
            (error, log_id),
        )
