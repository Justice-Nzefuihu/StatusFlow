from fastapi import (
    APIRouter, Depends, HTTPException, status
    )
from ..schemas import UserCreate, User
from typing import Annotated
from sqlalchemy.orm import Session
from ..database import get_db
from ..model import UserDB
from ..tasks import whatsapp_login_task, upload_profile
from celery import chain
import pathlib
import os

router = APIRouter(prefix="/user", tags=["User"])

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent.parent

@router.post(
    '/register', status_code=status.HTTP_201_CREATED, response_model=User
    )
def create_user(
    user : UserCreate, db : Annotated[Session, Depends(get_db)]
    ):
    prev_user = db.query(UserDB).filter_by(phone=user.phone).first()
    if prev_user:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="phone number already exist"
        )
    
    
    new_user = UserDB(**user.dict())
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    MAIN_DIR = os.path.join(BASE_DIR, str(new_user.id))
    PROFILES_DIR = os.path.join(MAIN_DIR, "profiles")
    MEDIA_DIR = os.path.join(MAIN_DIR, 'media')

    os.makedirs(MAIN_DIR, exist_ok=True)
    os.makedirs(PROFILES_DIR, exist_ok=True)
    os.makedirs(MEDIA_DIR, exist_ok=True)
    
    chain(
        whatsapp_login_task.si(new_user.phone, new_user.country, PROFILES_DIR),
        upload_profile.si(main_dir=MAIN_DIR, user_id=new_user.id)
    ).delay()


    return new_user