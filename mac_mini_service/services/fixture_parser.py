from openai import AsyncOpenAI
import json
import re
import logging
from models.fixture_parser import FixtureExtractionRequest, FixtureExtractionResponse, Fixture

logger = logging.getLogger("match-intel.fixture_parser")

client = AsyncOpenAI(base_url="http://localhost:8000/v1", api_key="1234")
MODEL = "Qwen2.5-14B-Instruct-4bit"
TEMPERATURE = 0.1

def _strip_markdown_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n", 1)
        if len(lines) > 1:
            text = lines[1]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    return text.strip()

def _parse_json_response(raw_text: str) -> list:
    cleaned = _strip_markdown_fences(raw_text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    match = re.search(r'\[.*\]', cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse JSON list from response: {cleaned[:200]}...")

async def parse_fixtures(request: FixtureExtractionRequest) -> FixtureExtractionResponse:
    system_prompt = f"""You are a precise sports data extractor. Your task is to read the provided search snippets and extract all cricket matches scheduled to play on {request.date_str} (MDT timezone).
For each match, extract exactly these fields:
1. team_a (e.g. Seattle Orcas)
2. team_b (e.g. Texas Super Kings)
3. match_format (one of: 'ODI', 'T20I', 'MLC T20')
4. sport_type (one of: 'international', 'mlc')
5. gender (one of: 'men', 'women')
6. competition (e.g. 'Major League Cricket 2026' or 'England Women vs Australia Women, Final')
7. venue (e.g. 'Grand Prairie Stadium, Grand Prairie')
8. match_date (the MDT local date of the match: YYYY-MM-DD, which must be {request.date_str})
9. match_time_utc (the approximate UTC start time of the match in YYYY-MM-DD HH:MM:SS+00 format, if known, or null)

Normalize team names to their common forms:
- Seattle Orcas, Texas Super Kings, San Francisco Unicorns, MI New York, Los Angeles Knight Riders, Washington Freedom.
- Standard nations: India, Australia, England, Pakistan, South Africa, New Zealand, West Indies, Sri Lanka, Bangladesh, Zimbabwe, Afghanistan, Ireland.

Return ONLY a valid JSON list of matches:
[
  {{
    "team_a": "Seattle Orcas",
    "team_b": "Texas Super Kings",
    "match_format": "MLC T20",
    "sport_type": "mlc",
    "gender": "men",
    "competition": "Major League Cricket 2026",
    "venue": "Grand Prairie Stadium, Grand Prairie",
    "match_date": "{request.date_str}",
    "match_time_utc": "{request.date_str} 19:30:00+00"
  }}
]

If no matches are mentioned for {request.date_str}, return an empty list [].
Do not include any code block, markdown, explanation, or extra characters. Output ONLY valid JSON."""

    try:
        logger.info(f"Parsing fixtures from search results for {request.date_str}")
        user_message = f"Search results:\n\n{request.search_results[:8000]}"
        
        response = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=TEMPERATURE,
            max_tokens=2000,
        )

        raw_output = response.choices[0].message.content
        data = _parse_json_response(raw_output)
        
        fixtures = []
        for idx, item in enumerate(data):
            # Assign a deterministic fake CricAPI ID to avoid breaking table constraints
            cricapi_id = f"searxng-{request.date_str}-{idx}"
            fixtures.append(Fixture(
                sport_type=item.get("sport_type", "mlc"),
                gender=item.get("gender", "men"),
                competition=item.get("competition", "Unknown"),
                match_format=item.get("match_format", "MLC T20"),
                team_a=item.get("team_a", ""),
                team_b=item.get("team_b", ""),
                venue=item.get("venue"),
                match_date=item.get("match_date", request.date_str),
                match_time_utc=item.get("match_time_utc"),
                cricapi_match_id=cricapi_id
            ))

        logger.info(f"Successfully parsed {len(fixtures)} fixtures")
        return FixtureExtractionResponse(
            success=True,
            fixtures=fixtures
        )

    except Exception as e:
        logger.error(f"Fixture parsing failed: {e}")
        return FixtureExtractionResponse(
            success=False,
            error=str(e)
        )
