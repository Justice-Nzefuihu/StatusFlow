from fastapi import APIRouter, Depends, HTTPException, status
from ..schemas import UserCreate, User
from typing import Annotated
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from ..database import get_db
from ..model import UserDB
from ..tasks import whatsapp_login_task, upload_profile
from celery import chain
import pathlib
import os
import logging

router = APIRouter(prefix="/user", tags=["User"])

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent.parent


@router.post(
    '/',
    status_code=status.HTTP_201_CREATED,
    response_model=User
)
def create_user(
    user: UserCreate,
    db: Annotated[Session, Depends(get_db)]
):
    """
    Register a new user, initialize local folders,
    and start background tasks for WhatsApp login and profile upload.
    """
    try:
        # Check if the phone number already exists
        existing_user = db.query(UserDB).filter_by(phone=user.phone).first()
        if existing_user:
            logger.warning("Attempted registration with existing phone number.")
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Phone number already exists."
            )

        # Create and save new user
        new_user = UserDB(**user.dict())
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        logger.info(f"User created successfully (UserID={new_user.id}).")

        # Prepare directories
        MAIN_DIR = os.path.join(BASE_DIR, str(new_user.id))
        PROFILES_DIR = os.path.join(MAIN_DIR, "profiles")
        MEDIA_DIR = os.path.join(MAIN_DIR, "media")

        for path in [MAIN_DIR, PROFILES_DIR, MEDIA_DIR]:
            try:
                os.makedirs(path, exist_ok=True)
            except OSError as e:
                logger.error(f"Failed to create directory {path}: {e}")
                raise HTTPException(
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Server error while setting up directories."
                )

        # Schedule WhatsApp login and profile upload via Celery
        try:
            chain(
                whatsapp_login_task.si(new_user.phone, new_user.country, PROFILES_DIR),
                upload_profile.si(main_dir=MAIN_DIR, user_id=new_user.id),
            ).delay()
            logger.info(f"Background tasks scheduled for user {new_user.id}.")
        except Exception as e:
            logger.error(f"Failed to enqueue background tasks: {e}")

        return new_user

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error while creating user: {e}")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error during registration."
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during registration: {e}")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected server error during registration."
        )
    finally:
        db.close()
