from celery_app import celery_app
from post_status import send_status_images, send_status_texts
from app.database import sessionLocal
from app.model import StatusDB, ScheduleEnum, UserDB
from datetime import datetime, timedelta
from whatsapp_login import login_or_restore

def is_due_by_schedule(schedule: ScheduleEnum, days_diff: int) -> bool:
    schedule_map = {
        ScheduleEnum.EVERYDAY.value: 1,
        ScheduleEnum.EVERY_2_DAYS.value: 2,
        ScheduleEnum.EVERY_3_DAYS.value: 3,
        ScheduleEnum.EVERY_4_DAYS.value: 4,
        ScheduleEnum.EVERY_5_DAYS.value: 5,
        ScheduleEnum.EVERY_6_DAYS.value: 6,
        ScheduleEnum.EVERY_WEEK.value: 7,
        ScheduleEnum.EVERY_10_DAYS.value: 10,
        ScheduleEnum.EVERY_2_WEEKS.value: 14,
    }
    interval = schedule_map.get(schedule, 1)
    return days_diff % interval == 0


@celery_app.task(bind=True, max_retries=3)
def post_status(self, user_id: int, status_ids: list[int]):
    db = sessionLocal()
    try:
        statuses = db.query(StatusDB).filter(StatusDB.id.in_(status_ids)).all()

        write_ups = []
        image_statuses = []

        for status in statuses:
            if status.is_text:
                write_ups.append(status.write_up)
            else:
                image_statuses.append((status.images_path, status.write_up))

        if image_statuses:
            send_status_images(user_id, image_statuses)
        if write_ups:
            send_status_texts(user_id, write_ups)

        for status in statuses:
            status.is_upload = True
        db.commit()

    except Exception as e:
        db.rollback()
        print(f"Error posting status for user {user_id}: {e}")
        db.close()
        self.retry(exc=e, countdown=30)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def schedule_status_task(self):
    db = sessionLocal()
    try:
        now = datetime.utcnow()
        start_time = (datetime.utcnow() - timedelta(minutes=30)).time()
        end_time = (datetime.utcnow() + timedelta(minutes=30)).time()

        users = db.query(UserDB).join(StatusDB).filter(
            StatusDB.is_upload == False,  # noqa: E712
            StatusDB.schedule_time.between(start_time, end_time)
        ).all()

        for user in users:
            due_status_ids = []
            for status in user.statuses:
                days_diff = (now.date() - status.created_at.date()).days
                if is_due_by_schedule(status.schedule, days_diff):
                    due_status_ids.append(status.id)

            if due_status_ids:
                post_status.delay(user.id, due_status_ids)

    except Exception as e:
        print(f"Error in schedule_status_task: {e}")
        db.close()
        self.retry(exc=e, countdown=30)
    finally:
        db.close()

@celery_app.task(bind=True, max_retries=3)
def whatsapp_login_task(self, user_id: int, phone: str, country: str):
    try:
        print(f"Starting WhatsApp login for {phone} ({country})...")
        login_or_restore(user_id, phone, country)
        print("Login completed successfully!")
    except Exception as e:
        print(f"Login failed: {e}")
        self.retry(exc=e, countdown=30)