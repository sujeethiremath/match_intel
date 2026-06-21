from pydantic import BaseModel
from typing import Optional, Dict, Any


class ExtractionRequest(BaseModel):
    extraction_type: str  # h2h, team_form, venue_stats, injury_news, pitch_report, lineup, squad, tournament_context
    sport_context: str    # e.g. "cricket — T20I" or "cricket — ODI"
    team_a: str
    team_b: str
    raw_text: str         # raw text from Exa search results


class ExtractionResponse(BaseModel):
    success: bool
    extraction_type: str
    data: Optional[Dict[str, Any]] = None
    model_used: Optional[str] = None
    error: Optional[str] = None
