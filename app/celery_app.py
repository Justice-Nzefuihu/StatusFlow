from celery import Celery
from celery.schedules import crontab

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
            "schedule": crontab(minute="*/15", hour="7-13"),  # from 7 to 1pm each day every 15 minutes
        },
        "update-is-uploaded-status":{
            'task': 'app.tasks.update_is_uploaded',
            "schedule": crontab(hour=0, minute=0), #end of the day
        }
    }
)