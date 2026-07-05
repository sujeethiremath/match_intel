"""
SearXNG client for match-intel pipeline.
Self-hosted SearXNG running on Lenovo at http://localhost:8080.
Used as the primary search engine for Stage 2 enrichment.
"""
import os
import httpx
from utils.logger import log

SEARXNG_URL = os.getenv("SEARXNG_URL", "http://localhost:8080")
REQUEST_TIMEOUT = None  # No timeout — let SearXNG take as long as needed
DEFAULT_RESULTS = 5


def search(query: str, num_results: int = DEFAULT_RESULTS, engines: str = None) -> str | None:
    """
    Search via SearXNG and return concatenated result snippets.

    Args:
        query: Search query string
        num_results: Number of results to request
        engines: Comma-separated engine names. None = all enabled.

    Returns:
        Concatenated snippet text, or None on failure/empty results
    """
    params = {
        "q": query,
        "format": "json",
        "language": "en",
        "safesearch": "0",
    }
    if engines:
        params["engines"] = engines

    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
            resp = client.get(f"{SEARXNG_URL}/search", params=params)
            resp.raise_for_status()
            data = resp.json()

        results = data.get("results", [])[:num_results]
        if not results:
            log.debug(f"SearXNG returned no results for: {query[:80]}")
            return None

        snippets = []
        for r in results:
            content = r.get("content", "") or r.get("title", "")
            if content:
                snippets.append(content.strip())

        if not snippets:
            return None

        combined = "\n\n".join(snippets)
        log.debug(f"SearXNG got {len(snippets)} snippets for: {query[:60]}")
        return combined

    except httpx.ConnectError:
        log.warning("SearXNG unreachable (connection refused)")
        return None
    except httpx.TimeoutException:
        log.warning(f"SearXNG timed out for query: {query[:60]}")
        return None
    except Exception as e:
        log.error(f"SearXNG search failed for '{query[:60]}': {e}")
        return None


# ─── Named Search Helpers (mirror exa_client interface exactly) ───────────────

def search_cricket_h2h(team_a: str, team_b: str, match_format: str) -> str | None:
    """Search for head-to-head record between two cricket teams."""
    query = f"{team_a} vs {team_b} {match_format} head to head record results history 2024 2025 2026"
    return search(query, num_results=5)


def search_team_form(team: str, match_format: str, gender: str) -> str | None:
    """Search for recent form of a cricket team."""
    gender_tag = "women's" if gender == "women" else ""
    query = f"{team} {gender_tag} {match_format} cricket recent results form 2025 2026"
    return search(query, num_results=5)


def search_venue_stats(venue: str, team_a: str, team_b: str) -> str | None:
    """Search for venue statistics and records."""
    query = f"{venue} cricket ground stats records pitch batting bowling average scores"
    return search(query, num_results=4)


def search_injury_news(team: str, gender: str) -> str | None:
    """Search for injury news and squad updates."""
    gender_tag = "women's" if gender == "women" else ""
    query = f"{team} {gender_tag} cricket team injury news squad updates availability 2026"
    return search(query, num_results=4)


def search_pitch_report(venue: str, match_format: str) -> str | None:
    """Search for pitch report and conditions."""
    query = f"{venue} pitch report {match_format} cricket conditions pace spin bounce 2025 2026"
    return search(query, num_results=4)


def search_tournament_context(competition: str, team_a: str, team_b: str) -> str | None:
    """Search for tournament context and standings."""
    query = f"{competition} {team_a} {team_b} standings points table tournament context 2026"
    return search(query, num_results=4)


def search_confirmed_lineup(team: str, date_str: str, opponent: str) -> str | None:
    """Search for confirmed playing XI / lineup."""
    query = f"{team} playing XI confirmed lineup squad vs {opponent} {date_str} cricket"
    return search(query, num_results=4)


def search_mlc_team_news(team: str) -> str | None:
    """Search for MLC team news and updates."""
    query = f"{team} Major League Cricket MLC 2026 team news squad roster players"
    return search(query, num_results=4)
