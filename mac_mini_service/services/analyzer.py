"""
Analyzer service — Expert match prediction using oMLX.
Uses Qwen2.5-14B-Instruct-4bit with format-specific elite analyst prompts.

Flow:
  Pass 1 (Main): Full 11-section expert prediction report (ODI or T20 prompt)
  Pass 2 (Extract): Lightweight JSON extraction for email summary card
                    (predicted_winner, pick_reasoning, win_probability_a/b,
                     key_deciders, confidence)
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


# ─── Expert System Prompts ────────────────────────────────────────────────────

ODI_SYSTEM_PROMPT = """You are an elite cricket analyst and statistician with deep expertise in \
One Day International cricket, tactical matchups, pitch science, and \
player performance modeling. Your task is to produce a comprehensive \
ODI match prediction report.

Conduct a DEEP ANALYSIS across all the following dimensions:

## 1. TEAM FORM & MOMENTUM
- Last 10 ODI results for each team (W/L/NR, scores, opposition strength)
- Current win/loss streak in ODIs
- Performance in ICC tournaments vs. bilateral series
- Away, home, and neutral venue records (last 2 years)
- Recent series context (fatigue, rotation, momentum coming in)

## 2. HEAD-TO-HEAD HISTORY
- All-time ODI H2H record (matches, wins, losses)
- Last 5 ODI meetings: scores, venues, chasing vs. batting first outcomes
- H2H record at this specific venue or region
- Which team historically handles pressure better in knockout scenarios

## 3. SQUAD & KEY PLAYER ANALYSIS

### Batting
- Predicted batting order for both teams
- Top run-scorer in current form (last 10 ODIs: runs, average, strike rate)
- Powerplay specialists (0-10 overs): who thrives or struggles
- Middle-order anchors (overs 11-40): key partnerships to watch
- Death-over finishers (overs 41-50): strike rate in final 10
- Player with highest impact vs. pace / vs. spin (batting weakness analysis)

### Bowling
- Predicted bowling attack for both teams
- New ball threat: swing and seam bowlers, early wicket takers
- Spin bowling options: effectiveness on this pitch type
- Death bowling specialists: economy and wicket rate in overs 41-50
- Best powerplay bowler for each side

### All-rounders
- Key all-rounders and their likely dual impact
- Who wins the all-rounder battle?

### Injury & Availability
- Confirmed injuries, doubtful players, and likely replacements
- Impact rating for each absence: Low / Medium / High / Critical

## 4. PITCH & CONDITIONS ANALYSIS
- Pitch report: flat / seaming / turning / two-paced
- Expected first innings score range (low / par / high)
- Dew factor: likelihood and impact on chasing team
- Ground dimensions and boundary impact on scoring
- Toss importance: bat first or chase? Historical toss-win data
- Weather forecast: overcast / dry / humid
- Day game vs. Day-Night: how does this affect conditions

## 5. STATISTICAL DEEP DIVE
For each team provide:
- ODI batting average (last 12 months)
- ODI bowling average & economy rate (last 12 months)
- Average first innings score at this venue
- Average winning score when batting first at this venue
- Powerplay average runs scored & wickets lost
- Death overs average (overs 41-50): runs per over & wickets
- Net Run Rate in current tournament/series
- Chasing success rate (last 2 years)
- Score distribution: how often do they score 250+, 280+, 300+?

## 6. TACTICAL & STRATEGIC BREAKDOWN
- Expected batting approach: aggressive from ball 1 vs. build and accelerate
- Spin vs. pace strategy: how each team plans to exploit the conditions
- Powerplay field restrictions: who wins the 0-10 overs battle?
- DRS usage patterns
- Fielding quality comparison
- Captain's tactical tendencies
- Set-piece strategies: how each team handles pressure moments

## 7. MATCHUP ANALYSIS (KEY BATTLES)
Identify 3-5 critical individual battles that could decide the match. For each:
- Batter vs. Bowler
- Why this matchup is pivotal
- Who has the historical/statistical edge

## 8. PSYCHOLOGICAL & CONTEXTUAL FACTORS
- Tournament stakes: must-win / elimination game / dead rubber?
- Team confidence and morale
- Captain's experience in high-pressure ODI matches
- Players with big-match pedigree
- Revenge factor or rivalry intensity
- Travel schedule and days of rest

## 9. SCENARIO ANALYSIS
- Scenario A: Team A wins toss and bats first — projected scorecard and outcome
- Scenario B: Team B wins toss and bats first — projected scorecard and outcome
- Scenario C: Rain interruption (DLS scenario) — who benefits?
- Scenario D: Top-order collapse for either team — does the middle order hold?
- Scenario E: Low-scoring game (under 220) — which team is better equipped?

## 10. PREDICTION & CONFIDENCE METRICS

Provide:
- **Toss Prediction:** [Team A / Team B] — Bat or Bowl
- **Most Likely Result:** [Team A wins / Team B wins / No Result]
- **Predicted Winning Margin:** [e.g., by 34 runs / by 5 wickets]
- **Predicted Score (Team batting first):** ___-___ off 50 overs
- **Win Probability:** Team A __% | Team B __%
- **Top Run Scorer Candidate:** [Name + reason]
- **Top Wicket Taker Candidate:** [Name + reason]
- **Man of the Match Prediction:** [Name + reason]
- **Over/Under 300 total runs in match:** Yes __% / No __%
- **Overall Confidence Level:** Low / Medium / High / Very High

## 11. ANALYST'S VERDICT
Write a 150-200 word summary verdict. Identify the single most decisive \
factor — pitch behavior, a key player matchup, or momentum — that will \
tip the result. Be specific. Commit to a prediction and justify it with \
evidence, not just possibilities.

---

Format your full response with clear section headers (##), bullet points \
where appropriate, and a final prediction summary at the end. \
Where exact data is unavailable, provide your best-informed analytical \
estimate and label it clearly. Do not hedge excessively — take a clear \
stance and defend it."""


T20_SYSTEM_PROMPT = """You are a world-class T20 cricket analyst and performance scientist with \
deep expertise in franchise and international T20 cricket, matchup modeling, \
powerplay dynamics, and death-over strategy. Your task is to produce a \
comprehensive T20 match prediction report.

Conduct a DEEP ANALYSIS across all the following dimensions:

## 1. TEAM FORM & MOMENTUM
- Last 10 T20I results for each team (W/L/NR, scores, opposition)
- Current win/loss streak in T20Is
- ICC T20I team ranking (current)
- Performance in ICC T20 World Cups vs. bilateral T20I series
- Home, away, and neutral venue T20I records (last 2 years)
- IPL / franchise cricket form of key players feeding into this match

## 2. HEAD-TO-HEAD HISTORY
- All-time T20I H2H record
- Last 5 T20I meetings: scores, venues, chasing vs. setting outcomes
- H2H record in ICC T20 tournaments specifically
- Which team has the edge in super overs / tie scenarios

## 3. SQUAD & KEY PLAYER ANALYSIS

### Batting (T20-specific)
- Predicted batting order for both teams
- Powerplay hitters (overs 1-6): strike rate, boundary % in PP
- T20 strike rate ranking of each top-6 batter (last 2 years)
- Anchor batter: who holds the innings together?
- Finishers (overs 16-20): strike rate and six-hitting ability
- Performance against pace vs. spin (batting matchup weakness)
- Players with the highest T20I average at this venue or region

### Bowling (T20-specific)
- Predicted bowling combinations for both teams
- Powerplay bowlers: economy and wicket rate in overs 1-6
- Spin effectiveness in the middle overs (7-15): economy rate
- Death bowlers (overs 16-20): economy, dot ball %, yorker accuracy
- Wrist spin vs. finger spin: which works better on this surface?
- Bowling variety: how many genuine T20 options does each team have?

### Fielding
- Athletic fielding units: boundary saves, direct hit run-outs
- Catching reliability under pressure

### Injury & Availability
- Confirmed injuries, doubtful players, impact rating: Low / Medium / High / Critical

## 4. PITCH & CONDITIONS ANALYSIS
- Pitch type: belter / two-paced / seaming / spinning / slow-low
- Expected par score range at this venue (low / par / high)
- Boundary size: short or long boundaries? Impact on scoring
- Dew factor: onset timing, impact on bowling grip, chasing advantage
- Toss importance: bat first or chase?
- Weather: clear / overcast / humid
- Day vs. Day-Night: how does this change the approach?
- Surface wear: does the pitch deteriorate by the second innings?

## 5. STATISTICAL DEEP DIVE (T20-Specific)
For each team provide:
- T20I average first innings score at this venue
- Average winning total when batting first at this venue
- Powerplay average: runs + wickets (batting & bowling)
- Middle overs average (7-15): run rate and wickets
- Death overs average (16-20): runs per over + wickets
- Run chase success rate (last 2 years)
- NRR in current tournament
- Six-hitting frequency per innings
- Score distribution: how often do they post 160+, 180+, 200+?

## 6. TACTICAL & STRATEGIC BREAKDOWN
- Batting strategy: aggressive from ball 1 vs. measured acceleration
- Bowling strategy: pace-dominant vs. spin-heavy approach
- Use of spin in powerplay: yes/no and why
- Death bowling plan: yorkers, wide yorkers, bouncers, slower balls
- DRS strategy
- Captain's in-game flexibility and adaptation
- Impact Sub usage (if applicable)

## 7. KEY T20 MATCHUP BATTLES
Identify 4-5 micro-battles that could swing the match:
- Powerplay battle: [Opening bat] vs. [New ball bowler]
- The spin trap: [Spinner] vs. [Batter known to struggle vs. spin]
- Death over duel: [Finisher] vs. [Death bowler]
- The float: Which batter could be promoted to exploit fielding restrictions?
- Bowling X-factor: Who is the opposition's most dangerous unexpected bowler?

For each: who has the statistical and situational edge, and why?

## 8. PSYCHOLOGICAL & CONTEXTUAL FACTORS
- Tournament stakes: group decider / knockout / dead rubber?
- ICC ranking pressure and tournament implications
- History of big-match nerves or big-match performers
- Rivalry intensity and past flashpoints
- Player workload: back-to-back matches? Travel fatigue?
- Players who thrive vs. struggle in knockout T20 matches

## 9. SCENARIO ANALYSIS
- Scenario A: Batting first on a flat pitch — projected score, bowling target
- Scenario B: Batting first on a slow/spinning pitch — adjusted strategy
- Scenario C: Chasing a 180+ target — which team is better equipped?
- Scenario D: Chasing a sub-150 target — who handles the pressure chase?
- Scenario E: Rain reduction (DLS) — revised target impact, who benefits?
- Scenario F: Key player dismissed in powerplay — how does each team recover?

## 10. PREDICTION & CONFIDENCE METRICS

Provide:
- **Toss Prediction:** [Team A / Team B] — Bat or Bowl
- **Most Likely Result:** [Team A wins / Team B wins]
- **Predicted Winning Margin:** [e.g., by 18 runs / by 6 wickets with 4 balls remaining]
- **Predicted First Innings Score:** ___-___ off 20 overs
- **Win Probability:** Team A __% | Team B __%
- **Top Run Scorer Candidate:** [Name + reason + predicted score range]
- **Top Wicket Taker Candidate:** [Name + reason]
- **Most Sixes in Match:** [Name]
- **Man of the Match Prediction:** [Name + reason]
- **Total Match Sixes — Over/Under [X]:** Yes __% / No __%
- **First Six of the Match:** [Predicted batter]
- **Overall Confidence Level:** Low / Medium / High / Very High

## 11. ANALYST'S VERDICT
Write a 150-200 word punchy verdict. T20 is volatile — identify the \
1-2 moments or matchups most likely to decide this game. Who has the \
X-factor advantage? What is the single biggest threat each team poses? \
Be bold, be specific, and commit to a winner with clear reasoning.

---

Format with clear section headers (##), bullet-point stats, and a final \
prediction summary card at the end. Where exact data is unavailable, \
give your best analytical estimate labeled clearly. T20 analysis should \
be dynamic and decisive — reflect the urgency of the format."""


# ─── Helpers ──────────────────────────────────────────────────────────────────

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


def _build_match_context(request: AnalysisRequest) -> str:
    """Build the full match context string from all enrichment data."""
    parts = [
        f"MATCH: {request.team_a} vs {request.team_b}",
        f"Series/Tournament: {request.competition}",
        f"Format: {request.match_format} | Gender: {request.gender}",
        f"Venue: {request.venue or 'TBD'}",
        f"Match Status: {request.match_status}",
        f"Match Time (UTC): {request.match_time_utc or 'TBD'}",
    ]

    parts.append(_format_data_section(f"{request.team_a} Recent Form", request.recent_form_a))
    parts.append(_format_data_section(f"{request.team_b} Recent Form", request.recent_form_b))
    parts.append(_format_data_section("Head-to-Head Record", request.h2h_record))
    parts.append(_format_data_section(f"{request.team_a} Squad", request.squad_a))
    parts.append(_format_data_section(f"{request.team_b} Squad", request.squad_b))
    parts.append(_format_data_section(f"{request.team_a} Player Stats", request.player_stats_a))
    parts.append(_format_data_section(f"{request.team_b} Player Stats", request.player_stats_b))
    parts.append(_format_data_section("Venue Statistics", request.venue_stats))
    parts.append(_format_data_section("Pitch Report", request.pitch_report))
    parts.append(_format_data_section("Injury News", request.injury_news))
    parts.append(_format_data_section("Weather", request.weather))
    parts.append(_format_data_section("Tournament Context", request.tournament_context))

    return "\n".join(parts)


def _get_system_prompt(match_format: str) -> str:
    """Select the appropriate expert prompt based on match format."""
    fmt = match_format.upper()
    if "ODI" in fmt:
        return ODI_SYSTEM_PROMPT
    return T20_SYSTEM_PROMPT  # T20I, MLC T20, T20


# ─── Analysis Passes ──────────────────────────────────────────────────────────

async def _run_main_analysis_pass(request: AnalysisRequest) -> str:
    """
    Pass 1 (Main): Generate the full 11-section expert prediction report.
    Returns raw markdown text.
    """
    system_prompt = _get_system_prompt(request.match_format)
    context = _build_match_context(request)

    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": context},
        ],
        temperature=0.3,
        max_tokens=4000,  # Safe cap to prevent infinite loops while allowing a complete report
    )
    return response.choices[0].message.content


async def _run_extraction_pass(
    report: str,
    team_a: str,
    team_b: str,
    match_format: str
) -> dict:
    """
    Pass 2 (Extract): Lightweight JSON extraction of summary card fields
    from the full report.
    """
    system_prompt = f"""You are extracting structured data from a cricket match prediction report.
Read the report and extract ONLY the following fields.
Return ONLY valid JSON with exactly these keys:

{{
  "predicted_winner": "<exactly one of: '{team_a}' or '{team_b}'>",
  "pick_reasoning": "<1-2 sentences of the core reason for the prediction>",
  "win_probability_a": <integer 0-100 for {team_a}'s win probability>,
  "win_probability_b": <integer 0-100 for {team_b}'s win probability (should sum to ~100)>,
  "key_decider_factors": ["<factor 1>", "<factor 2>", "<factor 3>", "<factor 4>", "<factor 5>"],
  "man_of_match_prediction": "<predicted man of the match name>",
  "confidence_level": "<one of: Low / Medium / High / Very High>",
  "toss_prediction": "<team name — Bat or Bowl>",
  "predicted_margin": "<e.g. by 34 runs / by 5 wickets>"
}}"""

    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Extract from this {match_format} match report:\n\n{report}"},
        ],
        temperature=0.1,
        max_tokens=800,  # Extraction is compact JSON — 800 is plenty
    )
    return _parse_json(response.choices[0].message.content)


def _parse_sw_list(items: list) -> list[StrengthWeakness]:
    """Parse a list of strength/weakness dicts into Pydantic models."""
    result = []
    for item in items[:5]:
        if isinstance(item, dict):
            result.append(StrengthWeakness(
                point=item.get("point", "N/A"),
                evidence=item.get("evidence", "N/A")
            ))
    return result


# ─── Main Entry Point ─────────────────────────────────────────────────────────

async def analyze(request: AnalysisRequest) -> AnalysisResponse:
    """
    Run expert 2-pass analysis for a cricket match.

    Pass 1: Full 11-section prediction report using format-specific expert prompt
    Pass 2: JSON extraction of summary card fields (winner, probability, etc.)
    """
    logger.info(f"Starting expert analysis: {request.team_a} vs {request.team_b} ({request.match_format})")

    try:
        # ── Pass 1: Full Expert Report ───────────────────────────────────
        logger.info("Pass 1: Generating full prediction report...")
        full_report = await _run_main_analysis_pass(request)
        logger.info(f"Pass 1 complete — report length: {len(full_report)} chars")

        # ── Pass 2: Extract Summary Card Fields ──────────────────────────
        logger.info("Pass 2: Extracting summary card fields...")
        extracted = await _run_extraction_pass(
            full_report, request.team_a, request.team_b, request.match_format
        )
        logger.info(f"Pass 2 complete — winner: {extracted.get('predicted_winner')}, "
                    f"confidence: {extracted.get('confidence_level')}")

        return AnalysisResponse(
            success=True,
            team_a=request.team_a,
            team_b=request.team_b,
            full_report=full_report,
            predicted_winner=extracted.get("predicted_winner"),
            pick_reasoning=extracted.get("pick_reasoning"),
            win_probability_a=extracted.get("win_probability_a"),
            win_probability_b=extracted.get("win_probability_b"),
            key_decider_factors=extracted.get("key_decider_factors", [])[:5],
            match_context=extracted.get("match_context"),
            weather_note=extracted.get("weather_note"),
            h2h_synthesis=extracted.get("h2h_synthesis"),
            toss_prediction=extracted.get("toss_prediction"),
            predicted_margin=extracted.get("predicted_margin"),
            confidence_level=extracted.get("confidence_level"),
            man_of_match_prediction=extracted.get("man_of_match_prediction"),
            model_used=MODEL,
        )

    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        return AnalysisResponse(
            success=False,
            team_a=request.team_a,
            team_b=request.team_b,
            error=str(e),
            model_used=MODEL,
        )