import logging
from celery import Celery
from celery.schedules import crontab
from .config import setting

logger = logging.getLogger(__name__)

try:
    celery_app = Celery(
        "whatsapp_scheduler",
        broker=setting.celery_broker_url,
        backend=setting.celery_result_backend,
    )
    logger.info("Celery app initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Celery app: {e}", exc_info=True)
    raise

try:
    celery_app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="Africa/Lagos",
        enable_utc=False,
        beat_schedule={
             "update-is-uploaded-status": {
                "task": "app.tasks.update_is_uploaded",
                "schedule": crontab(hour=00, minute=00),  # midnight daily
            },
            "check-scheduled-statuses": {
                "task": "app.tasks.schedule_status_task",
                "schedule": crontab(minute="*/15", hour="7-13"),  # from 7AM to 1PM every 15 minutes
            },
        },
    )
    logger.info("Celery configuration and beat schedule set successfully")
except Exception as e:
    logger.error(f"Failed to configure Celery: {e}", exc_info=True)
    raise

try:
    celery_app.autodiscover_tasks(["app"])
    logger.info("Celery autodiscover tasks executed successfully")
except Exception as e:
    logger.error(f"Failed to autodiscover tasks: {e}", exc_info=True)
    raise
