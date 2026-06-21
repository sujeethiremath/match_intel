# Cricket Intelligence Email System
## Complete Architecture & Build Reference
### Version 2.0 — Final

---

# TABLE OF CONTENTS

1. Project Purpose & Goals
2. The Two Machines
3. High-Level Architecture
4. Data Sources
5. Database Design
6. Mac Mini AI Service
7. Pipeline Stages — Detailed
8. Email Design
9. File & Folder Structure
10. Configuration Reference
11. Robustness & Failure Handling
12. Timing & Schedule
13. Setup Order for Gemini
14. Testing Approach
15. Important Notes & Constraints

---

---

# SECTION 1 — PROJECT PURPOSE & GOALS

## What This System Does

This is an automated overnight pipeline that delivers a detailed cricket intelligence email every morning at **8:00 AM MDT**. The email gives the reader everything they need to make their own match predictions — it does not make predictions itself.

The system runs without any human involvement. Once deployed, it operates every single night indefinitely. The reader simply opens their email at 8 AM and finds a beautifully formatted briefing waiting for them.

## What the Email Contains

For every cricket match scheduled on that day, the email contains:

- **5 Strengths for Team A** — each with a specific evidence note
- **5 Strengths for Team B** — each with a specific evidence note
- **5 Weaknesses for Team A** — each with a specific evidence note
- **5 Weaknesses for Team B** — each with a specific evidence note
- **5 Key Decider Factors** — the specific matchups and conditions that will most likely decide the result
- **Head-to-Head Synthesis** — what the historical record tells us that is relevant today
- **Match Context** — a narrative summary appropriate to whether the match is upcoming, in progress, or already finished
- **Weather Note** — flagged when dew or rain is a meaningful factor

## What Cricket This Covers

The system covers two categories of cricket:

**Category 1: International Cricket**
- Men's ODIs between ICC Full Member nations
- Men's T20Is between ICC Full Member nations
- Women's ODIs between ICC Full Member nations
- Women's T20Is between ICC Full Member nations
- No domestic leagues, no Tests, no Associate nations

**Category 2: MLC (Major League Cricket — USA)**
- Men's franchise T20 matches only
- Active during July only (the MLC season window)
- All 6 MLC franchise teams: MI New York, Seattle Orcas, Texas Super Kings, San Francisco Unicorns, LA Knight Riders, Washington Freedom
- The MLC section in the email only appears during July — it is hidden in all other months automatically

## The ICC Full Member Nations (International Cricket Only)

India, Australia, England, Pakistan, South Africa, New Zealand, West Indies, Sri Lanka, Bangladesh, Zimbabwe, Afghanistan, Ireland.

Matches between any two of these 12 nations in ODI or T20I format are included. All other cricket is excluded.

## Match Modes — A Critical Concept

Because the reader is in MDT timezone and matches happen globally, the same email handles three different match states:

| Mode | When It Applies | What the Email Shows |
|---|---|---|
| **PREVIEW** | Match starts after 8 AM MDT | Full 5+5+5+5 analysis for prediction |
| **IN_PROGRESS** | Match is ongoing at 8 AM MDT | Current state plus the full analysis |
| **COMPLETED** | Match already finished before 8 AM MDT | Result plus what actually decided it |

Asian evening matches (India, Pakistan, Sri Lanka) that start around 7 PM IST are already completed by 8 AM MDT because of the timezone difference. The system detects this automatically and adjusts the email content accordingly. MLC matches in the USA, by contrast, almost always appear as PREVIEW because they tip off in the evening US time.

---

---

# SECTION 2 — THE TWO MACHINES

## Lenovo IdeaPad (Sujeet-PC) — The Orchestrator

| Spec | Value |
|---|---|
| OS | Debian 12 (amd64) |
| CPU | Intel Core i3-1115G4 @ 3.00GHz |
| RAM | 12 GB |
| Storage | 119 GB |
| Hostname | Sujeet-PC |
| Role | Orchestrator, database owner, email sender |

**What Lenovo does:**
- Runs all cron jobs (the clock of the entire system)
- Owns and manages PostgreSQL (the only machine that reads or writes to the database)
- Calls external APIs (CricAPI, Exa, Open-Meteo)
- Sends jobs to Mac Mini and receives results back
- Compiles the final HTML email from the database
- Sends the email via Gmail SMTP

**What Lenovo does NOT do:**
- No AI inference — the i3 processor is not suitable for this
- No model hosting

## Mac Mini M4 — The Intelligence Engine

| Spec | Value |
|---|---|
| OS | macOS 15+ |
| Chip | Apple M4 |
| RAM | 24 GB unified memory |
| Role | AI inference engine |
| Always on | Yes — never sleeps, no wake needed |

**What Mac Mini does:**
- Runs oMLX — a native macOS AI inference server built on Apple's MLX framework
- Hosts two AI models: qwen2.5:14b (fast extraction) and qwen2.5:32b (deep analysis)
- Runs our FastAPI service that wraps oMLX and exposes two clean endpoints
- Receives raw text from Lenovo, returns structured JSON
- Never touches the database
- Stateless — it processes requests and returns responses, nothing else

**Why Mac Mini is excellent for this:**
The M4 chip with 24 GB of unified memory is specifically designed for this type of workload. The MLX framework (which oMLX is built on) is Apple's own machine learning framework optimized for Apple Silicon. Unlike other inference engines that treat memory as traditional VRAM, MLX exploits the unified memory bus natively — the CPU and GPU share the same memory without copying data between them. This gives dramatically better throughput than cross-platform tools on the same hardware.

Additionally, oMLX uses paged SSD KV caching. This means that context prefixes that have been computed before (like our system prompts and structural headers, which repeat every night) are cached to disk and restored instantly rather than recomputed. This is a meaningful speed advantage for our overnight pipeline which runs the same prompt structure repeatedly.

## The Communication Rule

This is the most important architectural principle:

> **Only Lenovo reads and writes to PostgreSQL. Mac Mini never touches the database.**

Lenovo calls Mac Mini's FastAPI service over the home network via HTTP. Mac Mini processes the request using oMLX and returns a JSON response. Lenovo takes that JSON and writes it to the database. Mac Mini has no database credentials and no knowledge of the database.

This separation keeps Mac Mini as a pure, stateless AI service. If Mac Mini goes down, Lenovo can still query the database, compile whatever data was already collected, and send an email. The failure is contained.

---

---

# SECTION 3 — HIGH-LEVEL ARCHITECTURE

## System Flow Diagram

```
HOME NETWORK
═══════════════════════════════════════════════════════════════════════

LENOVO (Sujeet-PC)                         MAC MINI M4
Debian 12 · Orchestrator                   macOS · AI Engine
──────────────────────                     ────────────────────────────

MIDNIGHT (12:00 AM MDT)
  │
  ▼
┌─────────────────────┐
│ STAGE 1             │──── CricAPI ──────────────► cricapi.com
│ FIXTURE DISCOVERY   │──── Exa Search ───────────► exa.ai
│                     │
│ Finds all matches   │
│ for today in MDT    │
│ Saves to DB         │
└─────────────────────┘
  │
  ▼
┌─────────────────────┐
│ STAGE 2             │──── Exa Search ───────────► exa.ai (H2H, form,
│ DEEP ENRICHMENT     │──── Open-Meteo ───────────► open-meteo.com
│                     │
│ Per match:          │──── POST /extract ────────► Mac Mini FastAPI :8001
│ H2H, form, venue,   │◄─── returns JSON ──────────  ↓ calls oMLX :8000
│ injury, pitch,      │                              ↓ qwen2.5:14b
│ weather, context    │                              ↓ structures raw text
│ Saves to DB         │                              returns clean JSON
└─────────────────────┘
  │
  ▼
┌─────────────────────┐
│ STAGE 3             │──── POST /analyze ────────► Mac Mini FastAPI :8001
│ AI ANALYSIS         │                              ↓ calls oMLX :8000
│                     │                              ↓ qwen2.5:32b
│ 3 passes per match  │                              ↓ Pass 1: Team A
│ Pass 1: Team A      │                              ↓ Pass 2: Team B
│ Pass 2: Team B      │◄─── returns analysis JSON ─  ↓ Pass 3: Synthesis
│ Pass 3: Synthesis   │
│ Saves to DB         │
└─────────────────────┘

6:00 AM MDT
  │
  ▼
┌─────────────────────┐
│ STAGE 4             │──── Exa Search ───────────► exa.ai (lineups)
│ TOP-UP SCRAPE       │──── POST /extract ────────► Mac Mini FastAPI
│                     │
│ Confirmed lineups   │
│ Late injury news    │
│ Updates match       │
│ status in DB        │
└─────────────────────┘

8:00 AM MDT
  │
  ▼
┌─────────────────────┐
│ STAGE 5             │
│ EMAIL COMPILE       │◄─── Queries PostgreSQL
│                     │     Renders Jinja2 HTML
│ Builds full HTML    │     Archives HTML in DB
│ email from DB       │
└─────────────────────┘
  │
  ▼
┌─────────────────────┐
│ STAGE 6             │──── Gmail SMTP ───────────► Inbox at 8:00 AM MDT
│ SEND                │
│                     │     Logs result to DB
└─────────────────────┘

═══════════════════════════════════════════════════════════════════════
```

## Port Map

| Service | Machine | Port | Purpose |
|---|---|---|---|
| oMLX inference server | Mac Mini | 8000 | LLM inference via MLX |
| Our FastAPI wrapper | Mac Mini | 8001 | Clean interface for Lenovo |
| PostgreSQL | Lenovo | 5432 | Database (localhost only) |

Lenovo communicates with Mac Mini on port 8001 only. Port 8000 (oMLX) is an internal Mac Mini concern — Lenovo never calls it directly.

---

---

# SECTION 4 — DATA SOURCES

## Overview

The system uses four data sources, each with a distinct role. No source overlaps with another.

```
CricAPI      ──► Structured match data (fixtures, scores, players)
Exa Search   ──► All contextual intelligence (H2H, form, news, venue)
Open-Meteo   ──► Weather forecasts at match venues
oMLX (local) ──► AI structuring + AI analysis (no external API cost)
```

---

## Source 1: CricAPI (cricapi.com)

**What it is:** A cricket-specific REST API that returns clean, structured JSON. No HTML parsing needed — the data comes back ready to use.

**Free tier:** 100 API calls per day. No credit card required. API key obtained via registration.

**What we use it for:**
- Getting today's fixture list (upcoming and live matches)
- Fetching full match scorecards (batting stats: runs, balls, 4s, 6s, strike rate; bowling stats: overs, runs, wickets, economy)
- Fetching individual player career statistics and profiles
- Getting series information and match IDs

**Endpoints used:**

| Endpoint | What it returns | When we call it |
|---|---|---|
| `currentMatches` | Live and recently completed matches | Stage 1 — midnight |
| `matches` | Upcoming scheduled matches | Stage 1 — midnight |
| `match_scorecard` | Full batting + bowling scorecard | Stage 2 — per match |
| `players_info` | Career stats, batting/bowling style, role | Stage 2 — per key player |
| `series_info` | Series details and match list | Stage 2 — per series |

**Daily call budget calculation:**

| Activity | Calls |
|---|---|
| Fixture discovery (current + upcoming) | 2 |
| Scorecards (average 4 matches per day) | 4 |
| Player stats (average 7 key players per day) | 7 |
| Series info (average 2 series per day) | 2 |
| Stage 4 top-up (current matches refresh) | 1 |
| **Total typical day** | **~16 calls** |
| **Worst case day (8 matches)** | **~35 calls** |
| **Daily budget** | **100 calls** |
| **Budget used (worst case)** | **35%** |

**Filtering:** CricAPI returns all cricket including domestic leagues. The system filters to only keep: (1) matches where both teams are ICC Full Member nations, (2) format is ODI or T20I, and (3) for MLC, both teams are from the 6 MLC franchises.

---

## Source 2: Exa Search API (exa.ai)

**What it is:** A real-time web search API designed specifically for AI pipelines. Unlike traditional scrapers, Exa takes a natural language query, searches the live web, and returns the actual text content of relevant pages — not just links. This eliminates the need to build and maintain custom scrapers for each website.

**Free tier:** 20,000 requests per month. API key obtained via registration.

**Why Exa instead of custom scrapers:** Custom scrapers break whenever a website changes its HTML structure. With Exa, we query by intent ("India vs Australia T20I head to head 2024 2025") and Exa figures out which pages are relevant and extracts their content. If ESPN Cricinfo redesigns their website tomorrow, our system still works because we never rely on specific HTML selectors.

**What we use it for — complete list:**

| Query Type | What We Search For | Stage |
|---|---|---|
| H2H Records | Head-to-head results between two specific teams in a specific format | Stage 2 |
| Team A Form | Recent results and performance narrative for Team A | Stage 2 |
| Team B Form | Recent results and performance narrative for Team B | Stage 2 |
| Venue Statistics | Win percentages batting/fielding first, pitch behaviour, notable records | Stage 2 |
| Injury News | Fitness updates, squad availability, selection news | Stage 2 |
| Pitch Report | Curator notes, pitch type, expected behavior | Stage 2 |
| Tournament Context | Current standings, points table, what each team needs | Stage 2 |
| MLC Team News | Franchise-specific news, squad updates (July only) | Stage 2 |
| Confirmed Lineups | Playing XI announcements, last-minute changes | Stage 4 (6 AM) |

**Monthly usage calculation:**

| Activity | Daily searches | Monthly (31 days) |
|---|---|---|
| Fixture context (2 searches/day) | 2 | 62 |
| Per match enrichment (7 searches × avg 4 matches) | 28 | 868 |
| Top-up lineup searches (2 × avg 4 matches) | 8 | 248 |
| **Total** | **~38/day** | **~1,178/month** |
| **Monthly budget** | | **20,000** |
| **Budget used** | | **~6%** |

**Important:** Exa returns raw text from multiple web pages. This raw text is then passed to Mac Mini's oMLX (qwen2.5:14b) to be structured into clean JSON. The AI extraction step is what turns "India leads 7-3 in T20Is with their last meeting at..." into a structured `{team_a_wins: 7, team_b_wins: 3, last_10: [...]}` object.

---

## Source 3: Open-Meteo (open-meteo.com)

**What it is:** A completely free weather forecast API. No API key required. No registration. No rate limits for reasonable usage.

**What we use it for:** Fetching the weather forecast for the city where each match is being played on match day.

**Data we extract per match:**

| Weather Field | Why It Matters for Cricket |
|---|---|
| Rain probability (%) | Risk of match interruption or DLS method application |
| Expected rainfall (mm) | Severity of rain impact if it comes |
| Maximum temperature (°C) | Player endurance, pitch behaviour |
| Evening humidity (%) | Dew factor — the single most impactful weather element in T20Is |
| Dew factor flag (true/false) | Automatically derived: humidity > 80% in evening hours |

**The dew factor explained:** When humidity exceeds roughly 80% in the evening (which is common in India, Sri Lanka, Bangladesh, Pakistan), dew settles on the outfield and the ball. A damp ball cannot grip seam or spin. This almost entirely eliminates the bowler's ability to extract movement. Teams batting second on a dewy night have a massive advantage because their bowlers struggled in the first innings but the dew helps them bat. This insight — when flagged by the system — is one of the most valuable pieces of prediction intelligence the email provides.

**Venue coordinate database:** The system maintains a lookup table mapping venue names to GPS coordinates. This covers all major ICC Full Member cricket grounds and all MLC venues in the USA. If a match is at a venue not in the lookup table, weather data is skipped for that match (logged as missing, pipeline continues normally).

---

## Source 4: oMLX + Apple MLX (Local, No Cost)

**What it is:** oMLX is a native macOS inference server that runs AI models locally using Apple's MLX framework. It exposes an OpenAI-compatible API. There is no cloud cost — inference runs entirely on Mac Mini.

**Two models, two distinct roles:**

| Model | Size | Role | Temperature | When Used |
|---|---|---|---|---|
| qwen2.5:14b (4-bit) | ~9 GB | Fast extraction | 0.1 (deterministic) | Structuring Exa raw text into JSON |
| qwen2.5:32b (4-bit) | ~20 GB | Deep analysis | 0.3–0.4 (creative) | 3-pass match intelligence |

**Why two different models:**
- Extraction needs determinism — we want consistent, parseable JSON output. Low temperature, smaller fast model.
- Analysis needs nuanced reasoning — we want insightful, specific, non-generic points. Higher temperature, largest available model.
- Both models fit in 24 GB unified memory simultaneously with ~3 GB of headroom.

**The KV caching advantage:** Our overnight pipeline runs the same system prompt structure for every match, every night. oMLX's SSD-backed KV caching means the first time these prefixes are computed, they are saved to disk. Every subsequent request that shares those prefixes restores from cache rather than recomputing. This reduces time-to-first-token from 30–90 seconds down to under 5 seconds on repeated prefix patterns — a significant improvement for a pipeline processing 4–8 matches in sequence.

---

---

# SECTION 5 — DATABASE DESIGN

## Overview

PostgreSQL 15 runs on Lenovo. It is the single source of truth for the entire system. Only Lenovo ever reads or writes to it. It serves three purposes:

1. **Pipeline state** — every stage records its start and completion, enabling crash recovery
2. **Match intelligence storage** — all scraped and AI-generated data persists here
3. **Email archive** — every email ever sent is stored as HTML, providing a permanent record

Database name: `cricket_intel`
Database user: `pipeline`

---

## Table: `matches`

**Purpose:** The core registry of every match discovered by Stage 1.

| Column | Type | Description |
|---|---|---|
| id | serial PK | Auto-incrementing match identifier |
| sport_type | varchar | Either `international` or `MLC` |
| gender | varchar | Either `men` or `women` |
| competition | text | Full competition name (e.g. "ICC T20I Series", "Major League Cricket") |
| match_format | varchar | One of: `ODI`, `T20I`, `MLC T20` |
| team_a | text | First team name as returned by CricAPI |
| team_b | text | Second team name as returned by CricAPI |
| venue | text | Full venue name (used for weather + venue stats lookup) |
| match_date | date | The MDT calendar date this match belongs to |
| match_time_utc | timestamptz | Match start time in UTC (null if unknown) |
| match_status | varchar | One of: `PREVIEW`, `IN_PROGRESS`, `COMPLETED` — updated throughout the day |
| cricapi_match_id | text | CricAPI's internal match ID (used to fetch scorecard) |
| created_at | timestamptz | When this record was first inserted |

**Unique constraint:** `(team_a, team_b, match_date, match_format, gender)` — prevents duplicate matches if the pipeline is re-run.

**Upsert behaviour:** If a match already exists (same teams, date, format, gender), the status, venue, and time are updated. The record is never duplicated.

---

## Table: `raw_scraped_data`

**Purpose:** Audit trail of every external data fetch. Records both successes and failures. Useful for debugging "why did the analysis come out wrong?" — you can always go back and see exactly what raw data was fed to the AI.

| Column | Type | Description |
|---|---|---|
| id | serial PK | Auto-incrementing |
| match_id | int FK | References matches.id |
| source | text | Data source: `cricapi`, `exa`, `open_meteo` |
| data_type | text | Type of data: `fixture`, `scorecard`, `h2h`, `team_form`, `venue_stats`, `injury_news`, `pitch_report`, `weather`, `tournament_context`, `lineup` |
| raw_content | jsonb | The actual raw data returned (Exa: raw text, CricAPI: JSON response) |
| fetched_at | timestamptz | When this data was fetched |
| success | boolean | Whether the fetch succeeded |
| error_msg | text | Error message if fetch failed (null on success) |

---

## Table: `processed_match_data`

**Purpose:** Cleaned, structured, AI-extracted data for each match. This is what gets sent to Mac Mini for analysis. Each match has one row. On upsert, existing non-null values are preserved — Stage 4 can add lineup data without overwriting Stage 2's form data.

| Column | Type | Description |
|---|---|---|
| id | serial PK | Auto-incrementing |
| match_id | int FK | References matches.id (unique — one row per match) |
| recent_form_a | jsonb | Last 10 results for Team A with scoreline, opponent, competition |
| recent_form_b | jsonb | Last 10 results for Team B |
| h2h_record | jsonb | Head-to-head history including last 10 meetings |
| squad_a | jsonb | Team A squad, key players, captain, roles (populated by Stage 2 and updated by Stage 4 with confirmed XI) |
| squad_b | jsonb | Team B squad, key players, captain |
| injury_news | jsonb | Injury and availability updates for both teams |
| venue_stats | jsonb | Venue records, batting/fielding first win percentages, pitch type |
| pitch_report | text | Free text pitch report from curator notes |
| weather | jsonb | Open-Meteo forecast including dew factor assessment |
| tournament_context | jsonb | Standings, qualification scenarios, what result each team needs |
| player_stats_a | jsonb | CricAPI career stats for Team A's key players |
| player_stats_b | jsonb | CricAPI career stats for Team B's key players |
| processed_at | timestamptz | Last time this row was updated |

**Upsert behaviour:** On conflict (match_id already exists), each column uses `COALESCE(new_value, existing_value)`. This means Stage 4 can update squad_a with a confirmed lineup without accidentally nullifying the h2h_record that Stage 2 already populated.

---

## Table: `ai_analysis`

**Purpose:** The output of Mac Mini's 3-pass analysis. This is the core intelligence of the system — what the email is built from. One row per match.

| Column | Type | Description |
|---|---|---|
| id | serial PK | Auto-incrementing |
| match_id | int FK | References matches.id (unique — one row per match) |
| model_used | text | The model that produced the analysis (e.g. "mlx-community/Qwen2.5-32B-Instruct-4bit") |
| strengths_a | jsonb | Array of 5 objects, each with `point` (the insight) and `evidence` (supporting stat) |
| strengths_b | jsonb | Array of 5 objects, same structure |
| weaknesses_a | jsonb | Array of 5 objects, same structure |
| weaknesses_b | jsonb | Array of 5 objects, same structure |
| key_decider_factors | jsonb | Array of 5 strings — the factors that will decide this match |
| h2h_synthesis | text | 2–3 sentence narrative connecting H2H history to current context |
| match_context | text | 2–3 sentences appropriate to the match status (PREVIEW / IN_PROGRESS / COMPLETED) |
| weather_note | text | One sentence about dew or rain impact (null if not significant) |
| analysis_complete | boolean | True only when all 3 analysis passes completed successfully |
| analyzed_at | timestamptz | When analysis was completed |

**Upsert behaviour:** On conflict, all analysis fields are overwritten. If Stage 3 is re-run (e.g. after a crash), the analysis is simply replaced with the fresh result.

---

## Table: `pipeline_runs`

**Purpose:** Tracks the status of every pipeline stage execution. This is the crash recovery mechanism. If the system fails at 3 AM, you can query this table to see exactly which stage failed and which ones completed successfully.

| Column | Type | Description |
|---|---|---|
| id | serial PK | Auto-incrementing |
| run_date | date | The MDT date this pipeline run belongs to |
| stage_name | text | Stage identifier: `FIXTURE_DISCOVERY`, `DEEP_ENRICHMENT`, `AI_ANALYSIS`, `TOP_UP_SCRAPE`, `EMAIL_COMPILE`, `SEND` |
| status | varchar | One of: `RUNNING`, `DONE`, `FAILED`, `SKIPPED` |
| started_at | timestamptz | When this stage started |
| completed_at | timestamptz | When this stage finished (null if still running or never finished) |
| matches_processed | int | How many matches this stage handled |
| notes | text | Summary notes on completion (e.g. "Enriched 4/4 matches") |
| error_log | text | Error message if status is FAILED (null otherwise) |

**Usage pattern:** Every stage writes a `RUNNING` row at the very start. It then updates to `DONE` or `FAILED` at the end. If the process is killed, the row stays as `RUNNING` — which tells you exactly where the crash happened.

---

## Table: `email_log`

**Purpose:** Record of every email the system has attempted to send. The HTML snapshot means you can always retrieve exactly what was sent on any date.

| Column | Type | Description |
|---|---|---|
| id | serial PK | Auto-incrementing |
| run_date | date | The MDT date this email was for |
| sent_at | timestamptz | Exact time the email was delivered (null if not yet sent) |
| status | varchar | One of: `PENDING`, `SENT`, `FAILED` |
| recipient | text | The email address the briefing was sent to |
| matches_included | int | Total number of matches in this email |
| error_message | text | SMTP error if status is FAILED |
| html_snapshot | text | The complete rendered HTML of the email — stored permanently |

**Maintenance note:** After 60 days, the `html_snapshot` column will accumulate significant storage. It is safe to null out old snapshots while keeping the metadata rows:
Run a SQL update that sets `html_snapshot` to null for rows older than 60 days. The row itself remains as a record of whether the email was sent.

---

## Database View: `todays_status`

**Purpose:** A convenience query joining matches, processed_match_data, and ai_analysis for today's date. Shows at a glance which matches have been enriched and which have been analyzed. Used for quick monitoring and debugging.

**Columns shown:** match ID, sport type, gender, format, both team names, match status, match time, whether enrichment data exists, whether analysis is complete.

---

## Indexes

Four indexes are created to ensure fast queries:
- `matches.match_date` — the most frequent filter in all queries
- `matches.sport_type` — for filtering cricket type
- `pipeline_runs.run_date` — for checking today's stage statuses
- `email_log.run_date` — for retrieving email history

---

---

# SECTION 6 — MAC MINI AI SERVICE

## Overview

The Mac Mini runs two services simultaneously:

1. **oMLX** on port 8000 — the AI inference engine (handles all LLM computation)
2. **Our FastAPI service** on port 8001 — a wrapper that Lenovo calls

These are completely separate processes. oMLX is an independent application. Our FastAPI service is a Python application that internally calls oMLX's OpenAI-compatible API.

Lenovo only ever talks to port 8001. It has no knowledge of port 8000.

## oMLX Configuration

oMLX must be configured to listen on `0.0.0.0` (all interfaces) rather than just localhost. Without this change, requests from Lenovo on the home network would be refused. This is a one-time configuration change in oMLX's settings.

oMLX is set to auto-start on macOS login via a LaunchAgent plist file. The Mac Mini is always on, so this ensures the service is always available even after a macOS update reboot.

## The Two FastAPI Endpoints

Our FastAPI service exposes exactly two endpoints to Lenovo:

---

### Endpoint 1: `POST /extract`

**Purpose:** Takes raw text from an Exa search result and uses qwen2.5:14b to structure it into clean JSON.

**When called:** During Stage 2 (deep enrichment) for each type of data — H2H, team form, venue stats, injury news, pitch report, tournament context, squad information, confirmed lineup.

**What Lenovo sends:**
- The type of extraction needed (h2h, team_form, venue_stats, injury_news, pitch_report, lineup, squad, tournament_context)
- The sport context string (e.g. "cricket — T20I" or "cricket — ODI")
- The team names (for context in the prompt)
- The raw text from Exa (up to 8,000 characters)

**What Mac Mini returns:**
- Whether extraction succeeded (true/false)
- The extraction type (echoed back)
- The structured data as a JSON object
- Which model was used
- Error message if extraction failed

**Temperature setting:** 0.1 — very low, making the model highly deterministic. Extraction is a precision task — we want consistent, parseable JSON, not creative variation.

**Prompt strategy per extraction type:**
- **h2h:** Asks the model to find team A wins, team B wins, total meetings, and last 10 individual results
- **team_form:** Asks for last 10 match results, key performers, form rating, win rate
- **venue_stats:** Asks for pitch type, bat-first win %, field-first win %, notable records
- **squad:** Asks for key players, captain, roles, batting/bowling styles
- **injury_news:** Asks for injuries, doubtful players, suspensions
- **pitch_report:** Asks for expected behavior, toss advantage, dew factor, pace vs spin
- **lineup:** Asks for confirmed playing XI, notable inclusions/omissions
- **tournament_context:** Asks for standings, qualification scenarios, match importance

---

### Endpoint 2: `POST /analyze`

**Purpose:** Takes all enriched match data and runs 3-pass deep analysis using qwen2.5:32b.

**When called:** Once per match during Stage 3, after all enrichment data has been collected.

**What Lenovo sends:** The complete match record including all enrichment data — recent form for both teams, H2H record, squad information, injury news, venue stats, pitch report, weather, tournament context, match status, format, and competition.

**What Mac Mini returns:**
- 5 strengths for Team A (each with a point and an evidence note)
- 5 strengths for Team B (each with a point and an evidence note)
- 5 weaknesses for Team A (each with a point and an evidence note)
- 5 weaknesses for Team B (each with a point and an evidence note)
- 5 key decider factors (strings describing specific matchups or conditions)
- Head-to-head synthesis (2–3 sentences)
- Match context (2–3 sentences appropriate to match status)
- Weather note (one sentence, or null if not significant)
- Whether analysis succeeded (true/false)
- Which model was used

**The 3-pass analysis design:**

Pass 1 and Pass 2 run independently and in sequence. Each analyzes one team in isolation, knowing only about that team's data and who the opponent is. This prevents the model from unconsciously favoring one team when analyzing the other. It produces sharper, more honest weaknesses.

Pass 3 receives the outputs of Pass 1 and Pass 2 as context, plus the H2H record, weather, and tournament context. Its job is synthesis — it looks at Team A's strengths vs Team B's weaknesses and vice versa to identify the specific battlegrounds that will decide the match.

This approach produces significantly richer analysis than a single prompt because each pass has full token budget to think deeply about one team, rather than splitting attention across both teams simultaneously.

**Temperature setting:** 0.3 for Passes 1 and 2, 0.35 for Pass 3 — slightly higher to allow nuanced, specific language while still being grounded in the data.

**Analysis quality rules enforced in the prompt:**
- Every point must reference a specific stat, player name, or observable pattern
- No generic statements like "experienced squad" or "good batting lineup"
- Every point must be relevant to THIS specific match (this opponent, this venue, this format)
- Weaknesses must be honest — the model is instructed not to downplay real vulnerabilities

**Timeout:** 20 minutes per match. If the Mac Mini does not respond within 20 minutes, Lenovo logs the failure and moves to the next match. The email for that match will show a banner saying analysis was unavailable, but the rest of the email is unaffected.

**Retry logic:** On timeout or error, Lenovo retries the analysis request once. If the retry also fails, the match is marked as analysis-failed and the pipeline continues.

## Auto-Start Configuration

Both oMLX and our FastAPI service are configured as macOS LaunchAgents. LaunchAgents start automatically when the user logs in and are automatically restarted if they crash (KeepAlive = true). Since Mac Mini is always on and the user is always logged in, both services are always running.

The FastAPI service's log output and error output are written to files in the `match-intel-service` directory for debugging purposes.

---

---

# SECTION 7 — PIPELINE STAGES: DETAILED

## Timing Overview

```
12:00 AM MDT  ─────  Stage 1: Fixture Discovery starts
12:20 AM MDT  ─────  Stage 2: Deep Enrichment starts
 1:30 AM MDT  ─────  Stage 3: AI Analysis starts (approx, depends on match count)
 3:30 AM MDT  ─────  Analysis complete (approx, 4 matches at 15 min each)
 6:00 AM MDT  ─────  Stage 4: Top-Up Scrape (6 AM cron)
 7:00 AM MDT  ─────  Stage 5: Email Compilation (part of 8 AM cron run)
 7:55 AM MDT  ─────  Stage 6: Email queued and sent
 8:00 AM MDT  ─────  Email arrives in inbox
```

The pipeline has generous time buffers. Even on a busy day with 8 matches and 3-pass analysis, the overnight window provides approximately 6 hours of buffer.

---

## Stage 1: Fixture Discovery

**Triggered by:** Midnight cron job (0 0 * * *)
**Duration:** ~15–20 minutes
**Writes to:** `matches` table, `pipeline_runs` table

**What it does:**

1. Records a `RUNNING` entry in `pipeline_runs` for stage `FIXTURE_DISCOVERY`

2. Calls CricAPI's `currentMatches` endpoint to get live and recently completed matches

3. Calls CricAPI's `matches` endpoint to get upcoming scheduled matches

4. Combines both lists and deduplicates by match ID

5. Runs the international filter — checks that:
   - Match format is ODI or T20I
   - Both teams are ICC Full Member nations (fuzzy name matching)
   - Detects gender from the competition name (looks for "women", "woman", "female", "ladies" in the name)

6. Runs the MLC filter only if the current month is July — checks that both teams are MLC franchise names

7. For each valid match, determines match status using the `determine_match_status` function: compares current UTC time to match start time UTC. ODI duration estimated at 8 hours, T20I and MLC T20 at 4 hours.

8. Calls `upsert_match` to save or update each match in the database

9. Updates `pipeline_runs` to `DONE` with count of matches found

**What happens if CricAPI fails:** If both `currentMatches` and `matches` endpoints fail (network error, timeout, API down), Stage 1 logs the failure in `pipeline_runs`, records the error, and the pipeline continues. Stages 2 and 3 will find zero matches and complete immediately. The email will still send at 8 AM stating "No fixtures found today."

---

## Stage 2: Deep Enrichment

**Triggered by:** Immediately after Stage 1 completes (same midnight cron run)
**Duration:** ~60–90 minutes for a typical day
**Writes to:** `raw_scraped_data` table, `processed_match_data` table, `pipeline_runs` table

**What it does:**

For each match in the database for today, it runs 7–8 enrichment tasks. Each task is independent — if one fails, the others continue.

**Enrichment tasks per match:**

1. **H2H Records** — Searches Exa for head-to-head results between the two teams in the specific format. Raw text returned by Exa is sent to Mac Mini's `/extract` endpoint (extraction_type: `h2h`). Structured result saved to `h2h_record` column.

2. **Team A Form** — Searches Exa for Team A's recent results and form narrative. Sent to `/extract` (extraction_type: `team_form`). Saved to `recent_form_a`.

3. **Team B Form** — Same as Team A Form. Saved to `recent_form_b`.

4. **Venue Statistics** — Searches Exa for the specific venue's records, pitch characteristics, and notable statistics. Sent to `/extract` (extraction_type: `venue_stats`). Saved to `venue_stats`.

5. **Injury News** — Searches Exa for injury and availability news for both teams combined. Sent to `/extract` (extraction_type: `injury_news`). Saved to `injury_news`.

6. **Pitch Report** — Searches Exa for recent curator notes and pitch reports for this venue. Sent to `/extract` (extraction_type: `pitch_report`). Saved to `pitch_report` as a text field.

7. **Tournament Context** — Searches Exa for the current standings, points table, and qualification scenarios for this competition. Sent to `/extract` (extraction_type: `tournament_context`). Saved to `tournament_context`.

8. **Weather** — Calls Open-Meteo API directly with venue coordinates and today's date. No AI extraction needed — the API returns structured JSON directly. Dew factor (boolean) is derived from evening humidity values. Saved to `weather`.

9. **MLC Team News** (July only, MLC matches only) — Searches Exa for franchise-specific news. Sent to `/extract` (extraction_type: `squad`). Saved to `squad_a` and `squad_b`.

**Raw data logging:** Every Exa search result is saved to `raw_scraped_data` before being sent for extraction. Every extraction result is also logged. This provides a complete audit trail.

**Failure isolation:** Each of the 7–8 tasks above has its own try/except. If the Exa search for H2H fails (network error, no results), Stage 2 logs the failure to `raw_scraped_data` (success=false) and moves on to Team A Form. The other 6 tasks still complete. The match ends up with partial data — which is fine. The AI analysis in Stage 3 works with whatever data is available.

---

## Stage 3: AI Analysis

**Triggered by:** Immediately after Stage 2 completes (same midnight cron run)
**Duration:** 10–20 minutes per match (3 passes × ~5 min each for 32B model)
**Writes to:** `ai_analysis` table, `pipeline_runs` table

**What it does:**

For each match in the database for today:

1. Loads the enrichment data from `processed_match_data` for that match

2. Builds the analysis request payload — combines match metadata (competition, format, gender, venue, status) with all enrichment fields

3. Sends a `POST /analyze` request to Mac Mini FastAPI with a 20-minute timeout

4. Mac Mini runs all 3 analysis passes sequentially (Pass 1 → Pass 2 → Pass 3) and returns the complete analysis as a single JSON response

5. Lenovo receives the response and saves all fields to the `ai_analysis` table, setting `analysis_complete = true`

6. If the request times out or returns an error, Lenovo retries once. If the retry also fails, `analysis_complete` remains false for that match. The match card in the email will show a "Limited data" banner instead of the analysis grid.

**Processing time estimate:**

| Scenario | Time per match | Total for 4 matches |
|---|---|---|
| Full data, 32B model | ~15 minutes | ~60 minutes |
| Partial data (faster) | ~10 minutes | ~40 minutes |
| Analysis fails | — | 0 minutes |

With 8 matches (very busy day): ~2 hours. Pipeline still finishes well before 6 AM.

---

## Stage 4: Top-Up Scrape

**Triggered by:** 6 AM cron job (0 6 * * *)
**Duration:** ~15–20 minutes
**Writes to:** `processed_match_data` (update squad_a, squad_b), `matches` (update match_status)

**What it does:**

1. Refreshes match status for all today's matches (some PREVIEW matches may now be IN_PROGRESS or COMPLETED if they started overnight)

2. For each match, searches Exa for confirmed playing XI and starting lineup announcements (teams often announce their XI 1–2 hours before the match)

3. Sends lineup text to Mac Mini `/extract` (extraction_type: `lineup`) to structure it

4. Updates `squad_a` and `squad_b` in `processed_match_data` with the confirmed XI — using `COALESCE` so it only overwrites if new data is found

**Why this matters:** Knowing the confirmed playing XI rather than just the squad list significantly improves analysis quality. It reveals:
- Whether a key batter is sitting out (changes team strength assessment dramatically)
- The team's XI balance (6 batters and 5 bowlers vs 7 batters and 4 bowlers)
- Whether a specialist spinner is playing (changes venue + pitch relevance)

Note: Stage 4 does NOT re-run the AI analysis. The confirmed lineup data sits in `processed_match_data` but Stage 3's analysis is not regenerated. This is a deliberate design choice — regenerating analysis at 6 AM would take another 60–120 minutes and potentially not finish before the 8 AM email. The lineup data is instead displayed directly in the email card as factual information alongside the existing AI analysis.

---

## Stage 5: Email Compilation

**Triggered by:** 8 AM cron job (0 8 * * *), runs immediately before Stage 6
**Duration:** ~2–5 minutes
**Reads from:** `matches`, `processed_match_data`, `ai_analysis` (single joined query)
**Writes to:** `pipeline_runs`, `email_log` (creates PENDING record)

**What it does:**

1. Runs a single SQL query joining all three data tables for today's MDT date, ordered by sport_type, gender, match_time_utc

2. Categorizes matches into four groups:
   - `intl_men` — international men's matches
   - `intl_women` — international women's matches
   - `mlc` — MLC matches (empty array outside July)

3. For each match, prepares template-ready data:
   - Looks up country flags from an emoji mapping table
   - Formats the match start time as local MDT time string
   - Parses JSONB columns from the database back into Python lists/dicts
   - Determines which status badge to show (PREVIEW / IN_PROGRESS / COMPLETED)

4. Passes the categorized, enriched data to the Jinja2 template engine to render the HTML email

5. Creates an entry in `email_log` with status PENDING

6. Returns the rendered HTML string and the total match count to Stage 6

**If no matches exist:** Returns an HTML email containing the header, a "No international ODI, T20I, or MLC fixtures today" message, and the footer. The email still sends at 8 AM regardless.

---

## Stage 6: Email Send

**Triggered by:** Immediately after Stage 5 returns the rendered HTML
**Duration:** ~10–30 seconds
**Writes to:** `email_log` (updates PENDING to SENT or FAILED)

**What it does:**

1. Reads email configuration (recipient, sender, SMTP settings) from config.yaml
2. Reads Gmail App Password from .env
3. Constructs the email as a multipart MIME message with:
   - A plain text fallback (one line saying to open in HTML client)
   - The full HTML body
4. Connects to smtp.gmail.com on port 587 using STARTTLS
5. Authenticates with the sender Gmail address and App Password
6. Sends the message
7. On success: updates `email_log` with status SENT, sent_at timestamp, match count, and the full HTML snapshot
8. On failure: updates `email_log` with status FAILED and the SMTP error message, then logs the error

**Retry strategy for Stage 6:** Unlike other stages, email send is not retried automatically. If Gmail SMTP fails once, the pipeline logs the failure and terminates. Manual retry is done by re-running `orchestrator.py email` from the command line.

---

## The Orchestrator

The orchestrator is a single Python script (`pipeline/orchestrator.py`) that is called by cron. It accepts one command-line argument determining which mode to run:

| Mode | Cron trigger | What it runs |
|---|---|---|
| `pipeline` | 0 0 * * * | Stage 1 → Stage 2 → Stage 3 (in sequence) |
| `topup` | 0 6 * * * | Stage 4 only |
| `email` | 0 8 * * * | Stage 5 → Stage 6 (in sequence) |

Before running the pipeline mode, the orchestrator performs a Mac Mini health check — it calls the `/health` endpoint on port 8001. It retries up to 5 times with 30-second intervals. If Mac Mini is unreachable after all retries, the pipeline aborts and logs a critical error. The email will still attempt to send at 8 AM using whatever data already exists in the database.

---

---

# SECTION 8 — EMAIL DESIGN

## Overall Structure

```
┌─────────────────────────────────────────────────┐
│           HEADER                                 │
│   🏏 Cricket Intelligence                        │
│   Your Daily Match Prediction Briefing           │
│   [Monday, June 15, 2026 · MDT]                 │
├─────────────────────────────────────────────────┤
│           TABLE OF CONTENTS                      │
│   Links to every match in the email              │
│   Grouped by section with status badges          │
├─────────────────────────────────────────────────┤
│  🏏 INTERNATIONAL — MEN'S                        │
│  ─────────────────────────────────────────────  │
│  [Match Card 1]                                  │
│  [Match Card 2]                                  │
│  ─ or ─                                          │
│  "No men's international ODI or T20I today"      │
├─────────────────────────────────────────────────┤
│  🏏 INTERNATIONAL — WOMEN'S                      │
│  ─────────────────────────────────────────────  │
│  [Match Cards or no-fixtures message]            │
├─────────────────────────────────────────────────┤
│  🏆 MLC (July only — hidden outside July)        │
│  ─────────────────────────────────────────────  │
│  [Match Cards]                                   │
├─────────────────────────────────────────────────┤
│           FOOTER                                 │
│   Pipeline info · match count · generated time   │
└─────────────────────────────────────────────────┘
```

## Section Headers — Visual Design

Each section has a distinct color-coded left border:
- International Men's — green border, dark green background
- International Women's — purple border, dark purple background
- MLC — blue border, dark blue background

A small pill badge sits inline with the section title identifying Men's / Women's.

## The Table of Contents

The ToC appears near the top of the email, before the match sections. It contains one link per match. Each link shows:
- Team flags (emoji) and team names
- Match format (ODI / T20I / MLC T20)
- A status badge (🔵 PREVIEW / 🔴 LIVE / ✅ DONE)

Clicking any ToC link jumps directly to that match card in the email. On mobile this is useful when there are many matches.

## Match Card Design

Each match occupies one card. The card has several distinct zones:

### Zone 1: Card Header
- Competition name (small, uppercase, grey)
- Status badge (top right corner): `🔵 Preview` / `🔴 Live` / `✅ Completed`
- Team A flag + name — centered
- VS circle — centered
- Team B flag + name — centered
- Three info chips: 📍 Venue · 🕐 Local time (MDT) · 📋 Format

The card has a coloured top border: blue for PREVIEW, red for IN_PROGRESS, green for COMPLETED.

### Zone 2: Analysis Grid (2 × 2)

A 2-column, 2-row grid containing four sub-panels:

```
┌──────────────────────┬──────────────────────┐
│  ⚡ Team A STRENGTHS  │  ⚡ Team B STRENGTHS  │
│  1. Point            │  1. Point            │
│     Evidence note    │     Evidence note    │
│  2. Point            │  2. Point            │
│     ...              │     ...              │
│  (5 points)          │  (5 points)          │
├──────────────────────┼──────────────────────┤
│  ⚠️ Team A WEAKNESSES │  ⚠️ Team B WEAKNESSES │
│  1. Point            │  1. Point            │
│     Evidence note    │     Evidence note    │
│  ...                 │  ...                 │
│  (5 points)          │  (5 points)          │
└──────────────────────┴──────────────────────┘
```

Headers: green for strengths, red for weaknesses.
Each point shows the insight text in bold/white, and the evidence note below it in small grey text.

If `analysis_complete` is false (AI analysis was not available for this match), the entire analysis grid is replaced with a single message: "⚠️ AI analysis unavailable — data collection may have been incomplete for this match."

### Zone 3: Key Decider Factors

Shown only if analysis was complete. Five numbered items, each with an amber circular number badge and the factor text. Background is slightly darker than the card body to visually separate it.

Section header: `🎯 Key Decider Factors` in amber.

### Zone 4: Head-to-Head Synthesis

2–3 sentences in italics connecting the historical H2H record to current form context. Shown in grey text. Only displayed if analysis was complete.

### Zone 5: Match Context

2–3 sentences in grey text. The content adapts to match status:
- PREVIEW: What to watch for, key narrative going in
- IN_PROGRESS: What has happened and what still matters
- COMPLETED: What actually decided the match

### Zone 6: Weather Note

Only shown if the weather note is not null (i.e. weather is a meaningful factor). Displayed in amber text on a dark amber background. Example: "🌤️ Heavy dew expected this evening in Mumbai — fielding team will be disadvantaged in the second innings."

## Color Palette

The email uses a dark theme throughout:
- Background: near-black (#0a0d13)
- Card background: dark navy (#111827)
- Card header background: slightly darker (#0d1017)
- Borders: dark grey (#1f2937)
- Body text: light grey (#e0e0e0)
- Subtle text (evidence notes, captions): medium grey (#6b7280)
- White: team names, section labels
- Green: strengths headers, completed badge
- Red: weaknesses headers, live badge
- Blue: preview badge, section header (intl men)
- Purple: section header (intl women)
- Amber: key deciders, weather note

## Mobile Responsiveness

The 2×2 analysis grid switches to a single-column layout on screens narrower than 580px. This makes the email readable on phones without horizontal scrolling. Team names reduce to 14px and flag emojis reduce in size.

## Flag Emoji System

A hardcoded mapping table converts team names to country flag emojis. Matching is case-insensitive and uses substring matching — "MI New York" maps to 🗽, "India" maps to 🇮🇳. If no match is found, the default cricket bat emoji 🏏 is used.

---

---

# SECTION 9 — FILE AND FOLDER STRUCTURE

## Mac Mini: `~/match-intel-service/`

```
match-intel-service/
│
├── main.py
│     The FastAPI application entry point.
│     Defines the /health, /extract, and /analyze routes.
│     Starts uvicorn on host 0.0.0.0, port 8001.
│
├── services/
│   ├── extractor.py
│   │     Handles the /extract endpoint logic.
│   │     Builds extraction prompts for each extraction_type.
│   │     Calls oMLX via OpenAI-compatible client on localhost:8000.
│   │     Uses qwen2.5:14b. Temperature 0.1.
│   │     Strips markdown fences from JSON responses.
│   │     Returns structured dict or error.
│   │
│   └── analyzer.py
│         Handles the /analyze endpoint logic.
│         Orchestrates the 3-pass analysis sequence.
│         Pass 1: builds Team A context, calls oMLX, parses result.
│         Pass 2: builds Team B context, calls oMLX, parses result.
│         Pass 3: combines both results + H2H/weather/tournament, synthesis call.
│         Uses qwen2.5:32b. Temperature 0.3–0.35.
│         Returns complete AnalysisResponse object.
│
├── models/
│   ├── extract.py
│   │     Pydantic request model: extraction_type, sport_context,
│   │     team_a, team_b, raw_text.
│   │     Pydantic response model: success, extraction_type,
│   │     data (dict), model_used, error.
│   │
│   └── analyze.py
│         Pydantic request model: all match fields + all enrichment
│         data fields (all Optional).
│         Pydantic response model: success, both team names,
│         all 4 analysis lists, key_decider_factors, h2h_synthesis,
│         match_context, weather_note, model_used, error.
│
├── requirements.txt
│     Lists: fastapi, uvicorn[standard], openai, pydantic, python-dotenv
│
├── fastapi.log
│     Auto-created. Standard output from uvicorn.
│
├── fastapi_error.log
│     Auto-created. Standard error from uvicorn.
│
└── com.matchintel.fastapi.plist
      macOS LaunchAgent configuration.
      Sets WorkingDirectory to this folder.
      Runs uvicorn main:app on 0.0.0.0:8001.
      KeepAlive = true (restarts on crash).
      RunAtLoad = true (starts on login).
```

## Lenovo: `/home/sujeet/match-intel/`

```
match-intel/
│
├── config.yaml
│     Master configuration. Edit this file to change scope, timing,
│     recipients, Mac Mini IP, or model names.
│     Never contains secrets (those go in .env).
│
├── .env
│     Contains: GMAIL_APP_PASSWORD, DB_PASSWORD,
│     CRICAPI_KEY, EXA_API_KEY, MAC_MINI_HOST, MAC_MINI_PORT.
│     Never commit this file to version control.
│
├── requirements.txt
│     Lists: exa-py, httpx, psycopg2-binary, jinja2, pyyaml,
│     python-dotenv, loguru, pytz
│
├── scrapers/
│   │
│   ├── cricapi_client.py
│   │     Wraps CricAPI (api.cricapi.com/v1).
│   │     Functions: get_current_matches(), get_upcoming_matches(),
│   │     get_match_scorecard(match_id), get_player_info(player_id),
│   │     get_series_info(series_id), filter_international_fixtures(),
│   │     filter_mlc_fixtures().
│   │     Reads CRICAPI_KEY from .env.
│   │     All functions return Python dicts/lists or None on failure.
│   │     No retry logic — failure returns None, caller handles it.
│   │
│   ├── exa_client.py
│   │     Wraps Exa Python SDK (exa_py library).
│   │     Core function: search(query, num_results=3) → returns
│   │     concatenated text from all result pages, or None.
│   │     Named helper functions for each query type:
│   │       search_cricket_h2h(team_a, team_b, format)
│   │       search_team_form(team, format, gender)
│   │       search_venue_stats(venue, team_a, team_b)
│   │       search_injury_news(team, gender)
│   │       search_pitch_report(venue, format)
│   │       search_tournament_context(competition, team_a, team_b)
│   │       search_confirmed_lineup(team, date_str, opponent)
│   │       search_mlc_team_news(team)
│   │     Reads EXA_API_KEY from .env.
│   │     Each function returns a single string of concatenated
│   │     page text, or None on failure.
│   │
│   └── weather_client.py
│         Wraps Open-Meteo API (no key needed).
│         Core function: get_weather(venue_name, date_str).
│         Looks up GPS coordinates from internal VENUE_COORDINATES dict.
│         Returns a weather dict with: temperature_max_c, rain_probability_pct,
│         rain_expected_mm, evening_humidity_pct, dew_factor_likely (bool),
│         match_risk (string), summary (string).
│         Returns None if venue not in coordinates table.
│
├── pipeline/
│   │
│   ├── orchestrator.py
│   │     Entry point called by cron.
│   │     Accepts argv[1]: "pipeline" | "topup" | "email"
│   │     Pipeline mode: calls Stage 1 → 2 → 3 in sequence.
│   │       Runs Mac Mini health check first — aborts if unreachable.
│   │     Topup mode: calls Stage 4 only.
│   │     Email mode: calls Stage 5 → 6 in sequence.
│   │     Uses asyncio.run() to run async stages.
│   │
│   ├── stage1_fixtures.py
│   │     Exports: run_stage1(today: date) → bool
│   │     Calls CricAPI current + upcoming, filters, saves to DB.
│   │     Handles international + MLC filtering.
│   │     Determines initial match status using timezone util.
│   │     Logs start/end to pipeline_runs table.
│   │
│   ├── stage2_enrichment.py
│   │     Exports: run_stage2(today: date) → bool
│   │     Loops through matches. For each match, runs 7–8 enrichment tasks.
│   │     Each task: Exa search → send to Mac Mini /extract → save to DB.
│   │     Weather: Open-Meteo call → save directly (no AI needed).
│   │     Each task is independently try/excepted.
│   │     All raw data logged to raw_scraped_data table.
│   │     Logs start/end to pipeline_runs table.
│   │
│   ├── stage3_analysis.py
│   │     Exports: run_stage3(today: date) → bool
│   │     Loops through matches. For each match:
│   │       Loads processed_match_data from DB.
│   │       Builds analysis payload.
│   │       Calls Mac Mini /analyze (20-min timeout).
│   │       Saves result to ai_analysis table.
│   │       Retries once on failure.
│   │     Logs start/end to pipeline_runs table.
│   │
│   ├── stage4_topup.py
│   │     Exports: run_stage4(today: date) → bool
│   │     Refreshes match statuses.
│   │     Searches for confirmed lineups via Exa.
│   │     Sends lineup text to /extract.
│   │     Updates squad_a/squad_b in processed_match_data.
│   │     Logs start/end to pipeline_runs table.
│   │
│   ├── stage5_compile.py
│   │     Exports: run_stage5(today: date) → tuple[str, int]
│   │     Calls compiler.compile_email(today).
│   │     Returns (html_string, match_count).
│   │     Has fallback: returns minimal error HTML if compilation fails.
│   │     Logs start/end to pipeline_runs table.
│   │
│   └── stage6_send.py
│         Exports: run_stage6(today, html, match_count) → bool
│         Reads email config from config.yaml.
│         Reads Gmail App Password from .env.
│         Builds MIME email with plain text + HTML parts.
│         Connects to smtp.gmail.com:587 with STARTTLS.
│         On success: marks email_log as SENT, stores HTML snapshot.
│         On failure: marks email_log as FAILED, logs error.
│
├── database/
│   │
│   ├── schema.sql
│   │     Complete SQL to create all 5 tables, the view, and all indexes.
│   │     Run once during initial setup.
│   │     Idempotent — uses CREATE TABLE IF NOT EXISTS throughout.
│   │
│   ├── connection.py
│   │     Creates and manages a psycopg2 ThreadedConnectionPool.
│   │     Pool is a module-level singleton — created once, reused.
│   │     Reads DB credentials from config.yaml (host, port, name, user)
│   │     and DB_PASSWORD from .env.
│   │     Provides a DB context manager class for clean connection
│   │     handling with automatic commit/rollback and connection return.
│   │
│   └── queries.py
│         All database read/write functions.
│         Uses the DB context manager from connection.py.
│         Function groups:
│           Pipeline runs: log_stage_start, log_stage_done, log_stage_failed
│           Matches: upsert_match, get_todays_matches, update_match_status
│           Processed data: upsert_processed, get_processed
│           AI analysis: save_analysis
│           Email join query: get_full_match_data_for_email
│           Email log: create_email_log, mark_email_sent, mark_email_failed
│
├── email_builder/
│   │
│   ├── compiler.py
│   │     Core function: compile_email(today) → (html_string, match_count)
│   │     Queries DB with get_full_match_data_for_email.
│   │     Categorizes matches into intl_men, intl_women, mlc lists.
│   │     Calls prepare_match() on each match dict:
│   │       - Looks up flag emojis from FLAG_MAP dict
│   │       - Formats UTC time to MDT local string
│   │       - Parses JSONB columns from string to Python objects
│   │     Builds Jinja2 template context dict.
│   │     Renders template and returns HTML string.
│   │
│   └── templates/
│       └── daily_briefing.html
│             Jinja2 HTML email template.
│             Complete HTML document with embedded CSS.
│             Uses Jinja2 macro for match card (called per match).
│             Sections: header, ToC, intl men, intl women, MLC, footer.
│             MLC section uses {% if has_mlc %} guard — hidden outside July.
│             No JavaScript. No external CSS. Fully self-contained HTML.
│
├── utils/
│   │
│   ├── logger.py
│   │     Sets up Loguru with two sinks:
│   │       Console: INFO level, colour-formatted
│   │       File: DEBUG level, daily rotation, 30-day retention
│   │     Log files named YYYY-MM-DD.log in the logs/ directory.
│   │
│   ├── mac_mini_client.py
│   │     HTTP client for Mac Mini FastAPI.
│   │     Reads host and port from config.yaml.
│   │     Functions:
│   │       health_check(retries, interval) → bool
│   │         Calls /health endpoint. Retries on failure.
│   │       extract(extraction_type, sport_context, raw_text,
│   │               team_a, team_b, timeout_secs) → dict or None
│   │         POSTs to /extract. Returns data dict or None on failure.
│   │       analyze(payload_dict, timeout_mins) → dict or None
│   │         POSTs to /analyze. Returns full response dict or None.
│   │     All functions log failures. Return None instead of raising
│   │     exceptions — callers handle None gracefully.
│   │
│   └── timezone.py
│         Defines MDT as UTC-6 timezone offset.
│         (Update to UTC-7 in November when clocks fall back to MST.)
│         Functions:
│           now_mdt() → datetime
│           today_mdt() → date
│           determine_match_status(match_time_utc_str, match_format) → str
│             Compares current UTC to match start UTC.
│             ODI duration = 8 hours. T20I/MLC = 4 hours.
│             Returns "PREVIEW", "IN_PROGRESS", or "COMPLETED".
│           format_mdt_time(utc_datetime) → str
│             Converts UTC datetime to "07:30 PM MDT" format string.
│
└── logs/
      Auto-created directory.
      Contains daily log files: 2026-06-15.log, 2026-06-16.log, etc.
      Also contains cron.log — stdout/stderr from cron job execution.
      Log files rotate daily, kept for 30 days, then auto-deleted.
```

---

---

# SECTION 10 — CONFIGURATION REFERENCE

## config.yaml — Every Option Explained

```
pipeline:
  timezone: MDT
    ↳ The timezone for "today" — affects which matches are
      included in today's briefing. MDT = Mountain Daylight Time.

  utc_offset_hours: -6
    ↳ MDT is UTC-6. Change to -7 in winter (MST).
      Update this every November (clocks fall back)
      and every March (clocks spring forward).

  midnight_cron: "0 0 * * *"
    ↳ When the main pipeline runs. Default: midnight MDT.
      Cron syntax: minute hour day month weekday.

  topup_cron: "0 6 * * *"
    ↳ When the lineup top-up runs. Default: 6 AM MDT.

  email_cron: "0 8 * * *"
    ↳ When the email compiles and sends. Default: 8 AM MDT.

  log_dir: /home/sujeet/match-intel/logs
    ↳ Where daily log files are written. Directory is created
      automatically if it doesn't exist.

  always_send_email: true
    ↳ If true, the email sends even when there are zero matches.
      The email shows a "no fixtures today" message.
      Recommended: keep as true for reliability.

email:
  recipient: YOUR_EMAIL@gmail.com
    ↳ The email address that receives the morning briefing.

  sender: YOUR_BOT_GMAIL@gmail.com
    ↳ The Gmail address that sends the email. Must match
      the Gmail account whose App Password is in .env.

  subject_template: "🏏 Cricket Intel — {weekday}, {date} MDT"
    ↳ Email subject line. {weekday} and {date} are replaced
      with the actual day and date at send time.

  smtp_host: smtp.gmail.com
    ↳ Gmail's SMTP server. Do not change.

  smtp_port: 587
    ↳ STARTTLS port for Gmail. Do not change.

cricket:
  international:
    formats: [ODI, T20I]
      ↳ Only these match formats are included from international
        cricket. Remove T20I to only get ODIs. Remove ODI to
        only get T20Is. Tests are never included.

    gender: [men, women]
      ↳ Both men's and women's international matches are included.
        Remove "women" to only receive men's matches.

    tier1_nations: [list of 12 nations]
      ↳ Only matches where BOTH teams are in this list are included.
        Add or remove nations to expand/narrow coverage.

  leagues:
    - id: MLC
      full_name: "Major League Cricket"
      gender: men
      format: "MLC T20"
      active_months: [7]
        ↳ MLC appears in the email only in months listed here.
          Currently July only. Add months to extend coverage.
          E.g. [6, 7] would include June and July.
      teams: [list of 6 franchise names]
        ↳ Used for filtering CricAPI results to MLC matches only.

mac_mini:
  host: 192.168.1.XXX
    ↳ Your Mac Mini's local IP address. Find with:
      ipconfig getifaddr en0 (on Mac Mini terminal).
      This must be updated before the first pipeline run.

  port: 8001
    ↳ Port for our FastAPI wrapper. Do not change unless
      you changed the FastAPI launch configuration.

  extraction_model: mlx-community/Qwen2.5-14B-Instruct-4bit
    ↳ Model used for Exa text extraction.
      Must match the model name as oMLX reports it.
      Check with: curl localhost:8000/v1/models

  analysis_model: mlx-community/Qwen2.5-32B-Instruct-4bit
    ↳ Model used for deep 3-pass match analysis.
      Same note — must match oMLX's reported model name.

  extraction_timeout_secs: 90
    ↳ How long to wait for a /extract response before giving up.

  analysis_timeout_mins: 20
    ↳ How long to wait for a /analyze response before giving up.
      20 minutes is generous for 32B model 3-pass analysis.

  max_retries: 2
    ↳ How many times to retry a failed Mac Mini call before
      giving up and moving on.

  health_retries: 5
    ↳ How many times to check Mac Mini /health at startup
      before aborting the pipeline.

  health_retry_interval_secs: 30
    ↳ Seconds between health check retries.

database:
  host: localhost
    ↳ PostgreSQL is on Lenovo itself. localhost is correct.

  port: 5432
    ↳ PostgreSQL default port.

  name: cricket_intel
    ↳ Database name created during setup.

  user: pipeline
    ↳ Database user created during setup.

  pool_min: 2
  pool_max: 10
    ↳ Connection pool size. Min = always-open connections.
      Max = maximum simultaneous connections. 2/10 is fine for
      this workload which runs sequentially overnight.
```

## .env — Secrets File

The `.env` file sits in the project root and is read by `python-dotenv` at startup. It must never be committed to version control. It contains:

| Variable | Description | Where to get it |
|---|---|---|
| `GMAIL_APP_PASSWORD` | 16-character Gmail App Password | Google Account → Security → 2-Step Verification → App passwords |
| `DB_PASSWORD` | PostgreSQL password for the `pipeline` user | Set by you during PostgreSQL setup |
| `CRICAPI_KEY` | CricAPI authentication key | Register at cricapi.com |
| `EXA_API_KEY` | Exa API key | Register at exa.ai |
| `MAC_MINI_HOST` | Mac Mini IP (also in config.yaml — keep in sync) | ipconfig getifaddr en0 |
| `MAC_MINI_PORT` | FastAPI port (8001) | Should always match config.yaml |

---

---

# SECTION 11 — ROBUSTNESS & FAILURE HANDLING

## The Seven Laws

These are the core robustness guarantees. The system is designed so that every one of these holds true regardless of what fails:

**Law 1: The email always sends at 8:00 AM MDT**
No partial pipeline failure, Mac Mini outage, or data gap prevents email delivery. The email may contain less information than usual, but it always arrives. If Stage 5 encounters an error, a minimal fallback HTML email is generated instead. Stage 6 sends whatever it receives.

**Law 2: Every stage is independently recoverable**
Every stage writes `RUNNING` to `pipeline_runs` before it starts and updates to `DONE` or `FAILED` when it ends. If the Lenovo server crashes at 2 AM mid-Stage 2, you can query `pipeline_runs` to see exactly where it stopped. You can then re-run just Stage 3 manually. Matches already enriched are not re-enriched (upsert with COALESCE).

**Law 3: Source failures never cascade**
If an Exa search fails for the H2H data for Match 3, Stage 2 logs the failure and moves on to venue stats for Match 3. If venue stats also fails, it moves to injury news. If all 7 tasks fail for a match, the match still appears in the email — just without enrichment data, and with the "AI analysis unavailable" banner.

**Law 4: Mac Mini analysis failures are isolated per match**
If Mac Mini's 3-pass analysis fails or times out for Match 2, that match is marked as analysis-failed. Stage 3 continues to Match 3. The email card for Match 2 shows a banner. Matches 1, 3, and 4 show full analysis.

**Law 5: CricAPI limit is never a risk**
The system uses approximately 15–16 CricAPI calls per day in normal operation and at most ~40 on an extremely busy day. The 100-call daily limit provides 2.5–6× headroom. The system never retries CricAPI calls in a loop.

**Law 6: Exa limit is never a risk**
Normal monthly usage is ~1,200 requests out of a 20,000 monthly budget (6%). Even at 10× normal usage, the budget would not be exceeded.

**Law 7: Every email is archived forever**
The full rendered HTML of every email is stored in the `email_log` table's `html_snapshot` column. Even if the email failed to send, the compiled HTML is still there. You can query it at any time to review a past briefing.

## Failure Scenarios and System Response

| Failure Scenario | System Response |
|---|---|
| Mac Mini unreachable at midnight | Pipeline aborts Stages 1–3. Stages 4–6 run normally at their scheduled times. Email sends with "no analysis available" for all matches. |
| Mac Mini unreachable at 6 AM | Stage 4 (top-up) skips extraction steps. Match statuses are still refreshed. Email compiles from Stage 3 analysis data. |
| CricAPI returns no matches | Stage 1 completes with 0 matches. Email sends with "no fixtures today" message. |
| Exa returns no results for a query | That specific data field is null. AI analysis proceeds with reduced context. Analysis may be less specific but still runs. |
| oMLX analysis times out | After 20 min timeout + 1 retry, match is skipped. analysis_complete = false. Banner shown in email. |
| Gmail SMTP fails | Email send failure is logged to email_log. No automatic retry. Manual re-run: `python orchestrator.py email`. |
| Lenovo crashes mid-pipeline | On next run (next night), pipeline starts fresh. Previous partial data in DB is available. Can also re-run specific stage manually. |
| Open-Meteo request fails | Weather data is null for that match. No dew note in the email card. Pipeline continues normally. |

---

---

# SECTION 12 — TIMING & SCHEDULE

## Timezone Context

The reader is in **MDT (Mountain Daylight Time = UTC-6)**.

When 8:00 AM MDT arrives:

| World Region | Local Time | Impact on Match Status |
|---|---|---|
| India / Sri Lanka / Bangladesh | 7:30 PM IST (previous evening) | Evening matches from the night before appear as COMPLETED |
| Pakistan | 7:00 PM PKT (previous evening) | Same as India |
| Australia (AEST) | 12:00 AM AEST (midnight) | Day matches may be IN_PROGRESS or COMPLETED |
| New Zealand | 2:00 AM NZST | Late evening matches COMPLETED |
| England / Ireland | 3:00 PM BST | Afternoon matches are PREVIEW |
| South Africa | 4:00 PM SAST | Afternoon matches are PREVIEW |
| USA (MLC) | 7:30 AM / 8:00 AM local | MLC evening matches are always PREVIEW |
| West Indies | 12:00 PM / 1:00 PM AST | Midday matches are PREVIEW |

This timezone reality makes the system significantly more useful than a simple "today's matches" listing. Asian cricket fans (or those following Asian teams) get post-match recaps with the analysis framing. European and American matches are full previews. The email covers the full 24-hour cricket day intelligently.

## MDT vs MST

MDT applies during summer (roughly March to November). MST (UTC-7) applies in winter. The `utc_offset_hours` in config.yaml and the `MDT` constant in `utils/timezone.py` must both be manually updated when clocks change. This happens twice a year:
- Second Sunday in March: change -7 to -6 (spring forward)
- First Sunday in November: change -6 to -7 (fall back)

## MLC Season Window

MLC currently runs in July. The `active_months: [7]` setting in config.yaml controls when MLC fixtures are scraped and when the MLC section appears in the email. Outside of July, the system completely ignores MLC — no Exa searches, no CricAPI filtering, no email section. This requires zero manual intervention — it is controlled entirely by the current month.

---

---

# SECTION 13 — SETUP ORDER FOR GEMINI

Complete every step before moving to the next. Test each step before proceeding.

## Phase 1: Mac Mini — oMLX

1. Download and install oMLX from omlx.ai
2. Download `mlx-community/Qwen2.5-32B-Instruct-4bit` model via oMLX dashboard
3. Download `mlx-community/Qwen2.5-14B-Instruct-4bit` model via oMLX dashboard
4. Configure oMLX to listen on `0.0.0.0` (not just localhost)
5. Start oMLX and verify it responds on port 8000 locally
6. Create and load the oMLX LaunchAgent plist for auto-start
7. **Test:** `curl http://localhost:8000/v1/models` returns JSON list of both models

## Phase 2: Mac Mini — FastAPI Service

1. Create the `~/match-intel-service/` directory and all subdirectories
2. Install Python packages (fastapi, uvicorn, openai, pydantic, python-dotenv)
3. Create `main.py`, `models/extract.py`, `models/analyze.py`
4. Create `services/extractor.py` and `services/analyzer.py`
5. Start FastAPI manually and verify it starts without errors
6. Create and load the FastAPI LaunchAgent plist for auto-start on port 8001
7. Configure Mac Mini firewall to allow inbound connections on port 8001
8. **Test:** `curl http://localhost:8001/health` returns `{"status":"ok"}`
9. **Test from Lenovo:** `curl http://MAC_MINI_IP:8001/health` returns `{"status":"ok"}`

## Phase 3: Lenovo — PostgreSQL

1. Install PostgreSQL 15 via apt
2. Start PostgreSQL service and enable auto-start
3. Create the `cricket_intel` database
4. Create the `pipeline` user with a strong password
5. Grant privileges to the pipeline user
6. Create the project directory structure at `/home/sujeet/match-intel/`
7. Save `schema.sql` and run it against the `cricket_intel` database
8. **Test:** Connect as the pipeline user and run `SELECT * FROM todays_status;` — should return 0 rows with no error

## Phase 4: Lenovo — Python Environment

1. Install Python 3.11 and python3.11-venv via apt
2. Create virtual environment at `/home/sujeet/match-intel/venv/`
3. Activate the virtual environment
4. Install all pip packages from requirements.txt
5. **Test:** Import each key package to verify installation

## Phase 5: Lenovo — Configuration

1. Create `config.yaml` with all settings — especially update `mac_mini.host` with the actual Mac Mini IP
2. Create `.env` with all five secrets
3. **Test:** Read config.yaml from Python, verify all keys exist

## Phase 6: Lenovo — API Clients

1. Create `scrapers/cricapi_client.py`
2. Create `scrapers/exa_client.py`
3. Create `scrapers/weather_client.py`
4. **Test CricAPI:** Call `get_upcoming_matches()` and verify it returns a list
5. **Test Exa:** Call `search_cricket_h2h("India", "Australia", "T20I")` and verify it returns text
6. **Test Open-Meteo:** Call `get_weather("Eden Gardens", "2026-07-01")` and verify it returns a dict

## Phase 7: Lenovo — Database Layer

1. Create `database/connection.py`
2. Create `database/queries.py`
3. **Test:** Call `log_stage_start(today, "TEST")` and verify a row appears in `pipeline_runs`

## Phase 8: Lenovo — Utilities

1. Create `utils/logger.py`
2. Create `utils/mac_mini_client.py`
3. Create `utils/timezone.py`
4. **Test Mac Mini client:** Call `health_check()` and verify it returns True
5. **Test extraction:** Call `extract("h2h", "cricket — T20I", "sample text", "India", "Australia")` — verify it returns a dict

## Phase 9: Lenovo — Pipeline Stages

1. Create `pipeline/orchestrator.py`
2. Create `pipeline/stage1_fixtures.py`
3. **Test Stage 1 manually:** Run `python orchestrator.py pipeline` — check DB for matches
4. Create `pipeline/stage2_enrichment.py`
5. **Test Stage 2 manually:** Verify processed_match_data rows are created
6. Create `pipeline/stage3_analysis.py`
7. **Test Stage 3 manually:** Verify ai_analysis rows are created with analysis_complete = true
8. Create `pipeline/stage4_topup.py`
9. Create `pipeline/stage5_compile.py`
10. Create `pipeline/stage6_send.py`

## Phase 10: Lenovo — Email Template

1. Create `email_builder/compiler.py`
2. Create `email_builder/templates/daily_briefing.html`
3. **Test:** Run `python orchestrator.py email` — check inbox for email

## Phase 11: Lenovo — Cron Jobs

1. Open crontab with `crontab -e`
2. Add three cron entries pointing to the venv Python and orchestrator.py
3. Entries: midnight (pipeline), 6 AM (topup), 8 AM (email)
4. Each entry should redirect stdout and stderr to cron.log
5. Create the logs/ directory manually if it doesn't exist
6. **Test:** Temporarily change the email cron to 2 minutes in the future, wait for it to fire, verify email arrives, then restore to 8 AM

---

---

# SECTION 14 — TESTING APPROACH

## Testing Strategy

Testing happens in two modes:

**Unit testing** — test each component in isolation before integrating
**Integration testing** — test the full end-to-end pipeline once all components exist

## Key Tests to Verify

| Test | What to Check | Expected Result |
|---|---|---|
| oMLX health | `curl localhost:8000/v1/models` on Mac Mini | JSON with both model names |
| FastAPI health (local) | `curl localhost:8001/health` on Mac Mini | `{"status":"ok"}` |
| FastAPI health (remote) | `curl MAC_MINI_IP:8001/health` on Lenovo | `{"status":"ok"}` |
| PostgreSQL connection | Connect as pipeline user, query todays_status view | 0 rows, no errors |
| CricAPI connection | Call get_upcoming_matches() | List of match dicts returned |
| Exa search | Search for H2H between two real teams | Text string with cricket content |
| Open-Meteo | Get weather for Eden Gardens | Dict with rain and humidity data |
| Mac Mini extraction | Send sample cricket text, request h2h extraction | Structured JSON dict returned |
| Stage 1 manual run | Run `python orchestrator.py pipeline` | Matches appear in DB |
| Stage 2 manual run | Check processed_match_data after Stage 1 | Enrichment columns populated |
| Stage 3 manual run | Check ai_analysis after Stage 2 | analysis_complete = true rows |
| Full email test | Run `python orchestrator.py email` | Email received in inbox |
| Email HTML quality | Open received email | Dark theme, correct sections, match cards visible |
| Cron test | Set cron 2 min ahead, wait | Email arrives at exact scheduled time |

## Monitoring After Deployment

The simplest daily health check is: **did the email arrive?** If yes, the system is working. If no, check:

1. `tail -50 /home/sujeet/match-intel/logs/cron.log` — cron output
2. `tail -50 /home/sujeet/match-intel/logs/YYYY-MM-DD.log` — pipeline log
3. `psql -U pipeline -d cricket_intel -c "SELECT stage_name, status, error_log FROM pipeline_runs WHERE run_date = CURRENT_DATE ORDER BY id;"` — which stage failed
4. `curl http://MAC_MINI_IP:8001/health` — is Mac Mini still reachable

---

---

# SECTION 15 — IMPORTANT NOTES & CONSTRAINTS

## Mac Mini Model Name Verification

The exact string to use for `extraction_model` and `analysis_model` in config.yaml depends on how oMLX reports the model names. After downloading models, run:

```
curl http://localhost:8000/v1/models
```

Copy the exact model `id` strings from the response and use those in config.yaml and in the FastAPI service files (the EXTRACTION_MODEL and ANALYSIS_MODEL constants).

## Mac Mini IP Address

The Mac Mini's local IP address can change if your router assigns IPs dynamically. To prevent this, configure your home router to assign a fixed/reserved IP address to the Mac Mini based on its MAC address. This is a one-time router configuration that permanently binds the Mac Mini to the same IP (e.g. 192.168.1.105) forever.

## Seasonal Timezone Update

Twice a year you must manually update two values:

- In `config.yaml`: change `utc_offset_hours` between -6 (MDT, summer) and -7 (MST, winter)
- In `utils/timezone.py`: change the MDT timezone offset constant accordingly

Dates to remember:
- Second Sunday in March: spring forward — change -7 to -6
- First Sunday in November: fall back — change -6 to -7

## CricAPI Data Filtering

CricAPI returns all cricket globally — domestic leagues, associate nations, age-group cricket, everything. The `filter_international_fixtures()` function uses fuzzy name matching to find ICC Full Member nations. Occasionally a team name variant may be missed (e.g. "West Indies A" vs "West Indies"). If you notice a valid match being missed, add the variant team name to the tier1_nations list or adjust the matching logic.

## Exa Query Quality

The quality of the data extracted depends on the quality of the Exa queries. If you find that H2H records are repeatedly missing or inaccurate, try adding the current year to the query or being more specific about the format. Example: instead of "India Pakistan T20I head to head" try "India vs Pakistan T20I head to head results 2023 2024 2025 statistics."

## Email Client Compatibility

The email template is designed for modern email clients with good HTML and CSS support: Gmail (web and mobile), Apple Mail, Outlook for Mac. Some older Outlook versions (Windows) strip embedded CSS. If Outlook Windows compatibility is needed, all CSS must be inlined using a tool called `premailer` (a Python library). This is not implemented in the current design.

## Database Growth

The database grows modestly over time. The main concern is the `html_snapshot` column in `email_log`, which stores the full HTML of each sent email (~50–100 KB each). After a year of daily emails, this is ~35 MB — negligible. After several years, consider nullifying old snapshots while retaining the metadata rows.

The `raw_scraped_data` table also grows continuously. After 90 days, rows older than 90 days can be safely deleted — they are audit data only and not used by any pipeline function.

## Pitch Report Timing

Pitch reports are published by ground curators typically 24–48 hours before a match. For matches starting very late in the MDT day (e.g. a match starting at 7 PM MDT tomorrow morning in Australia), the pitch report may not yet be available at midnight when Stage 2 runs. The Stage 4 top-up scrape at 6 AM gives a second chance to capture pitch reports that were published after midnight.

## MLC Season Note

MLC has been running since 2023 as a US-based T20 franchise league held in July. The `active_months: [7]` setting reflects the current typical season window. If MLC expands its season in future years, simply update this list (e.g. `[7, 8]` for July and August). No code changes are needed.

---

---

*Document Version: 2.0 — Final Architecture*
*System: Cricket Intelligence Email Pipeline*
*Hardware: Lenovo IdeaPad Sujeet-PC (Debian 12) + Mac Mini M4 (macOS)*
*Coverage: International ODI + T20I (men + women) · MLC (men, July)*
*Email delivery: 8:00 AM MDT daily*
*Total monthly API cost: $0 — all free tier or self-hosted*
