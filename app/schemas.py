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
    status: List["Status"] = []
    

    class Config:
        from_attributes = True



class Status(BaseModel):
    write_up: str | None = None
    is_text: bool = False
    image_path: str | None = None
    schedule: ScheduleEnum
    time: time
    id: UUID
    user_id: UUID
    is_upload: bool
    created_at: datetime
    sequuence: int
    user: User

    class Config:
        from_attributes = True


User.update_forward_refs()
Status.update_forward_refs()
