from datetime import datetime
from sqlalchemy import ForeignKey, UniqueConstraint
from enum import Enum
from sqlalchemy.orm import (
    Mapped, mapped_column, DeclarativeBase, relationship
)
from typing import List
from .database import Base


class UserDB(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True)
    link: Mapped[str] = mapped_column(unique=True)
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        onupdate=datetime.utcnow
        )
    
    status: Mapped[List['StatusDB']] = relationship(back_populates='user')
    

class StatusDB(Base):
    __tablename__ = "status"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey(
        "user.id", ondelete="CASCADE"
    ), index=True)

    user: Mapped[UserDB] = relationship(back_populates="status")

class ImageDB(Base):
    __tablename__ = "status"

    id: Mapped[int] = mapped_column(primary_key=True)