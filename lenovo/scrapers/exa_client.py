import os
from datetime import date
from exa_py import Exa
from dotenv import load_dotenv
from utils.logger import log

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

EXA_API_KEY = os.getenv("EXA_API_KEY", "")

_exa = None


def _get_exa() -> Exa:
    """Lazy-initialize the Exa client."""
    global _exa
    if _exa is None:
        _exa = Exa(api_key=EXA_API_KEY)
    return _exa


def search(query: str, num_results: int = 3, category: str = "news") -> str | None:
    """
    Core Exa search function. Returns concatenated highlights text.
    
    Args:
        query: Search query string
        num_results: Number of results to fetch
        category: Exa search category (default: 'news')
    
    Returns:
        Concatenated highlights text, or None on failure
    """
    try:
        client = _get_exa()
        results = client.search_and_contents(
            query,
            type="auto",
            num_results=num_results,
            category=category,
            contents={"highlights": True},
        )

        highlights = []
        for r in results.results:
            if hasattr(r, "highlights") and r.highlights:
                for h in r.highlights:
                    highlights.append(h.strip())
            elif hasattr(r, "text") and r.text:
                highlights.append(r.text.strip()[:500])

        if not highlights:
            log.debug(f"Exa search returned no highlights for: {query[:80]}")
            return None

        combined = "\n\n".join(highlights)
        log.debug(f"Exa search got {len(highlights)} highlights for: {query[:60]}")
        return combined

    except Exception as e:
        log.error(f"Exa search failed for '{query[:60]}': {e}")
        return None


# ─── Named Search Helpers ────────────────────────────────────────────────────

def search_cricket_h2h(team_a: str, team_b: str, match_format: str) -> str | None:
    """Search for head-to-head record between two cricket teams."""
    query = f"{team_a} vs {team_b} {match_format} head to head record results history 2024 2025 2026"
    return search(query, num_results=4)


def search_team_form(team: str, match_format: str, gender: str) -> str | None:
    """Search for recent form of a cricket team."""
    gender_tag = "women's" if gender == "women" else ""
    query = f"{team} {gender_tag} {match_format} cricket recent results form 2025 2026"
    return search(query, num_results=3)


def search_venue_stats(venue: str, team_a: str, team_b: str) -> str | None:
    """Search for venue statistics and records."""
    query = f"{venue} cricket ground stats records pitch batting bowling average scores"
    return search(query, num_results=3)


def search_injury_news(team: str, gender: str) -> str | None:
    """Search for injury news and squad updates."""
    gender_tag = "women's" if gender == "women" else ""
    query = f"{team} {gender_tag} cricket team injury news squad updates availability 2026"
    return search(query, num_results=3)


def search_pitch_report(venue: str, match_format: str) -> str | None:
    """Search for pitch report and conditions."""
    query = f"{venue} pitch report {match_format} cricket conditions pace spin bounce 2025 2026"
    return search(query, num_results=3)


def search_tournament_context(competition: str, team_a: str, team_b: str) -> str | None:
    """Search for tournament context and standings."""
    query = f"{competition} {team_a} {team_b} standings points table tournament context 2026"
    return search(query, num_results=3)


def search_confirmed_lineup(team: str, date_str: str, opponent: str) -> str | None:
    """Search for confirmed playing XI / lineup."""
    query = f"{team} playing XI confirmed lineup squad vs {opponent} {date_str} cricket"
    return search(query, num_results=3)


def search_mlc_team_news(team: str) -> str | None:
    """Search for MLC team news and updates."""
    query = f"{team} Major League Cricket MLC 2026 team news squad roster players"
    return search(query, num_results=3)
