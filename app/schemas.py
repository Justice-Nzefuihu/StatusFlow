from pydantic import BaseModel, constr
from datetime import datetime, time
from typing import List
from .model import ScheduleEnum
from uuid import UUID


class UserBase(BaseModel):
    phone: constr(max_length=20, pattern= "^\\+[1-9]\\d{7,14}$") # type: ignore
    country: constr(max_length=50) # type: ignore

class UserCreate(UserBase):
    pass

class User(UserBase):
    id: UUID
    created_at: datetime
    sequence: int
    status: List["Status"] = []
    

    class Config:
        from_attributes = True

class StatusBase(BaseModel):
    write_up: str | None = None
    schedule: ScheduleEnum
    schedule_time: time

class StatusCreate(StatusBase):
    image: str
    images_path: str | None = None
    is_text: bool = False

class StatusUpdate(StatusBase):
    pass

class Status(StatusBase):
    user_id: UUID
    is_text: bool = False
    images_path: str | None = None
    is_upload: bool
    id: UUID
    created_at: datetime
    user: User

    class Config:
        from_attributes = True


User.update_forward_refs()
Status.update_forward_refs()
