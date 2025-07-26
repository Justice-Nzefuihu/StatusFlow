from fastapi import (
    APIRouter, Depends, HTTPException, status, 
    Response, UploadFile, File, Form
    )
from ..schemas import Status
from typing import Annotated, List
from sqlalchemy.orm import Session, joinedload
from ..database import get_db
from ..model import StatusDB
from sqlalchemy import or_, and_
import os
import shutil

router = APIRouter(prefix="/user", tags=["User"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post(
    '/', status_code=status.HTTP_201_CREATED, response_model=Status
    )
def create_status(
    *, user_id: int, write_up: str | None = Form(None),
    is_text: bool = Form(False),
    schedule: str = Form(...),
    time: str = Form(...),
    image: UploadFile | None = File(None), 
    db : Annotated[Session, Depends(get_db)]
    ):

    image_path = None
    if image:
        file_name = image.filename
        user_profile_path = os.path.join(UPLOAD_DIR, user_id)
        os.makedirs(user_profile_path, exist_ok=True)
        file_location = os.path.join(user_profile_path, file_name)
        os.makedirs(file_location, exist_ok=True)

        with open(file_location, "wb") as buffer:
                shutil.copyfileobj(image.file, buffer)

        image_path = str(file_location)
        

    prev_status = db.query(StatusDB).filter(
        or_(
            StatusDB.images_path == image_path,
            and_(
                StatusDB.write_up == write_up, 
                StatusDB.is_text == is_text
            )
        ), StatusDB.user_id == user_id
        ).first()
   
    if prev_status:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Status already exist"
        )
     
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
    
    new_status = StatusDB(
        user_id=user_id,
        write_up=write_up,
        is_text=is_text,
        images_path=image_path,
        schedule=schedule,
        time=time
    )

    db.add(new_status)
    db.commit()
    db.refresh(new_status)

    return new_status

@router.get('/', response_model=List[StatusDB])
def get_statuses(
    user_id: int, db : Annotated[Session, Depends(get_db)]
):
    status = db.query(StatusDB).filter(StatusDB.user_id == user_id).options(
        joinedload(StatusDB.user)
    ).all()

    return status

@router.delete('/{status_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_status(
    user_id: int, status_id: int, 
    db : Annotated[Session, Depends(get_db)]
):
    current_status_qs = db.query(StatusDB).filter(
        StatusDB.id == status_id,
        StatusDB.user_id == user_id
        )
    current_status = current_status_qs.first()

    if not current_status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Status with id '{status_id}' not found"
        )
    
    current_status_qs.delete(synchronize_session=False)
    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)



@router.put('/{status_id}', response_model=Status)
def update_employee(
    *, user_id: int, status_id: int,  write_up: str | None = Form(None),
    schedule: str = Form(...),
    time: str = Form(...),
    db : Annotated[Session, Depends(get_db)]
):
    current_status_qs = db.query(StatusDB).filter(
        StatusDB.id == status_id,
        StatusDB.user_id == user_id
        )
    current_status = current_status_qs.first()

    if not current_status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Status with id '{status_id}' not found"
        )
    
    current_status_qs.update({
        "write_up": write_up,
        "schedule": schedule,
        "time": time}, synchronize_session=False)
    db.commit()

    db.refresh(current_status)

    return current_status

