import os
import sys
import asyncio
import yaml
from datetime import date
from utils.logger import log
from utils.timezone import today_mdt
from utils.mac_mini_client import health_check
from utils.wake_mac_mini import wake_mac_mini

# Import stages
from pipeline.stage1_fixtures import run_stage1
from pipeline.stage2_enrichment import run_stage2
from pipeline.stage3_analysis import run_stage3
from pipeline.stage4_topup import run_stage4
from pipeline.stage5_compile import run_stage5
from pipeline.stage6_send import run_stage6

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_config():
    with open(os.path.join(BASE_DIR, "config.yaml"), "r") as f:
        return yaml.safe_load(f)


async def run_midnight_pipeline(today: date):
    """Run midnight discovery, enrichment, and analysis (Stages 1, 2, and 3)."""
    log.info(f"================ STARTING MIDNIGHT PIPELINE FOR {today} ================")

    # Stage 1 & 2 do NOT require the Mac Mini — always run them regardless
    log.info("Stage 1: Running fixture discovery...")
    stage1_ok = run_stage1(today)
    if not stage1_ok:
        log.warning("Stage 1 fixture discovery reported issues, continuing pipeline...")

    log.info("Stage 2: Running deep enrichment...")
    stage2_ok = run_stage2(today)
    if not stage2_ok:
        log.warning("Stage 2 deep enrichment reported issues, continuing pipeline...")

    # Stage 3 requires the Mac Mini — wake it up first via Wake-on-LAN if needed
    log.info("Waking up Mac Mini via Wake-on-LAN before AI analysis...")
    mac_awake = wake_mac_mini()
    if not mac_awake:
        log.error("Mac Mini did not respond after WoL attempt — skipping Stage 3 (AI analysis) for today.")
        log.info("Fixtures and enrichment data are saved. Analysis will run on next successful wake.")
        log.info(f"================ MIDNIGHT PIPELINE COMPLETE (no AI) FOR {today} ================")
        return

    log.info("Stage 3: Running AI analysis...")
    stage3_ok = await run_stage3(today)
    if not stage3_ok:
        log.warning("Stage 3 AI analysis reported issues.")

    log.info(f"================ MIDNIGHT PIPELINE COMPLETE FOR {today} ================")


def run_topup_pipeline(today: date):
    """Run 6 AM top-up scrape and lineups (Stage 4)."""
    log.info(f"================ STARTING TOP-UP PIPELINE FOR {today} ================")
    run_stage4(today)
    log.info(f"================ TOP-UP PIPELINE COMPLETE FOR {today} ================")


def run_email_pipeline(today: date):
    """Run 8 AM email compilation and sending (Stages 5 and 6)."""
    log.info(f"================ STARTING EMAIL PIPELINE FOR {today} ================")
    config = get_config()
    always_send = config.get("pipeline", {}).get("always_send_email", True)

    html, count, compile_ok = run_stage5(today)
    if not compile_ok:
        log.error("Stage 5 email compilation failed. Aborting email send.")
        sys.exit(1)

    if count == 0 and not always_send:
        log.info("No matches processed today and always_send_email is false. Skipping email send.")
        return

    send_ok = run_stage6(today, html, count)
    if send_ok:
        log.info("Email briefing dispatched successfully!")
    else:
        log.error("Stage 6 email sending failed.")

    log.info(f"================ EMAIL PIPELINE COMPLETE FOR {today} ================")


def main():
    if len(sys.argv) < 2:
        print("Usage: python pipeline/orchestrator.py [pipeline|topup|email]")
        sys.exit(1)

    mode = sys.argv[1].lower()
    today = today_mdt()

    if mode == "pipeline":
        asyncio.run(run_midnight_pipeline(today))
    elif mode == "topup":
        run_topup_pipeline(today)
    elif mode == "email":
        run_email_pipeline(today)
    else:
        print(f"Unknown mode: {mode}")
        print("Usage: python pipeline/orchestrator.py [pipeline|topup|email]")
        sys.exit(1)


if __name__ == "__main__":
    main()