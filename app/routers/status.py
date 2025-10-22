from fastapi import (
    APIRouter, Depends, HTTPException, status, 
    Response, UploadFile, File, Form
)
from typing import Annotated, List
from sqlalchemy.orm import Session, joinedload
from ..schemas import Status
from ..database import get_db
from ..model import StatusDB, UserDB, ScheduleEnum
from ..tasks import upload_media, delete_media, download_media
import os
import shutil
import pathlib
import logging
from datetime import time
from uuid import UUID

# ---------------- Logging Setup ---------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s"
)
logger = logging.getLogger(__name__)

# ---------------- Router ---------------- #
router = APIRouter(prefix="/status/{user_id}", tags=["Status"])
BASE_DIR = pathlib.Path(__file__).resolve().parent.parent.parent


# ---------------- Create Status ---------------- #
@router.post('/', status_code=status.HTTP_201_CREATED, response_model=Status)
def create_status(
    *,
    user_id: UUID,
    write_up: str | None = Form(None),
    is_text: bool = Form(False),
    schedule: ScheduleEnum = Form(...),
    time: time = Form(time(7, 0)),
    image: UploadFile | None = File(None),
    db: Annotated[Session, Depends(get_db)]
):
    try:
        image_path = None
        MAIN_DIR = os.path.join(BASE_DIR, str(user_id))
        MEDIA_DIR = os.path.join(MAIN_DIR, 'media')

        os.makedirs(MAIN_DIR, exist_ok=True)
        os.makedirs(MEDIA_DIR, exist_ok=True)

        if image:
            file_name = image.filename
            file_location = os.path.join(MAIN_DIR, file_name)
            with open(file_location, "wb") as buffer:
                shutil.copyfileobj(image.file, buffer)
            image_path = str(file_location)
            logger.info(f"Uploaded media saved at {file_location}")

        if is_text and image is not None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Text-only status cannot include an image."
            )

        if not is_text and image is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Image status must include an image."
            )

        user = db.query(UserDB).filter_by(id=user_id).first()
        if not user:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=f"User with id {user_id} not found"
            )

        if is_text:
            prev_status = (
                db.query(StatusDB)
                .filter(
                    StatusDB.user_id == user_id,
                    StatusDB.is_text.is_(True),
                    StatusDB.write_up == write_up.strip()
                )
                .first()
            )
        else:
            prev_status = (
                db.query(StatusDB)
                .filter(
                    StatusDB.user_id == user_id,
                    StatusDB.is_text.is_(False),
                    StatusDB.images_path == image_path.strip()
                )
                .first()
            )

        if user.sequence:
            if user.sequence >= 20:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail="Statuses can't exceed 20"
                )
            user.sequence += 1
        else:
            user.sequence = 1

        if prev_status:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Status already exists"
            )

        new_status = StatusDB(
            user_id=user_id,
            write_up=write_up,
            is_text=is_text,
            images_path=image_path,
            schedule=schedule,
            schedule_time=time
        )

        db.add(new_status)
        db.commit()
        db.refresh(new_status)
        logger.info(f"New status created for user {user_id} (status_id={new_status.id})")

        if image_path:
            upload_media.delay(image_path, user_id)
            logger.info(f"Media upload task triggered for user {user_id}")


        return new_status

    except HTTPException as http_err:
        db.rollback()
        logger.error(f"HTTP error while creating status: {http_err.detail}")
        raise http_err

    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error creating status for user {user_id}: {e}")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


# ---------------- Get Statuses ---------------- #
@router.get('/', response_model=List[Status])
def get_statuses(user_id: UUID, db: Annotated[Session, Depends(get_db)]):
    try:
        user = db.query(UserDB).filter_by(id=user_id).first()
        if not user:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=f"User with id {user_id} not found"
            )

        statuses = db.query(StatusDB).filter(
            StatusDB.user_id == user_id
        ).options(joinedload(StatusDB.user)).all()

        media_dir = os.path.join(BASE_DIR, str(user_id), "media")
        if not os.path.exists(media_dir) or not os.listdir(media_dir):
            download_media.delay(str(BASE_DIR), str(user_id))
            logger.info(f"Triggered media download for user {user_id}")

        logger.info(f"Retrieved {len(statuses)} statuses for user {user_id}")
        return statuses

    except HTTPException as http_err:
        logger.error(f"HTTP error retrieving statuses: {http_err.detail}")
        raise http_err
    except Exception as e:
        logger.error(f"Unexpected error fetching statuses for user {user_id}: {e}")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


# ---------------- Delete Status ---------------- #
@router.delete('/{status_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_status(user_id: UUID, status_id: UUID, db: Annotated[Session, Depends(get_db)]):
    try:
        user = db.query(UserDB).filter_by(id=user_id).first()
        if not user:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=f"User with id {user_id} not found"
            )

        current_status_qs = db.query(StatusDB).filter(
            StatusDB.id == status_id,
            StatusDB.user_id == user_id
        )
        current_status = current_status_qs.first()

        if not current_status:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=f"Status with id '{status_id}' not found"
            )

        image_path = current_status.images_path
        current_status_qs.delete(synchronize_session=False)
        user.sequence -= 1
        db.commit()
        logger.info(f"Deleted status {status_id} for user {user_id}")

        if image_path:
            delete_media.delay(str(image_path), str(user_id))
            logger.info(f"Triggered media deletion for user {user_id}")

        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except HTTPException as http_err:
        db.rollback()
        logger.error(f"HTTP error deleting status: {http_err.detail}")
        raise http_err

    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error deleting status {status_id} for user {user_id}: {e}")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


# ---------------- Update Status ---------------- #
@router.put('/{status_id}', response_model=Status)
def update_status(
    *,
    user_id: UUID,
    status_id: UUID,
    write_up: str | None = Form(None),
    schedule: ScheduleEnum = Form(...),
    time: time = Form(time(7, 0)),
    db: Annotated[Session, Depends(get_db)]
):
    try:
        user = db.query(UserDB).filter_by(id=user_id).first()
        if not user:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=f"User with id {user_id} not found"
            )

        current_status_qs = db.query(StatusDB).filter(
            StatusDB.id == status_id,
            StatusDB.user_id == user_id
        )
        current_status = current_status_qs.first()

        if not current_status:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=f"Status with id '{status_id}' not found"
            )
        
        if current_status.is_text:
            if write_up == '':
                raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Can not update text-only status with nothing."
                )
            
            prev_status = (
                db.query(StatusDB)
                .filter(
                    StatusDB.user_id == user_id,
                    StatusDB.is_text.is_(True),
                    StatusDB.write_up == write_up.strip(),
                    StatusDB.id != status_id
                )
                .first()
            )

            if prev_status:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail="Status already exists"
                )

        current_status_qs.update({
            "write_up": write_up,
            "schedule": schedule,
            "schedule_time": time
        }, synchronize_session=False)

        db.commit()
        db.refresh(current_status)
        logger.info(f"Updated status {status_id} for user {user_id}")

        return current_status

    except HTTPException as http_err:
        db.rollback()
        logger.error(f"HTTP error updating status: {http_err.detail}")
        raise http_err

    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error updating status {status_id} for user {user_id}: {e}")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")
