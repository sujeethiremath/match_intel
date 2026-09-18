# Match Intel — AI Service API Reference

The **Mac Mini AI Service** (`mac_mini_service/`) exposes REST API endpoints built with FastAPI. It interfaces with local `oMLX` LLM inference engines to perform structured data extractions and deep match predictions.

Base URL: `http://localhost:8001` (configurable via `MAC_MINI_HOST` and `MAC_MINI_PORT`)

---

## Endpoints Summary

| Endpoint | Method | Description |
|---|---|---|
| `/health` | `GET` | Health check endpoint |
| `/extract` | `POST` | Structured data extraction from raw search text |
| `/analyze` | `POST` | Execute 3-pass match prediction analysis |
| `/parse-fixtures` | `POST` | Extract scheduled fixtures from raw search snippets |

---

## 1. Health Check

### Request
```http
GET /health HTTP/1.1
Host: localhost:8001
```

### Response
```json
{
  "status": "ok",
  "service": "match-intel-ai"
}
```

---

## 2. Structured Extraction

Extracts clean JSON objects from unstructured web search snippets for specific extraction types (`h2h`, `team_form`, `venue_stats`, `injury_news`, `pitch_report`, `lineup`, `squad`, `tournament_context`).

### Request
```http
POST /extract HTTP/1.1
Host: localhost:8001
Content-Type: application/json

{
  "extraction_type": "h2h",
  "sport_context": "cricket",
  "raw_text": "India and Australia have played 151 ODIs. India has won 57, Australia 84, with 10 no-result matches...",
  "team_a": "India",
  "team_b": "Australia",
  "model": "mlx-community/Qwen2.5-14B-Instruct-4bit"
}
```

### Response
```json
{
  "success": true,
  "extraction_type": "h2h",
  "data": {
    "team_a_wins": 57,
    "team_b_wins": 84,
    "draws_or_no_result": 10,
    "total_meetings": 151
  },
  "error": null,
  "model_used": "mlx-community/Qwen2.5-14B-Instruct-4bit"
}
```

---

## 3. Match Prediction & Analysis

Executes deep expert analysis report and extracts match winner prediction metrics.

### Request
```http
POST /analyze HTTP/1.1
Host: localhost:8001
Content-Type: application/json

{
  "sport": "cricket",
  "format": "ODI",
  "team_a": "India",
  "team_b": "Australia",
  "venue": "M. Chinnaswamy Stadium, Bengaluru",
  "h2h_data": {},
  "form_a_data": {},
  "form_b_data": {},
  "venue_data": {},
  "pitch_data": {},
  "weather_data": {},
  "model": "mlx-community/Qwen2.5-14B-Instruct-4bit"
}
```

### Response
```json
{
  "success": true,
  "full_report": "# EXPERT MATCH PREDICTION REPORT\n...",
  "predicted_winner": "India",
  "pick_reasoning": "Stronger spin depth and dominant record at Bengaluru.",
  "win_probability_a": 58,
  "win_probability_b": 42,
  "key_deciders": [
    "Spin control in middle overs",
    "Dew factor during 2nd innings chase"
  ],
  "confidence": 75,
  "strengths_weaknesses": {
    "team_a": {
      "strengths": ["World-class top order", "Elite spin attack"],
      "weaknesses": ["Death bowling consistency"]
    },
    "team_b": {
      "strengths": ["Aggressive powerplay bowling"],
      "weaknesses": ["Vulnerability against quality leg-spin"]
    }
  },
  "error": null
}
```

---

## 4. Parse Fixtures

Extracts match fixtures from unstructured fixture search results.

### Request
```http
POST /parse-fixtures HTTP/1.1
Host: localhost:8001
Content-Type: application/json

{
  "date_str": "2026-07-20",
  "search_results": "Major League Cricket 2026 schedule: Seattle Orcas vs Texas Super Kings..."
}
```

### Response
```json
{
  "success": true,
  "fixtures": [
    {
      "team_a": "Seattle Orcas",
      "team_b": "Texas Super Kings",
      "format": "MLC T20",
      "venue": "Grand Prairie Stadium, Dallas",
      "time_str": "15:30 MDT"
    }
  ]
}
```
