from celery import Celery

celery_app = Celery(
    "whatsapp_scheduler",
    broker="sqla+sqlite:///celery_broker.db",
    backend="db+sqlite:///celery_results.db" 
)

celery_app.conf.update(
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "check-scheduled-statuses": {
            "task": "app.tasks.schedule_status_task",
            "schedule": 1800.0,  # every 30 min
        }
    }
)