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

        browser, wait = login_or_restore(user.phone, user.country, str(os.path.join(MAIN_DIR, "profiles")), user.id, for_status=True)

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

        browser.quit()
        logger.info("Closed browser for %s (%s)", user.phone, user.country)

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
        now = datetime.now()
        start_time = now.time()
        end_time = (now + timedelta(minutes=30)).time()

        logger.info(f"Checking statuses scheduled between {start_time} and {end_time}")

        # Query directly from Status table (avoid heavy join)
        due_statuses = (
            db.query(StatusDB)
            .filter(
                StatusDB.is_upload.is_(False),
                StatusDB.schedule_time.between(start_time, end_time)
            )
            .all()
        )

        if not due_statuses:
            logger.info("No pending statuses in this interval.")
            return

        # Group statuses by user
        user_map = {}
        for status in due_statuses:
            user_map.setdefault(status.user_id, []).append(status.id)

        logger.info(f"Found {len(user_map)} users with scheduled statuses.")

        # Schedule Celery chains per user
        for user_id, status_ids in user_map.items():
            logger.info(f"Scheduling {len(status_ids)} statuses for user {user_id}")
            chain(
                download_user_main_folder.s(user_id),
                post_status.s(status_ids)
            ).delay()

        logger.info("All due statuses scheduled successfully.")

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
        statuses = db.query(StatusDB).filter(
            StatusDB.is_upload.is_(True)
        ).all()
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
    db = sessionLocal()
    try:
        logger.info(f"Starting WhatsApp login for {phone} ({country})")
        login_or_restore(phone, country, PROFILES_DIR)
        logger.info("Login completed successfully")
    except Exception as e:
        logger.error(f"Login failed: {e}", exc_info=True)

        try:
            # Retry (up to 3 times)
            self.retry(exc=e, countdown=30)
        except self.MaxRetriesExceededError:
            # Only run this block if ALL retries have failed
            logger.critical(
                "All login retries failed. Beginning user cleanup...",
                extra={"phone": phone, "country": country}
            )

            try:
                user = db.query(UserDB).filter_by(phone=phone, country=country).first()

                if user:
                    # Proceed only if login_status == False AND main_folder is None
                    if not user.login_status and not user.main_folder_id:
                        base_folder = os.path.join(os.path.dirname(PROFILES_DIR), str(user.id))

                        # Delete user’s folder safely
                        if os.path.exists(base_folder):
                            shutil.rmtree(base_folder, ignore_errors=True)
                            logger.warning(
                                "Deleted folder for user due to failed login",
                                extra={"phone": phone, "folder": base_folder}
                            )

                        # Delete user record from DB
                        db.delete(user)
                        db.commit()
                        logger.warning(
                            "User deleted after repeated login failures",
                            extra={"phone": phone, "country": country}
                        )
                    else:
                        logger.info(
                            "User not deleted — login_status or main_folder set",
                            extra={
                                "phone": phone,
                                "login_status": user.login_status,
                                "main_folder": user.main_folder_id,
                            },
                        )
                else:
                    logger.warning(
                        "User not found in DB during cleanup",
                        extra={"phone": phone, "country": country}
                    )

            except Exception as cleanup_error:
                db.rollback()
                logger.error(
                    f"Error during user cleanup: {str(cleanup_error)}",
                    exc_info=True,
                    extra={"phone": phone, "country": country}
                )

    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def upload_profile(self, main_dir, user_id, for_status: bool = False):
    db = sessionLocal()
    try:
        logger.info(f"Uploading profile for user {user_id}")
        user = db.query(UserDB).filter(UserDB.id == user_id).first()

        if for_status:
            folder = upload_folder(main_dir, delete=False)
        else:
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

        MAIN_DIR = os.path.join(BASE_DIR, str(user_id))
        
        if os.path.exists(MAIN_DIR):
            shutil.rmtree(MAIN_DIR)
            logger.info(f"Deleted local media file: {media_file}")

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
        if not name.endswith(".enc"):
            name += ".enc"
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
