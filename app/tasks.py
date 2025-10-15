import os
import pathlib
import shutil
import logging
from datetime import datetime, timedelta
from celery import chain
from .celery_app import celery_app
from .post_status import send_status_images, send_status_texts
from app.database import sessionLocal
from app.model import StatusDB, ScheduleEnum, UserDB
from .whatsapp_login import login_or_restore
from .gdrive import (
    upload_folder, upload_file, list_files_in_folder,
    delete_by_name, download_folder
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent


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
def post_status(self, MAIN_DIR, status_ids: list[int]):
    db = sessionLocal()
    try:
        logger.info(f"Posting statuses {status_ids} from MAIN_DIR {MAIN_DIR}")

        statuses = db.query(StatusDB).filter(StatusDB.id.in_(status_ids)).all()
        if not statuses:
            logger.warning("No statuses found to post")
            return

        write_ups = []
        image_statuses = []
        user = None

        for status in statuses:
            user = db.query(UserDB).filter_by(id=status.user_id).first()
            if status.is_text:
                write_ups.append(status.write_up)
            else:
                image_statuses.append((status.images_path, status.write_up))

        if not user:
            logger.error("No user found for given statuses")
            return

        browser, wait = login_or_restore(user.phone, user.country, str(os.path.join(MAIN_DIR, "profiles")))

        if image_statuses:
            logger.info(f"Sending {len(image_statuses)} image statuses for {user.phone} ({user.country})")
            send_status_images(image_statuses, user.phone, user.country, browser, wait)
        if write_ups:
            logger.info(f"Sending {len(write_ups)} text statuses for {user.phone} ({user.country})")
            send_status_texts(write_ups, user.phone, user.country, browser, wait)

        for status in statuses:
            status.is_upload = True
        db.commit()
        logger.info("Statuses marked as uploaded")

        shutil.rmtree(MAIN_DIR)
        logger.info(f"Cleaned up MAIN_DIR {MAIN_DIR}")

    except Exception as e:
        db.rollback()
        logger.error(f"Error posting status: {e}", exc_info=True)
        self.retry(exc=e, countdown=30)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def schedule_status_task(self):
    db = sessionLocal()
    try:
        logger.info("Running schedule_status_task")
        now = datetime.utcnow()
        start_time = (now - timedelta(minutes=30)).time()
        end_time = (now + timedelta(minutes=30)).time()

        users = db.query(UserDB).join(StatusDB).filter(
            StatusDB.is_upload == False,  # noqa: E712
            StatusDB.schedule_time.between(start_time, end_time)
        ).all()

        logger.info(f"Found {len(users)} users with pending statuses in time window")

        for user in users:
            due_status_ids = []
            for status in user.statuses:
                days_diff = (now.date() - status.created_at.date()).days
                if is_due_by_schedule(status.schedule, days_diff):
                    due_status_ids.append(status.id)

            if due_status_ids:
                logger.info(f"Scheduling statuses {due_status_ids} for user {user.id}")
                chain(
                    download_user_main_folder.s(user.id),
                    post_status.s(due_status_ids)
                ).delay()

    except Exception as e:
        logger.error(f"Error in schedule_status_task: {e}", exc_info=True)
        self.retry(exc=e, countdown=30)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def update_is_uploaded(self):
    db = sessionLocal()
    try:
        logger.info("Resetting is_upload flag for all statuses")
        statuses = db.query(StatusDB).all()
        for status in statuses:
            status.is_upload = False
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating is_upload: {e}", exc_info=True)
        self.retry(exc=e, countdown=30)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def whatsapp_login_task(self, phone: str, country: str, PROFILES_DIR: str):
    try:
        logger.info(f"Starting WhatsApp login for {phone} ({country})")
        login_or_restore(phone, country, PROFILES_DIR)
        logger.info("Login completed successfully")
    except Exception as e:
        logger.error(f"Login failed: {e}", exc_info=True)
        self.retry(exc=e, countdown=30)


@celery_app.task(bind=True, max_retries=3)
def upload_profile(self, main_dir, user_id):
    db = sessionLocal()
    try:
        logger.info(f"Uploading profile for user {user_id}")
        user = db.query(UserDB).filter(UserDB.id == user_id).first()
        folder = upload_folder(main_dir)
        user.main_folder_id = folder.get("id")
        db.commit()
        logger.info("Profile uploaded successfully")
    except Exception as e:
        db.rollback()
        logger.error(f"Error in upload profile: {e}", exc_info=True)
        self.retry(exc=e, countdown=30)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def upload_media(self, media_file, user_id):
    db = sessionLocal()
    try:
        logger.info(f"Uploading media {media_file} for user {user_id}")
        user = db.query(UserDB).filter(UserDB.id == user_id).first()

        items = list_files_in_folder(user.main_folder_id)
        media_folder_id = None
        for item in items:
            if item["mimeType"] == "application/vnd.google-apps.folder" and item["name"] == "media":
                media_folder_id = item["id"]
                break

        if not media_folder_id:
            media_folder = upload_folder("media", user.main_folder_id)
            media_folder_id = media_folder.get("id")

        upload_file(media_file, media_folder_id)
        logger.info("Media uploaded successfully")
    except Exception as e:
        logger.error(f"Error in upload_media: {e}", exc_info=True)
        self.retry(exc=e, countdown=30)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def delete_media(self, media_file, user_id):
    db = sessionLocal()
    try:
        logger.info(f"Deleting media {media_file} for user {user_id}")
        user = db.query(UserDB).filter(UserDB.id == user_id).first()

        items = list_files_in_folder(user.main_folder_id)
        media_folder_id = None
        for item in items:
            if item["mimeType"] == "application/vnd.google-apps.folder" and item["name"] == "media":
                media_folder_id = item["id"]
                break

        if not media_folder_id:
            media_folder = upload_folder("media", user.main_folder_id)
            media_folder_id = media_folder.get("id")

        name = os.path.basename(media_file)
        delete_by_name(name, media_folder_id)
        logger.info("Media deleted successfully")
    except Exception as e:
        logger.error(f"Error in delete_media: {e}", exc_info=True)
        self.retry(exc=e, countdown=30)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def download_media(self, BASE_DIR, user_id):
    db = sessionLocal()
    try:
        logger.info(f"Downloading media for user {user_id}")
        user = db.query(UserDB).filter(UserDB.id == user_id).first()

        items = list_files_in_folder(user.main_folder_id)
        media_folder_id = None
        for item in items:
            if item["mimeType"] == "application/vnd.google-apps.folder" and item["name"] == "media":
                media_folder_id = item["id"]
                break

        if not media_folder_id:
            media_folder = upload_folder("media", user.main_folder_id)
            media_folder_id = media_folder.get("id")

        MAIN_DIR = os.path.join(BASE_DIR, str(user_id))
        MEDIA_DIR = os.path.join(MAIN_DIR, "media")
        os.makedirs(MAIN_DIR, exist_ok=True)
        os.makedirs(MEDIA_DIR, exist_ok=True)

        download_folder(media_folder_id, MEDIA_DIR)
        logger.info("Media downloaded successfully")
    except Exception as e:
        logger.error(f"Error in download_media: {e}", exc_info=True)
        self.retry(exc=e, countdown=30)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def download_user_main_folder(self, user_id):
    db = sessionLocal()
    try:
        logger.info(f"Downloading main folder for user {user_id}")
        user = db.query(UserDB).filter(UserDB.id == user_id).first()

        MAIN_DIR = os.path.join(BASE_DIR, str(user_id))
        os.makedirs(MAIN_DIR, exist_ok=True)

        download_folder(user.main_folder_id, MAIN_DIR)
        logger.info("Main folder downloaded successfully")
        return MAIN_DIR
    except Exception as e:
        logger.error(f"Error in download_user_main_folder: {e}", exc_info=True)
        self.retry(exc=e, countdown=30)
    finally:
        db.close()
