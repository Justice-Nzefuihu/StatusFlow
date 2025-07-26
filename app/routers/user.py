from fastapi import (
    APIRouter, Depends, HTTPException, status
    )
from ..schemas import UserCreate, User
from typing import Annotated
from sqlalchemy.orm import Session
from ..database import get_db
from ..model import UserDB
from ..tasks import whatsapp_login_task


router = APIRouter(prefix="/user", tags=["User"])


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

    whatsapp_login_task.delay(new_user.id, new_user.phone, new_user.country)

    return new_user