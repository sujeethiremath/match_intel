from pydantic import BaseModel
from typing import List, Optional

class Fixture(BaseModel):
    sport_type: str        # 'international' or 'mlc'
    gender: str            # 'men' or 'women'
    competition: str
    match_format: str      # 'ODI', 'T20I', 'MLC T20'
    team_a: str
    team_b: str
    venue: Optional[str] = None
    match_date: str        # 'YYYY-MM-DD'
    match_time_utc: Optional[str] = None
    cricapi_match_id: str  # e.g. 'searxng-...'

class FixtureExtractionRequest(BaseModel):
    date_str: str
    search_results: str

class FixtureExtractionResponse(BaseModel):
    success: bool
    fixtures: List[Fixture] = []
    error: Optional[str] = None
