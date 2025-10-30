from fastapi import (
    APIRouter, Depends, HTTPException, status, 
    Response
)
from typing import Annotated, List
from sqlalchemy.orm import Session, joinedload
from ..schemas import Status, StatusCreate, StatusUpdate
from ..database import get_db
from ..model import StatusDB, UserDB, ScheduleEnum
from ..tasks import upload_media, delete_media, download_media
from app.middlewares import get_rate_limit

import os
import pathlib
from datetime import datetime, timedelta
from uuid import UUID
import base64

# ---------------- Logging Setup ---------------- #
from app.logging_config import get_logger

logger = get_logger(__name__)

# ---------------- Router ---------------- #
router = APIRouter(prefix="/status/{phone_number}", tags=["Status"])
BASE_DIR = pathlib.Path(__file__).resolve().parent.parent.parent

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


# ---------------- Create Status ---------------- #
@router.post('', status_code=status.HTTP_201_CREATED, 
             response_model=Status, 
             dependencies=[Depends(get_rate_limit(50, 60))])
def create_status(
    *,
    phone_number: str,
    create_data: StatusCreate,
    db: Annotated[Session, Depends(get_db)]
):
    try:
        user = db.query(UserDB).filter_by(phone=phone_number).first()
        user_id = user.id

        write_up = create_data.write_up
        is_text = create_data.is_text
        schedule = create_data.schedule
        time = create_data.schedule_time
        image = create_data.image
    
        image_path = create_data.images_path
        MAIN_DIR = os.path.join(BASE_DIR, str(user_id))
        MEDIA_DIR = os.path.join(MAIN_DIR, 'media')

        os.makedirs(MAIN_DIR, exist_ok=True)
        os.makedirs(MEDIA_DIR, exist_ok=True)

        if image:
            try:
                image_bytes = base64.b64decode(image.split(",")[-1])
                file_name = image_path
                file_location = os.path.join(MEDIA_DIR, file_name)
                with open(file_location, "wb") as f:
                    f.write(image_bytes)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid image data: {e}")

            image_path = str(file_location)
            position = image_path.find(str(user_id))
            user_id_length = len(str(user_id))
            image_path = image_path[:position+user_id_length] + "_uploading" + image_path[position+user_id_length:]

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
            upload_media.delay(str(file_location), user_id)
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
@router.get('', response_model=List[Status], 
            dependencies=[Depends(get_rate_limit(50, 60))])
def get_statuses(phone_number: str, db: Annotated[Session, Depends(get_db)]):
    try:
        user = db.query(UserDB).filter_by(phone=phone_number).first()
        if not user:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=f"User with id {phone_number} not found"
            )
        
        user_id = user.id

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
@router.delete('/{status_id}', 
               status_code=status.HTTP_204_NO_CONTENT
               , dependencies=[Depends(get_rate_limit(50, 60))])
def delete_status(phone_number: str, status_id: UUID, db: Annotated[Session, Depends(get_db)]):
    try:
        user = db.query(UserDB).filter_by(phone=phone_number).first()
        if not user:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=f"User with id {phone_number} not found"
            )
        
        user_id = user.id

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
        
        now = datetime.now()
        start_time = (now - timedelta(minutes=5)).time()
        end_time = (now + timedelta(minutes=35)).time()
        days_diff = (now.date() - current_status.created_at.date()).days

        is_within_window = start_time <= current_status.schedule_time <= end_time

        if((is_due_by_schedule(current_status.schedule, days_diff) 
            or days_diff ==1)
           and is_within_window) and not current_status.is_upload:
            raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete status — upload in progress or within schedule time."
        )

        image_path = current_status.images_path
        current_status_qs.delete(synchronize_session=False)
        user.sequence -= 1
        db.commit()
        logger.info(f"Deleted status {status_id} for user {user_id}")

        if image_path:
            
            if image_path.endswith("_uploading"):
                position = image_path.find(str(user_id))
                user_id_length = len(str(user_id))
                image_path = image_path[:position+user_id_length] + image_path[position+user_id_length:]

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
@router.put('/{status_id}', 
            response_model=Status, 
            dependencies=[Depends(get_rate_limit(50, 60))])
def update_status(
    *,
    phone_number: str,
    status_id: UUID,
    update_data: StatusUpdate,
    db: Annotated[Session, Depends(get_db)]
):
    try:
        user = db.query(UserDB).filter_by(phone=phone_number).first()
        if not user:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=f"User with id {phone_number} not found"
            )
        
        user_id = user.id

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
        
        now = datetime.now()
        start_time = (now - timedelta(minutes=5)).time()
        end_time = (now + timedelta(minutes=35)).time()
        days_diff = (now.date() - current_status.created_at.date()).days

        is_within_window = start_time <= current_status.schedule_time <= end_time

        if((is_due_by_schedule(current_status.schedule, days_diff) 
            or days_diff ==1)
           and is_within_window and not current_status.is_upload):
            raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update status — upload in progress or within schedule time."
        )
        
        if current_status.is_text:
            if update_data.write_up == '':
                raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Can not update text-only status with nothing."
                )
            
            prev_status = (
                db.query(StatusDB)
                .filter(
                    StatusDB.user_id == user_id,
                    StatusDB.is_text.is_(True),
                    StatusDB.write_up == update_data.write_up.strip(),
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
            "write_up": update_data.write_up,
            "schedule": update_data.schedule,
            "schedule_time": update_data.schedule_time
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
