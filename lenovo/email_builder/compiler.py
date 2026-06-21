import os
import json
import yaml
from datetime import date, datetime, timezone, timedelta
from jinja2 import Environment, FileSystemLoader
from database.queries import get_full_match_data_for_email

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(BASE_DIR, "config.yaml"), "r") as f:
    _cfg = yaml.safe_load(f)

MDT_OFFSET = timedelta(hours=-6)
MDT = timezone(MDT_OFFSET, name="MDT")

FLAG_MAP = {
    # Nations
    "india": "🇮🇳",
    "australia": "🇦🇺",
    "england": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
    "pakistan": "🇵🇰",
    "south africa": "🇿🇦",
    "new zealand": "🇳🇿",
    "west indies": "🌴",
    "sri lanka": "🇱🇰",
    "bangladesh": "🇧🇩",
    "zimbabwe": "🇿🇼",
    "afghanistan": "🇦🇫",
    "ireland": "🇮🇪",
    
    # MLC Teams
    "mi new york": "🗽",
    "los angeles knight riders": "⚔️",
    "seattle orcas": "🐳",
    "washington freedom": "🦅",
    "san francisco unicorns": "🦄",
    "texas super kings": "🦁",
}


def get_flag(team_name: str) -> str:
    """Return the flag emoji for a team."""
    if not team_name:
        return "🌴"
    normalized = team_name.lower().strip()
    for key, flag in FLAG_MAP.items():
        if key in normalized:
            return flag
    return "🌴"


def format_mdt_time(utc_dt) -> str:
    """Format a UTC datetime string or object into MDT timezone string."""
    if not utc_dt:
        return ""
    try:
        # If it's already a datetime object
        if isinstance(utc_dt, datetime):
            dt = utc_dt
        else:
            # Parse from ISO string
            utc_str = str(utc_dt).strip()
            if utc_str.endswith("Z"):
                utc_str = utc_str[:-1] + "+00:00"
            dt = datetime.fromisoformat(utc_str)

        # Convert to MDT
        local_dt = dt.astimezone(MDT)
        return local_dt.strftime("%I:%M %p MDT")
    except Exception as e:
        return str(utc_dt)


def prepare_match_for_template(match: dict) -> dict:
    """Parse JSON strings and attach flag emojis and times for the template."""
    m = dict(match)
    m["flag_a"] = get_flag(m.get("team_a", ""))
    m["flag_b"] = get_flag(m.get("team_b", ""))
    m["match_time_local"] = format_mdt_time(m.get("match_time_utc"))

    json_fields = [
        "strengths_a",
        "strengths_b",
        "weaknesses_a",
        "weaknesses_b",
        "key_decider_factors",
    ]
    for field in json_fields:
        val = m.get(field)
        if isinstance(val, str):
            try:
                m[field] = json.loads(val)
            except Exception:
                m[field] = []
        elif val is None:
            m[field] = []

    return m


def compile_email(today: date) -> tuple[str, int]:
    """
    Compile the briefing email from the database for the given date.
    Returns (rendered_html_string, total_matches_included).
    """
    all_matches = get_full_match_data_for_email(today)
    total_matches = len(all_matches)

    prepared_matches = [prepare_match_for_template(m) for m in all_matches]

    international_men = [
        m for m in prepared_matches
        if m["sport_type"] == "international" and m["gender"] == "men"
    ]
    international_women = [
        m for m in prepared_matches
        if m["sport_type"] == "international" and m["gender"] == "women"
    ]
    mlc_matches = [
        m for m in prepared_matches
        if m["sport_type"] == "mlc"
    ]

    now_mdt = datetime.now(MDT)
    
    # MLC active during configured months
    mlc_cfg = _cfg.get("cricket", {}).get("leagues", {}).get("mlc", {})
    active_months = mlc_cfg.get("active_months", [7])
    show_mlc = (today.month in active_months)

    context = {
        "date": today.strftime("%B %d, %Y"),
        "weekday": today.strftime("%A"),
        "generated_at": now_mdt.strftime("%I:%M %p"),
        "total_matches": total_matches,
        "international_men": international_men,
        "international_women": international_women,
        "mlc_matches": mlc_matches,
        "show_mlc": show_mlc,
    }

    template_dir = os.path.join(os.path.dirname(__file__), "templates")
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template("daily_briefing.html")
    
    return template.render(**context), total_matches