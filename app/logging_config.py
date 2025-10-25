import os
import logging
from logging.handlers import RotatingFileHandler
from app.tasks import send_error_email


class CeleryEmailHandler(logging.Handler):
    """Custom logging handler that sends error logs via Celery email task."""

    def emit(self, record):
        try:
            subject = f"[ERROR LOG] {record.levelname} in {record.module}"
            message = self.format(record)

            # Queue async Celery task
            send_error_email.delay(subject, message)

        except Exception as e:
            # Use a plain internal fallback logger, not this same handler (to avoid recursion)
            logging.getLogger("internal_logger").error(
                f"Failed to queue email task: {e}"
            )


# === Configuration ===
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FILE = os.getenv("LOG_FILE", "logs/app.log")

# Ensure logs directory exists
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

# === Root logger setup ===
logger = logging.getLogger("app_logger")
logger.setLevel(LOG_LEVEL)

# === Format ===
formatter = logging.Formatter(
    "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
)

# === Console Handler ===
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)

# === Rotating File Handler ===
file_handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=5_000_000,  # 5 MB
    backupCount=5,       # Keep last 5 rotated files
    encoding="utf-8",
)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)

# === Celery Email Handler ===
email_handler = CeleryEmailHandler()
email_handler.setLevel(logging.ERROR)
email_handler.setFormatter(formatter)

# === Register handlers ===
logger.addHandler(console_handler)
logger.addHandler(file_handler)
logger.addHandler(email_handler)

# === Internal fallback logger (used inside CeleryEmailHandler) ===
internal_logger = logging.getLogger("internal_logger")
internal_logger.addHandler(console_handler)
internal_logger.setLevel(logging.WARNING)


def get_logger(name: str = None):
    """
    Returns a child logger from the main app logger.
    Usage: logger = get_logger(__name__)
    """
    return logger.getChild(name) if name else logger
