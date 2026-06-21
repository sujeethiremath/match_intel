"""
Analyzer service — 3-pass deep match analysis using oMLX.
Uses Qwen2.5-14B-Instruct-4bit with temperature 0.3-0.35 for nuanced analysis.

Pass 1: Analyze Team A in isolation
Pass 2: Analyze Team B in isolation  
Pass 3: Synthesis — key deciders, H2H synthesis, match context, weather note
"""
from openai import AsyncOpenAI
import json
import re
import logging
from models.analyze import AnalysisRequest, AnalysisResponse, StrengthWeakness

logger = logging.getLogger("match-intel.analyzer")

# oMLX local server
client = AsyncOpenAI(base_url="http://localhost:8000/v1", api_key="1234")
MODEL = "Qwen2.5-14B-Instruct-4bit"


def _strip_markdown_fences(text: str) -> str:
    """Remove ```json ... ``` fences from LLM output."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n", 1)
        if len(lines) > 1:
            text = lines[1]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    return text.strip()


def _parse_json(raw_text: str) -> dict:
    """Parse JSON from LLM response with robust fallback."""
    cleaned = _strip_markdown_fences(raw_text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    match = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    raise ValueError(f"Could not parse JSON: {cleaned[:300]}...")


def _format_data_section(label: str, data) -> str:
    """Format enrichment data into a readable text section for the prompt."""
    if data is None:
        return f"\n{label}: No data available."
    if isinstance(data, str):
        return f"\n{label}:\n{data}"
    return f"\n{label}:\n{json.dumps(data, indent=2, default=str)}"


def _build_team_context(request: AnalysisRequest, team: str, is_team_a: bool) -> str:
    """Build the context string for a single team analysis pass."""
    form = request.recent_form_a if is_team_a else request.recent_form_b
    squad = request.squad_a if is_team_a else request.squad_b
    stats = request.player_stats_a if is_team_a else request.player_stats_b
    opponent = request.team_b if is_team_a else request.team_a

    parts = [
        f"Match: {request.team_a} vs {request.team_b}",
        f"Format: {request.match_format} | Competition: {request.competition}",
        f"Gender: {request.gender} | Venue: {request.venue or 'TBC'}",
        f"Match Status: {request.match_status}",
        f"\nYou are analyzing: {team} (opponent: {opponent})",
    ]

    parts.append(_format_data_section(f"{team} Recent Form", form))
    parts.append(_format_data_section(f"{team} Squad", squad))
    parts.append(_format_data_section(f"{team} Player Stats", stats))
    parts.append(_format_data_section("Venue Statistics", request.venue_stats))
    parts.append(_format_data_section("Pitch Report", request.pitch_report))
    parts.append(_format_data_section("Injury News", request.injury_news))

    return "\n".join(parts)


async def _run_team_pass(team: str, opponent: str, context: str, match_format: str) -> dict:
    """Run a single team analysis pass (Pass 1 or Pass 2)."""
    system_prompt = f"""You are an elite cricket analyst. Analyze ONLY {team}'s position in this {match_format} match against {opponent}.

RULES:
1. Provide EXACTLY 5 strengths and EXACTLY 5 weaknesses.
2. Every point MUST reference a specific player name, stat, or observable pattern.
3. NO generic statements like "experienced squad" or "good batting lineup".
4. Every point must be relevant to THIS specific match (this opponent, this venue, this format).
5. Weaknesses must be HONEST — do not downplay real vulnerabilities.
6. Each evidence note should cite a specific stat, recent performance, or matchup.
7. You MUST write out all 10 points (5 strengths and 5 weaknesses) in full. Do NOT use placeholders, do NOT use ellipses or "...", and do NOT truncate the JSON list.

Return ONLY a valid JSON object with this exact structure:
{{
  "strengths": [
    {{"point": "strength description here", "evidence": "specific stat or evidence here"}},
    {{"point": "strength description here", "evidence": "specific stat or evidence here"}},
    {{"point": "strength description here", "evidence": "specific stat or evidence here"}},
    {{"point": "strength description here", "evidence": "specific stat or evidence here"}},
    {{"point": "strength description here", "evidence": "specific stat or evidence here"}}
  ],
  "weaknesses": [
    {{"point": "weakness description here", "evidence": "specific stat or evidence here"}},
    {{"point": "weakness description here", "evidence": "specific stat or evidence here"}},
    {{"point": "weakness description here", "evidence": "specific stat or evidence here"}},
    {{"point": "weakness description here", "evidence": "specific stat or evidence here"}},
    {{"point": "weakness description here", "evidence": "specific stat or evidence here"}}
  ]
}}"""

    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": context}
        ],
        temperature=0.3,
        max_tokens=3000
    )

    return _parse_json(response.choices[0].message.content)


async def _run_synthesis_pass(
    request: AnalysisRequest,
    team_a_analysis: dict,
    team_b_analysis: dict
) -> dict:
    """Run Pass 3: Synthesis combining both team analyses."""
    system_prompt = f"""You are an elite cricket analyst performing synthesis for {request.team_a} vs {request.team_b} ({request.match_format}).

Given the independent analyses of both teams, the head-to-head record, weather conditions, and tournament context, identify the specific battlegrounds that will decide this match, choose a predicted winner, and provide reasoning for your prediction. Be concrete and specific.

Return ONLY valid JSON in this exact format:
{{
  "key_decider_factors": [
    "<specific matchup or condition that will decide this match>",
    "<specific matchup or condition>",
    "<specific matchup or condition>",
    "<specific matchup or condition>",
    "<specific matchup or condition>"
  ],
  "h2h_synthesis": "<2-3 sentences connecting the historical H2H record to current form and this specific match context>",
  "match_context": "<2-3 sentences appropriate to match status: PREVIEW=what to watch for; IN_PROGRESS=what has happened and what matters; COMPLETED=what actually decided the match>",
  "weather_note": "<one sentence about dew or rain impact, or null if weather is not a meaningful factor>",
  "predicted_winner": "<name of the team predicted to win: either {request.team_a} or {request.team_b}>",
  "pick_reasoning": "<1-2 sentences of professional reasoning explaining why this team is predicted to win>"
}}"""

    context_parts = [
        f"Match: {request.team_a} vs {request.team_b}",
        f"Format: {request.match_format} | Competition: {request.competition}",
        f"Venue: {request.venue or 'TBC'} | Status: {request.match_status}",
        f"\n{request.team_a} Analysis:",
        json.dumps(team_a_analysis, indent=2),
        f"\n{request.team_b} Analysis:",
        json.dumps(team_b_analysis, indent=2),
        _format_data_section("Head-to-Head Record", request.h2h_record),
        _format_data_section("Weather", request.weather),
        _format_data_section("Tournament Context", request.tournament_context),
    ]

    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "\n".join(context_parts)}
        ],
        temperature=0.35,
        max_tokens=2000
    )

    return _parse_json(response.choices[0].message.content)


def _parse_sw_list(items: list) -> list[StrengthWeakness]:
    """Parse a list of strength/weakness dicts into Pydantic models."""
    result = []
    for item in items[:5]:  # Ensure max 5
        if isinstance(item, dict):
            result.append(StrengthWeakness(
                point=item.get("point", "N/A"),
                evidence=item.get("evidence", "N/A")
            ))
    return result


async def analyze(request: AnalysisRequest) -> AnalysisResponse:
    """
    Run 3-pass deep analysis for a cricket match.
    
    Pass 1: Analyze Team A in isolation (temp 0.3)
    Pass 2: Analyze Team B in isolation (temp 0.3)
    Pass 3: Synthesis with H2H, weather, tournament context (temp 0.35)
    """
    logger.info(f"Starting 3-pass analysis: {request.team_a} vs {request.team_b}")

    try:
        # ── Pass 1: Team A ──────────────────────────────────────────────
        logger.info(f"Pass 1: Analyzing {request.team_a}...")
        team_a_context = _build_team_context(request, request.team_a, is_team_a=True)
        team_a_analysis = await _run_team_pass(
            request.team_a, request.team_b, team_a_context, request.match_format
        )
        logger.info(f"Pass 1 complete: {len(team_a_analysis.get('strengths', []))} strengths, "
                     f"{len(team_a_analysis.get('weaknesses', []))} weaknesses")

        # ── Pass 2: Team B ──────────────────────────────────────────────
        logger.info(f"Pass 2: Analyzing {request.team_b}...")
        team_b_context = _build_team_context(request, request.team_b, is_team_a=False)
        team_b_analysis = await _run_team_pass(
            request.team_b, request.team_a, team_b_context, request.match_format
        )
        logger.info(f"Pass 2 complete: {len(team_b_analysis.get('strengths', []))} strengths, "
                     f"{len(team_b_analysis.get('weaknesses', []))} weaknesses")

        # ── Pass 3: Synthesis ───────────────────────────────────────────
        logger.info("Pass 3: Running synthesis...")
        synthesis = await _run_synthesis_pass(request, team_a_analysis, team_b_analysis)
        logger.info("Pass 3 complete")

        # ── Build response ──────────────────────────────────────────────
        return AnalysisResponse(
            success=True,
            team_a=request.team_a,
            team_b=request.team_b,
            strengths_a=_parse_sw_list(team_a_analysis.get("strengths", [])),
            strengths_b=_parse_sw_list(team_b_analysis.get("strengths", [])),
            weaknesses_a=_parse_sw_list(team_a_analysis.get("weaknesses", [])),
            weaknesses_b=_parse_sw_list(team_b_analysis.get("weaknesses", [])),
            key_decider_factors=synthesis.get("key_decider_factors", [])[:5],
            h2h_synthesis=synthesis.get("h2h_synthesis", ""),
            match_context=synthesis.get("match_context", ""),
            weather_note=synthesis.get("weather_note"),
            predicted_winner=synthesis.get("predicted_winner"),
            pick_reasoning=synthesis.get("pick_reasoning"),
            model_used=MODEL
        )

    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        return AnalysisResponse(
            success=False,
            team_a=request.team_a,
            team_b=request.team_b,
            error=str(e),
            model_used=MODEL
        )