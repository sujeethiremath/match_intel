import os
from datetime import date
from utils.logger import log
from database.queries import log_stage_start, log_stage_done, log_stage_failed
from email_builder.compiler import compile_email


def run_stage5(today: date) -> tuple[str, int, bool]:
    """
    Stage 5: Email Compilation.
    Loads data from DB, compiles Jinja2 HTML briefing.
    Returns (rendered_html, match_count, success_flag).
    """
    stage_id = log_stage_start(today, "stage5_compile")
    log.info(f"=== Stage 5: Email Compilation for {today} ===")

    try:
        html, count = compile_email(today)
        log.info(f"Successfully compiled email with {count} matches.")
        log_stage_done(stage_id, count, f"Compiled email with {count} matches")
        return html, count, True
    except Exception as e:
        error_msg = f"Stage 5 compilation failed: {e}"
        log.exception(error_msg)
        log_stage_failed(stage_id, error_msg)
        return "", 0, False
