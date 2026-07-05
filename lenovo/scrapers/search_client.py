"""
Unified search facade for match-intel pipeline.

Priority order:
  1. SearXNG (self-hosted on Lenovo, free, unlimited)
  2. Exa (paid API, fallback when SearXNG is unavailable)

All Stage 2 enrichment code should import from this module instead of
exa_client or searxng_client directly.
"""
from utils.logger import log
import scrapers.searxng_client as _searxng
import scrapers.exa_client as _exa


def _with_fallback(searxng_fn, exa_fn, *args, **kwargs) -> str | None:
    """
    Try SearXNG first. Fall back to Exa if SearXNG returns None or fails.
    """
    result = searxng_fn(*args, **kwargs)
    if result:
        return result
    log.info("SearXNG returned no results — falling back to Exa")
    return exa_fn(*args, **kwargs)


def search(query: str, num_results: int = 5, **kwargs) -> str | None:
    """Primary search — SearXNG with Exa fallback."""
    result = _searxng.search(query, num_results=num_results)
    if result:
        return result
    log.info(f"SearXNG empty for '{query[:50]}' — trying Exa")
    return _exa.search(query, num_results=num_results)


def search_cricket_h2h(team_a: str, team_b: str, match_format: str) -> str | None:
    return _with_fallback(
        _searxng.search_cricket_h2h, _exa.search_cricket_h2h,
        team_a, team_b, match_format
    )


def search_team_form(team: str, match_format: str, gender: str) -> str | None:
    return _with_fallback(
        _searxng.search_team_form, _exa.search_team_form,
        team, match_format, gender
    )


def search_venue_stats(venue: str, team_a: str, team_b: str) -> str | None:
    return _with_fallback(
        _searxng.search_venue_stats, _exa.search_venue_stats,
        venue, team_a, team_b
    )


def search_injury_news(team: str, gender: str) -> str | None:
    return _with_fallback(
        _searxng.search_injury_news, _exa.search_injury_news,
        team, gender
    )


def search_pitch_report(venue: str, match_format: str) -> str | None:
    return _with_fallback(
        _searxng.search_pitch_report, _exa.search_pitch_report,
        venue, match_format
    )


def search_tournament_context(competition: str, team_a: str, team_b: str) -> str | None:
    return _with_fallback(
        _searxng.search_tournament_context, _exa.search_tournament_context,
        competition, team_a, team_b
    )


def search_confirmed_lineup(team: str, date_str: str, opponent: str) -> str | None:
    return _with_fallback(
        _searxng.search_confirmed_lineup, _exa.search_confirmed_lineup,
        team, date_str, opponent
    )


def search_mlc_team_news(team: str) -> str | None:
    return _with_fallback(
        _searxng.search_mlc_team_news, _exa.search_mlc_team_news,
        team
    )
