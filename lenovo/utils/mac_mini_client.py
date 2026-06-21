import os
import time
import httpx
import yaml
from dotenv import load_dotenv
from utils.logger import log

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

with open(os.path.join(BASE_DIR, "config.yaml"), "r") as f:
    _cfg = yaml.safe_load(f)

MAC_HOST = os.getenv("MAC_MINI_HOST", _cfg["mac_mini"]["host"])
MAC_PORT = int(os.getenv("MAC_MINI_PORT", _cfg["mac_mini"]["port"]))
EXTRACTION_TIMEOUT = _cfg["mac_mini"].get("extraction_timeout_secs", 90)
ANALYSIS_TIMEOUT_MINS = _cfg["mac_mini"].get("analysis_timeout_mins", 20)
HEALTH_RETRIES = _cfg["mac_mini"].get("health_check_retries", 5)
HEALTH_INTERVAL = _cfg["mac_mini"].get("health_check_interval_secs", 30)
EXTRACTION_MODEL = _cfg["mac_mini"].get("extraction_model", "mlx-community/Qwen2.5-14B-Instruct-4bit")
ANALYSIS_MODEL = _cfg["mac_mini"].get("analysis_model", "mlx-community/Qwen2.5-14B-Instruct-4bit")

BASE_URL = f"http://{MAC_HOST}:{MAC_PORT}"


def health_check(retries: int = None, interval: int = None) -> bool:
    """
    Check Mac Mini FastAPI health endpoint with retries.
    Returns True if healthy, False after exhausting retries.
    """
    retries = retries or HEALTH_RETRIES
    interval = interval or HEALTH_INTERVAL

    for attempt in range(1, retries + 1):
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(f"{BASE_URL}/health")
                if resp.status_code == 200:
                    log.info(f"Mac Mini health check passed (attempt {attempt})")
                    return True
                else:
                    log.warning(f"Mac Mini health check returned {resp.status_code} (attempt {attempt})")
        except httpx.ConnectError:
            log.warning(f"Mac Mini unreachable (attempt {attempt}/{retries})")
        except Exception as e:
            log.warning(f"Mac Mini health check error (attempt {attempt}): {e}")

        if attempt < retries:
            log.info(f"Retrying in {interval}s...")
            time.sleep(interval)

    log.error(f"Mac Mini health check failed after {retries} attempts")
    return False


def extract(extraction_type: str, sport_context: str, raw_text: str,
            team_a: str, team_b: str, timeout_secs: int = None) -> dict | None:
    """
    Call Mac Mini /extract endpoint to extract structured data from raw text.
    
    Args:
        extraction_type: e.g. 'h2h', 'team_form', 'venue_stats', 'injury_news', etc.
        sport_context: e.g. 'cricket ODI men'
        raw_text: The raw text content to extract from
        team_a: First team name
        team_b: Second team name
        timeout_secs: Override default timeout
    
    Returns:
        Extracted dict or None on failure
    """
    timeout_secs = timeout_secs or EXTRACTION_TIMEOUT

    payload = {
        "extraction_type": extraction_type,
        "sport_context": sport_context,
        "raw_text": raw_text,
        "team_a": team_a,
        "team_b": team_b,
        "model": EXTRACTION_MODEL,
    }

    try:
        with httpx.Client(timeout=httpx.Timeout(timeout_secs, connect=15.0)) as client:
            resp = client.post(f"{BASE_URL}/extract", json=payload)
            resp.raise_for_status()
            data = resp.json()
            log.debug(f"Extraction [{extraction_type}] succeeded for {team_a} vs {team_b}")
            return data.get("result", data)
    except httpx.TimeoutException:
        log.error(f"Extraction [{extraction_type}] timed out after {timeout_secs}s")
        return None
    except httpx.HTTPStatusError as e:
        log.error(f"Extraction [{extraction_type}] HTTP error: {e.response.status_code}")
        return None
    except Exception as e:
        log.error(f"Extraction [{extraction_type}] failed: {e}")
        return None


def analyze(payload_dict: dict, timeout_mins: int = None) -> dict | None:
    """
    Call Mac Mini /analyze endpoint to generate full match analysis.
    
    Args:
        payload_dict: Full match data payload for analysis
        timeout_mins: Override default timeout in minutes
    
    Returns:
        Analysis result dict or None on failure
    """
    timeout_mins = timeout_mins or ANALYSIS_TIMEOUT_MINS
    timeout_secs = timeout_mins * 60

    payload_dict["model"] = ANALYSIS_MODEL

    try:
        with httpx.Client(timeout=httpx.Timeout(timeout_secs, connect=15.0)) as client:
            resp = client.post(f"{BASE_URL}/analyze", json=payload_dict)
            resp.raise_for_status()
            data = resp.json()
            log.info("Analysis call succeeded")
            return data.get("result", data)
    except httpx.TimeoutException:
        log.error(f"Analysis timed out after {timeout_mins} minutes")
        return None
    except httpx.HTTPStatusError as e:
        log.error(f"Analysis HTTP error: {e.response.status_code} — {e.response.text[:300]}")
        return None
    except Exception as e:
        log.error(f"Analysis failed: {e}")
        return None
