from datetime import datetime, date, timezone, timedelta

MDT_OFFSET = timedelta(hours=-6)
MDT = timezone(MDT_OFFSET, name="MDT")

# Match duration estimates in hours
FORMAT_DURATIONS = {
    "ODI": 8,
    "T20I": 4,
    "T20": 4,
    "MLC T20": 4,
}


def now_mdt() -> datetime:
    """Current datetime in MDT (UTC-6)."""
    return datetime.now(MDT)


def today_mdt() -> date:
    """Current date in MDT."""
    return now_mdt().date()


def determine_match_status(match_time_utc_str: str, match_format: str) -> str:
    """
    Determine if a match is PREVIEW, IN_PROGRESS, or COMPLETED based on UTC time.
    
    Args:
        match_time_utc_str: ISO format UTC timestamp string, or None
        match_format: e.g. 'ODI', 'T20I', 'MLC T20'
    
    Returns:
        One of 'PREVIEW', 'IN_PROGRESS', 'COMPLETED'
    """
    if not match_time_utc_str:
        return "PREVIEW"

    try:
        if isinstance(match_time_utc_str, datetime):
            match_utc = match_time_utc_str
            if match_utc.tzinfo is None:
                match_utc = match_utc.replace(tzinfo=timezone.utc)
        else:
            match_time_utc_str = str(match_time_utc_str).strip()
            if match_time_utc_str.endswith("Z"):
                match_time_utc_str = match_time_utc_str[:-1] + "+00:00"
            match_utc = datetime.fromisoformat(match_time_utc_str)
            if match_utc.tzinfo is None:
                match_utc = match_utc.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return "PREVIEW"

    now_utc = datetime.now(timezone.utc)
    duration_hrs = FORMAT_DURATIONS.get(match_format, 4)
    match_end_est = match_utc + timedelta(hours=duration_hrs)

    if now_utc < match_utc:
        return "PREVIEW"
    elif now_utc < match_end_est:
        return "IN_PROGRESS"
    else:
        return "COMPLETED"


def format_mdt_time(utc_datetime) -> str:
    """
    Convert a UTC datetime to a human-readable MDT string.
    
    Args:
        utc_datetime: datetime object (timezone-aware or naive UTC) or ISO string
    
    Returns:
        Formatted string like '2:30 PM MDT' or 'TBD' if conversion fails
    """
    if not utc_datetime:
        return "TBD"

    try:
        if isinstance(utc_datetime, str):
            utc_str = utc_datetime.strip()
            if utc_str.endswith("Z"):
                utc_str = utc_str[:-1] + "+00:00"
            utc_datetime = datetime.fromisoformat(utc_str)

        if utc_datetime.tzinfo is None:
            utc_datetime = utc_datetime.replace(tzinfo=timezone.utc)

        mdt_time = utc_datetime.astimezone(MDT)
        return mdt_time.strftime("%-I:%M %p MDT")
    except (ValueError, TypeError, AttributeError):
        return "TBD"
