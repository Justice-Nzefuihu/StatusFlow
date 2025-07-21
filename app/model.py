from datetime import datetime
from sqlalchemy import ForeignKey
from sqlalchemy.orm import (
    Mapped, mapped_column, relationship, DeclarativeBase
)
from typing import List

class Base(DeclarativeBase):
    id: Mapped[int] = mapped_column(primary_key=True)



class UserDB(Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(unique=True)
    link: Mapped[str] = mapped_column(unique=True)
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        onupdate=datetime.utcnow
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

    user: Mapped[UserDB] = relationship(back_populates="statuses")
    images: Mapped[List['ImageDB']] = relationship(back_populates='status', cascade="all, delete")

class ImageDB(Base):
    __tablename__ = "images"

    images: Mapped[str] = mapped_column()
    status_id: Mapped[int] = mapped_column(ForeignKey(
        "statuses.id", ondelete="CASCADE"
    ), index=True)

    status: Mapped[StatusDB] = relationship(back_populates="images")