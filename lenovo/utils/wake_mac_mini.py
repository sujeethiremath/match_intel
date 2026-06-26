"""
Wake-on-LAN utility for the Mac Mini M4.

Sends a WoL magic packet using the Mac Mini's Ethernet MAC address,
then polls the /health endpoint until the service is responsive.
"""
import time
import subprocess
import httpx
import yaml
import os
from utils.logger import log
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

with open(os.path.join(BASE_DIR, "config.yaml"), "r") as f:
    _cfg = yaml.safe_load(f)

MAC_HOST = os.getenv("MAC_MINI_HOST", _cfg["mac_mini"]["host"])
MAC_PORT = int(os.getenv("MAC_MINI_PORT", _cfg["mac_mini"]["port"]))

# Mac Mini M4 primary Ethernet MAC address (en0)
# Change this if you switch to a different network interface
MAC_MINI_HARDWARE_MAC = os.getenv("MAC_MINI_MAC_ADDRESS", "1c:f6:4c:4b:e6:90")

# Wake-up configuration
WAKE_WAIT_SECS = 90       # Max seconds to wait after sending WoL packet
WAKE_POLL_INTERVAL = 5    # Check every N seconds
HEALTH_URL = f"http://{MAC_HOST}:{MAC_PORT}/health"


def _send_magic_packet(mac_address: str) -> bool:
    """Send a Wake-on-LAN magic packet using the system wakeonlan command."""
    try:
        result = subprocess.run(
            ["wakeonlan", mac_address],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            log.info(f"WoL magic packet sent to {mac_address}")
            return True
        else:
            log.error(f"wakeonlan command failed: {result.stderr.strip()}")
            return False
    except FileNotFoundError:
        log.error("wakeonlan binary not found — install it with: sudo apt install wakeonlan")
        return False
    except Exception as e:
        log.error(f"Failed to send WoL packet: {e}")
        return False


def _is_mac_mini_responsive() -> bool:
    """Check if the Mac Mini FastAPI service is responding."""
    try:
        with httpx.Client(timeout=8.0) as client:
            resp = client.get(HEALTH_URL)
            return resp.status_code == 200
    except Exception:
        return False


def wake_mac_mini(
    mac_address: str = None,
    wait_secs: int = WAKE_WAIT_SECS,
    poll_interval: int = WAKE_POLL_INTERVAL,
) -> bool:
    """
    Wake the Mac Mini using Wake-on-LAN and wait for its FastAPI service to come up.

    Args:
        mac_address: Hardware MAC address of the Mac Mini (defaults to config value).
        wait_secs: Maximum seconds to wait for the service to become responsive.
        poll_interval: How often (in seconds) to poll the health endpoint.

    Returns:
        True if the Mac Mini is responsive within wait_secs, False otherwise.
    """
    mac_address = mac_address or MAC_MINI_HARDWARE_MAC

    # Check if Mac Mini is already awake — skip WoL if so
    if _is_mac_mini_responsive():
        log.info("Mac Mini is already awake and responsive. No WoL needed.")
        return True

    log.info(f"Mac Mini not responsive. Sending Wake-on-LAN packet to {mac_address}...")
    if not _send_magic_packet(mac_address):
        log.error("Failed to send WoL packet. Cannot wake Mac Mini.")
        return False

    log.info(f"WoL packet sent. Waiting up to {wait_secs}s for Mac Mini to wake up...")
    elapsed = 0
    while elapsed < wait_secs:
        time.sleep(poll_interval)
        elapsed += poll_interval
        if _is_mac_mini_responsive():
            log.info(f"Mac Mini is awake and responsive after {elapsed}s! ✓")
            return True
        log.info(f"  Still waiting... ({elapsed}/{wait_secs}s)")

    log.error(f"Mac Mini did not respond within {wait_secs}s after WoL packet.")
    return False
