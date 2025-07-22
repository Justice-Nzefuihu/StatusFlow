from datetime import datetime
from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import (
    Mapped, mapped_column, relationship, DeclarativeBase
)
from typing import List

class Base(DeclarativeBase):
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)



class UserDB(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("phone", 'country', name="uq_user_phone_country"),
    )

    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    country: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        default=func.now()
    )
    
    statuses: Mapped[List["StatusDB"]] = relationship(
        "StatusDB", back_populates="user", cascade="all, delete"
    )
    

class StatusDB(Base):
    __tablename__ = "statuses"

    user_id: Mapped[int] = mapped_column(ForeignKey(
        "users.id", ondelete="CASCADE"
    ), index=True)
    write_up: Mapped[str | None] = mapped_column(nullable=True)
    is_upload: Mapped[bool] = mapped_column(default=False)
    is_text: Mapped[bool] = mapped_column(default=False)
    images_path: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        default=func.now()
    )
    sequence: Mapped[int] = mapped_column()

    user: Mapped[UserDB] = relationship(back_populates="statuses")