# Match Intel — Configuration Reference

This reference describes the configuration parameters, environment variables, `config.yaml` schema, and scheduling options available in **Match Intel**.

---

## 1. Environment Variables Reference

Environment variables are loaded from `lenovo/.env` using `python-dotenv`.

| Variable Name | Description | Default Value | Required? |
|---|---|---|---|
| `GMAIL_APP_PASSWORD` | 16-character Gmail App Password for SMTP | None | Yes (for Stage 6) |
| `DB_PASSWORD` | PostgreSQL user password | `""` | Yes |
| `CRICAPI_KEY` | CricAPI feed authentication key | `""` | Optional (if SearXNG fallback active) |
| `EXA_API_KEY` | Exa AI Search API key | `""` | Optional (if SearXNG active) |
| `MAC_MINI_HOST` | Hostname/IP of AI inference service | `localhost` | Yes |
| `MAC_MINI_PORT` | Port of AI inference service | `8001` | Yes |
| `MAC_MINI_MAC_ADDRESS` | Ethernet MAC address for WoL wake-up | `00:11:22:33:44:55` | Optional |
| `SEARXNG_URL` | Base URL of self-hosted SearXNG search | `http://localhost:8080` | Yes |
| `EMAIL_RECIPIENT` | Target email address for briefing report | Config value | Optional override |
| `EMAIL_SENDER` | Sender Gmail address | Config value | Optional override |
| `LOG_DIR` | Output directory for log files | `logs` | Optional |

---

## 2. `config.yaml` Configuration Schema

The central configuration file located at `lenovo/config.yaml` controls pipeline behaviors, league definitions, model selections, and database pool settings:

```yaml
pipeline:
  timezone: MDT
  utc_offset_hours: -6
  midnight_scrape_cron: "0 0 * * *"
  topup_scrape_cron: "0 6 * * *"
  email_send_cron: "0 8 * * *"
  log_dir: logs
  always_send_email: true

email:
  recipient: your_recipient@example.com
  sender: your_sender@example.com
  subject_template: "🏏 Cricket Intelligence — {weekday}, {date} MDT"
  smtp_host: smtp.gmail.com
  smtp_port: 587

cricket:
  international:
    formats:
      - ODI
      - T20I
    gender:
      - men
      - women
  tier1_nations:
    - India
    - Australia
    - England
    - Pakistan
    - South Africa
    - New Zealand
    - West Indies
    - Sri Lanka
    - Bangladesh
    - Zimbabwe
    - Afghanistan
    - Ireland
  leagues:
    mlc:
      name: Major League Cricket
      active_months:
        - 6
        - 7
      format: MLC T20
      teams:
        - MI New York
        - Los Angeles Knight Riders
        - Seattle Orcas
        - Washington Freedom
        - San Francisco Unicorns
        - Texas Super Kings

mac_mini:
  host: localhost
  port: 8001
  extraction_model: mlx-community/Qwen2.5-14B-Instruct-4bit
  analysis_model: mlx-community/Qwen2.5-14B-Instruct-4bit
  health_check_retries: 5
  health_check_interval_secs: 30

database:
  host: 127.0.0.1
  port: 5432
  name: match_intel
  user: pipeline
  pool_min: 2
  pool_max: 10
```

---

## 3. Cron Scheduling Configuration

To automate daily execution on Linux systems, add these jobs via `crontab -e`:

```cron
# 00:00 MDT — Scrape fixtures, enrich context, and run AI predictions
0 0 * * * cd /path/to/match_intel/lenovo && ./run.sh pipeline >> logs/midnight.log 2>&1

# 06:00 MDT — Top up early starting lineups and playing XI
0 6 * * * cd /path/to/match_intel/lenovo && ./run.sh topup >> logs/topup.log 2>&1

# 08:00 MDT — Render Jinja2 template and send briefing email
0 8 * * * cd /path/to/match_intel/lenovo && ./run.sh email >> logs/email.log 2>&1
```
