from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class StrengthWeakness(BaseModel):
    point: str
    evidence: str


class AnalysisRequest(BaseModel):
    match_format: str           # ODI, T20I, MLC T20
    competition: str
    gender: str                 # men, women
    sport_type: str             # international, MLC
    team_a: str
    team_b: str
    venue: Optional[str] = None
    match_status: str = "PREVIEW"   # PREVIEW, IN_PROGRESS, COMPLETED
    match_time_utc: Optional[str] = None
    recent_form_a: Optional[Any] = None
    recent_form_b: Optional[Any] = None
    h2h_record: Optional[Any] = None
    squad_a: Optional[Any] = None
    squad_b: Optional[Any] = None
    injury_news: Optional[Any] = None
    venue_stats: Optional[Any] = None
    pitch_report: Optional[str] = None
    weather: Optional[Any] = None
    tournament_context: Optional[Any] = None
    player_stats_a: Optional[Any] = None
    player_stats_b: Optional[Any] = None


class AnalysisResponse(BaseModel):
    success: bool
    team_a: str
    team_b: str
    strengths_a: Optional[List[StrengthWeakness]] = None
    strengths_b: Optional[List[StrengthWeakness]] = None
    weaknesses_a: Optional[List[StrengthWeakness]] = None
    weaknesses_b: Optional[List[StrengthWeakness]] = None
    key_decider_factors: Optional[List[str]] = None
    h2h_synthesis: Optional[str] = None
    match_context: Optional[str] = None
    weather_note: Optional[str] = None
    predicted_winner: Optional[str] = None
    pick_reasoning: Optional[str] = None
    model_used: Optional[str] = None
    error: Optional[str] = None