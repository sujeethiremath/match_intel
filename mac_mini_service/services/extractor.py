"""
Extractor service — structures raw Exa text into clean JSON using oMLX.
Uses Qwen2.5-14B-Instruct-4bit with temperature 0.1 for deterministic extraction.
"""
from openai import AsyncOpenAI
import json
import re
import logging
from models.extract import ExtractionRequest, ExtractionResponse

logger = logging.getLogger("match-intel.extractor")

# oMLX local server
client = AsyncOpenAI(base_url="http://localhost:8000/v1", api_key="1234")
MODEL = "Qwen2.5-14B-Instruct-4bit"
TEMPERATURE = 0.1

# ─── Extraction prompt templates per type ───────────────────────────────────

EXTRACTION_PROMPTS = {
    "h2h": """You are a cricket data extractor. Extract head-to-head records from the text below.
Return ONLY a valid JSON object with this structure:
{{
  "team_a_wins": <integer>,
  "team_b_wins": <integer>,
  "draws_or_no_result": <integer>,
  "total_meetings": <integer>,
  "last_10": [
    {{"winner": "<team name>", "margin": "<e.g. 5 wickets>", "venue": "<venue>", "date": "<date>"}}
  ]
}}
If data is unclear, use best estimates. Return valid JSON only, no markdown.""",

    "team_form": """You are a cricket data extractor. Extract recent team form from the text below.
Return ONLY a valid JSON object with this structure:
{{
  "last_10_results": [
    {{"opponent": "<team>", "result": "won/lost/no result", "margin": "<margin>", "competition": "<series>", "date": "<date>"}}
  ],
  "key_performers": ["<player name> - <role/contribution>"],
  "form_rating": "<excellent/good/average/poor>",
  "win_rate": "<e.g. 7/10>"
}}
Extract as many results as available up to 10. Return valid JSON only, no markdown.""",

    "venue_stats": """You are a cricket data extractor. Extract venue statistics from the text below.
Return ONLY a valid JSON object with this structure:
{{
  "pitch_type": "<pace-friendly/spin-friendly/balanced/flat>",
  "bat_first_win_pct": <number or null>,
  "field_first_win_pct": <number or null>,
  "avg_first_innings_score": <number or null>,
  "highest_score": "<score if available>",
  "notable_records": ["<record description>"]
}}
Return valid JSON only, no markdown.""",

    "injury_news": """You are a cricket data extractor. Extract injury and player availability news from the text below.
Return ONLY a valid JSON object with this structure:
{{
  "injuries": [
    {{"player": "<name>", "team": "<team>", "status": "injured/doubtful/recovered", "details": "<injury description>"}}
  ],
  "doubtful": [
    {{"player": "<name>", "team": "<team>", "reason": "<reason>"}}
  ],
  "suspended": [
    {{"player": "<name>", "team": "<team>", "reason": "<reason>"}}
  ]
}}
Return valid JSON only, no markdown.""",

    "pitch_report": """You are a cricket data extractor. Extract pitch report information from the text below.
Return ONLY a valid JSON object with this structure:
{{
  "expected_behavior": "<description of how the pitch is expected to play>",
  "toss_advantage": "<bat first/field first/neutral>",
  "dew_factor": "<significant/moderate/minimal/none>",
  "pace_vs_spin": "<pace-dominated/spin-dominated/balanced>",
  "curator_notes": "<any direct quotes or notes from the curator>"
}}
Return valid JSON only, no markdown.""",

    "lineup": """You are a cricket data extractor. Extract confirmed playing XI from the text below.
Return ONLY a valid JSON object with this structure:
{{
  "playing_xi": [
    {{"name": "<player name>", "role": "batter/bowler/all-rounder/wicket-keeper", "batting_style": "<right-hand/left-hand>", "bowling_style": "<pace/spin/medium or N/A>"}}
  ],
  "notable_inclusions": ["<description of surprising picks>"],
  "notable_omissions": ["<description of notable players left out>"]
}}
Return valid JSON only, no markdown.""",

    "squad": """You are a cricket data extractor. Extract squad information from the text below.
Return ONLY a valid JSON object with this structure:
{{
  "key_players": [
    {{"name": "<player name>", "role": "batter/bowler/all-rounder/wicket-keeper", "batting_style": "<right-hand/left-hand>", "bowling_style": "<pace/spin/medium or N/A>"}}
  ],
  "captain": "<captain name>",
  "vice_captain": "<vice captain name or null>"
}}
Return valid JSON only, no markdown.""",

    "tournament_context": """You are a cricket data extractor. Extract tournament/series context from the text below.
Return ONLY a valid JSON object with this structure:
{{
  "standings": [
    {{"team": "<team name>", "played": <int>, "won": <int>, "lost": <int>, "points": <int or null>, "nrr": "<net run rate or null>"}}
  ],
  "qualification_scenarios": "<what each team needs to qualify/advance>",
  "match_importance": "<dead rubber/must-win/series decider/etc>",
  "points_table_summary": "<brief summary of the standings>"
}}
Return valid JSON only, no markdown."""
}


def _strip_markdown_fences(text: str) -> str:
    """Remove ```json ... ``` fences from LLM output."""
    text = text.strip()
    if text.startswith("```"):
        # Remove opening fence
        lines = text.split("\n", 1)
        if len(lines) > 1:
            text = lines[1]
        # Remove closing fence
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    return text.strip()


def _parse_json_response(raw_text: str) -> dict:
    """Parse JSON from LLM response, handling various edge cases."""
    cleaned = _strip_markdown_fences(raw_text)

    # Try direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Try finding JSON object in the text
    match = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse JSON from response: {cleaned[:200]}...")


async def extract(request: ExtractionRequest) -> ExtractionResponse:
    """
    Takes raw text from Exa and uses Qwen2.5:14b to structure it into clean JSON.
    """
    extraction_type = request.extraction_type.lower()

    # Get the appropriate prompt template
    system_prompt = EXTRACTION_PROMPTS.get(extraction_type)
    if not system_prompt:
        return ExtractionResponse(
            success=False,
            extraction_type=extraction_type,
            error=f"Unknown extraction type: {extraction_type}"
        )

    # Build the user message with context
    user_message = f"""Sport Context: {request.sport_context}
Team A: {request.team_a}
Team B: {request.team_b}

Raw text to extract from:
---
{request.raw_text[:8000]}
---

Extract the relevant data and return valid JSON only."""

    try:
        logger.info(f"Extracting {extraction_type} for {request.team_a} vs {request.team_b}")

        response = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=TEMPERATURE,
            max_tokens=2000
        )

        raw_output = response.choices[0].message.content
        data = _parse_json_response(raw_output)

        logger.info(f"Successfully extracted {extraction_type}")
        return ExtractionResponse(
            success=True,
            extraction_type=extraction_type,
            data=data,
            model_used=MODEL
        )

    except Exception as e:
        logger.error(f"Extraction failed for {extraction_type}: {e}")
        return ExtractionResponse(
            success=False,
            extraction_type=extraction_type,
            error=str(e),
            model_used=MODEL
        )