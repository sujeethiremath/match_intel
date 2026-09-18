# Match Intel — Developer & Setup Guide

This guide provides instructions for setting up a local development environment, running tests, debugging pipeline stages, and contributing to **Match Intel**.

---

## 1. Local Development Environment

### Prerequisites
- **Python 3.10+** (Python 3.14 recommended)
- **PostgreSQL 14+**
- **Git**
- **Docker** (optional, for running local SearXNG)

---

## 2. Setting Up the Repository

```bash
# Clone repository
git clone https://github.com/sujeethiremath/match_intel.git
cd match_intel

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r lenovo/requirements.txt
```

---

## 3. Database Initialization

1. Ensure PostgreSQL is running locally:
   ```bash
   pg_isready
   ```

2. Create the target database and user:
   ```sql
   CREATE DATABASE match_intel;
   CREATE USER pipeline WITH PASSWORD 'your_dev_password';
   GRANT ALL PRIVILEGES ON DATABASE match_intel TO pipeline;
   ```

3. Load the database schema:
   ```bash
   psql -d match_intel -U pipeline -f lenovo/database/schema.sql
   ```

---

## 4. Environment Configuration

Copy the sample environment file to `.env`:

```bash
cp .env.example lenovo/.env
```

Configure `lenovo/.env` with your development parameters:

```ini
GMAIL_APP_PASSWORD=your_gmail_app_password
DB_PASSWORD=your_dev_password
CRICAPI_KEY=your_cricapi_key
EXA_API_KEY=your_exa_api_key
MAC_MINI_HOST=localhost
MAC_MINI_PORT=8001
SEARXNG_URL=http://localhost:8080
EMAIL_RECIPIENT=dev@example.com
EMAIL_SENDER=dev@example.com
```

---

## 5. Running the AI Inference Service Locally

To run the Mac Mini FastAPI service locally for testing:

```bash
cd mac_mini_service
source ../venv/bin/activate

# Launch service on port 8001
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

Verify service status:
```bash
curl http://localhost:8001/health
# Expected output: {"status": "ok", "service": "match-intel-ai"}
```

---

## 6. Running & Debugging Pipeline Stages

From the `lenovo/` directory, you can trigger individual pipeline stages:

```bash
cd lenovo

# Run complete pipeline for today's date
./run.sh pipeline

# Run complete pipeline for a specific date
./run.sh pipeline --date 2026-07-20

# Run specific stage only:
./run.sh stage1   # Fixture discovery
./run.sh stage2   # Search enrichment
./run.sh stage3   # AI analysis & prediction
./run.sh topup    # Lineup top-up
./run.sh email    # Jinja2 compile & SMTP send
```

---

## 7. Testing & Quality Assurance

### Code Compilation Check
Ensure all Python files compile cleanly without syntax errors:

```bash
python3 -m py_compile lenovo/pipeline/*.py lenovo/scrapers/*.py mac_mini_service/*.py
```

### Log Inspection
Logs are saved in `lenovo/logs/` with daily rotation. Inspect live logs with:

```bash
tail -f lenovo/logs/pipeline_*.log
```

---

## 8. Code Style Guidelines

- **PEP 8**: Follow standard Python code style guidelines.
- **Type Hints**: Use standard Python type annotations wherever possible (`def parse(data: dict) -> list:`).
- **Environment Isolation**: Never hardcode credentials, IP addresses, or home directory paths in source code. Use `os.getenv()` with safe defaults.
