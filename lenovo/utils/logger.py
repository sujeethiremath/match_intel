import sys
import os
from loguru import logger

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.getenv("LOG_DIR", os.path.join(BASE_DIR, "logs"))
os.makedirs(LOG_DIR, exist_ok=True)

# Remove default handler
logger.remove()

# Console handler — INFO level
logger.add(
    sys.stderr,
    level="INFO",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> — <level>{message}</level>",
    colorize=True,
)

# File handler — DEBUG level, daily rotation, 30-day retention
logger.add(
    os.path.join(LOG_DIR, "pipeline_{time:YYYY-MM-DD}.log"),
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} — {message}",
    rotation="00:00",
    retention="30 days",
    compression="gz",
    enqueue=True,
)

log = logger
