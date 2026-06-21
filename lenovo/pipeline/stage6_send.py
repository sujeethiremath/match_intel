import os
import smtplib
import yaml
from datetime import date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from utils.logger import log
from database.queries import (
    log_stage_start,
    log_stage_done,
    log_stage_failed,
    create_email_log,
    mark_email_sent,
    mark_email_failed,
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))


def get_config():
    with open(os.path.join(BASE_DIR, "config.yaml"), "r") as f:
        return yaml.safe_load(f)


def run_stage6(today: date, html: str, match_count: int) -> bool:
    """
    Stage 6: Email Sending.
    Sends the compiled briefing HTML via Gmail SMTP and records it.
    """
    stage_id = log_stage_start(today, "stage6_send")
    log.info(f"=== Stage 6: Email Sending for {today} ===")

    config = get_config()
    email_cfg = config["email"]
    recipient = email_cfg["recipient"]
    sender = email_cfg["sender"]

    log_id = create_email_log(today, recipient)

    date_str = today.strftime("%B %d, %Y")
    subject = email_cfg["subject_template"].replace("{weekday}", today.strftime("%A")).replace("{date}", date_str)

    try:
        # Construct MIME Message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = recipient

        # Fallback text
        msg.attach(MIMEText(f"Cricket Intelligence Briefing for {date_str}. Please view in an HTML-compatible client.", "plain"))
        msg.attach(MIMEText(html, "html"))

        # Send via Gmail SMTP
        gmail_app_password = os.getenv("GMAIL_APP_PASSWORD")
        if not gmail_app_password:
            raise ValueError("GMAIL_APP_PASSWORD not found in environment variables")

        log.info(f"Connecting to SMTP server {email_cfg['smtp_host']}:{email_cfg['smtp_port']}...")
        with smtplib.SMTP(email_cfg["smtp_host"], email_cfg["smtp_port"]) as smtp:
            smtp.starttls()
            log.info("Logging in...")
            smtp.login(sender, gmail_app_password)
            log.info(f"Sending email to {recipient}...")
            smtp.send_message(msg)

        mark_email_sent(log_id, match_count, html)
        log.info("Email sent successfully!")
        log_stage_done(stage_id, match_count, f"Email sent to {recipient}")
        return True

    except Exception as e:
        error_msg = f"Failed to send email: {str(e)}"
        log.exception(error_msg)
        mark_email_failed(log_id, error_msg)
        log_stage_failed(stage_id, error_msg)
        return False