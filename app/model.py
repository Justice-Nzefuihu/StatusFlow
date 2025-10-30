from datetime import datetime, time
from sqlalchemy import ForeignKey, String, UniqueConstraint, Time
from sqlalchemy.sql import func
from sqlalchemy.orm import (
    Mapped, mapped_column, relationship, DeclarativeBase
)
from uuid import UUID, uuid4
from enum import Enum
from typing import List

class Base(DeclarativeBase):
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)



class UserDB(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("phone", 'country', name="uq_user_phone_country"),
    )

    phone: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True)
    country: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        default=func.now()
    )
    login_status: Mapped[bool] = mapped_column(default=False)
    main_folder_id: Mapped[ str | None] = mapped_column(String(50), unique=True, nullable=True)
    sequence: Mapped[int] = mapped_column(default=0, nullable=True)
    statuses: Mapped[List["StatusDB"]] = relationship(
        "StatusDB", back_populates="user", cascade="all, delete"
    )

class ScheduleEnum(str, Enum):
    EVERYDAY = "Every Day"
    EVERY_2_DAYS = "Every 2 Days"
    EVERY_3_DAYS = "Every 3 Days"
    EVERY_4_DAYS = "Every 4 Days"
    EVERY_5_DAYS = "Every 5 Days"
    EVERY_6_DAYS = "Every 6 Days"
    EVERY_WEEK = "Every Week"
    EVERY_10_DAYS = "Every 10 Days"
    EVERY_2_WEEKS = "Every 2 Weeks"


class StatusDB(Base):
    __tablename__ = "statuses"

    user_id: Mapped[int] = mapped_column(ForeignKey(
        "users.id", ondelete="CASCADE"
    ), index=True)
    write_up: Mapped[str | None] = mapped_column(nullable=True)
    is_upload: Mapped[bool] = mapped_column(default=False)
    is_text: Mapped[bool] = mapped_column(default=False)
    images_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        default=func.now()
    )
    schedule: Mapped[ScheduleEnum] = mapped_column(String(20), default=ScheduleEnum.EVERYDAY.value)
    schedule_time: Mapped[time] = mapped_column(Time(), default=time(7, 0))

    user: Mapped[UserDB] = relationship(back_populates="statuses")